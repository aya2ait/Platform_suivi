from typing import List, Optional, Union, Any, Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

# Import from the new relative paths within the 'app' package
from app.core.database import get_db
from app.models.models import Directeur, Vehicule, Mission, Collaborateur, Affectation, Utilisateur
from app.schemas.schemas import (
    MissionCreate,
    MissionUpdate,
    MissionResponse,
    AssignCollaboratorsRequest,
    AffectationResponse,
    VehiculeResponse,
    UpdateCollaboratorsRequest,
    ManageCollaboratorsRequest,
    DetailedAffectationResponse
)
# Import des fonctions de vérification de disponibilité
from app.services.availability_check import check_mission_availability
# Import des dépendances d'authentification et d'autorisation
from app.core.auth_dependencies import get_current_active_user, require_permission
from app.core.security import RolePermissions # Import pour utiliser les rôles définis

# Create an APIRouter instance for missions
router = APIRouter(
    prefix="/missions",
    tags=["Missions"],
    responses={
        401: {"description": "Non autorisé"},
        403: {"description": "Accès refusé"},
        404: {"description": "Non trouvé"}
    },
)


# --- NOUVELLE FONCTIONNALITÉ: Modifier les collaborateurs affectés ---
@router.put(
    "/{mission_id}/collaborators",
    response_model=List[AffectationResponse],
    status_code=status.HTTP_200_OK,
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:update"))] # Protégé: Requiert la permission de modifier les missions
)
def update_mission_collaborators(
    mission_id: int,
    request: UpdateCollaboratorsRequest,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None # Ajout de la dépendance d'authentification
):
    """
    Met à jour la liste complète des collaborateurs affectés à une mission.
    Remplace tous les collaborateurs existants par la nouvelle liste fournie.
    Vérifie la disponibilité des collaborateurs avant l'affectation.
    """
    # Vérifier que la mission existe
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    # Vérifier la disponibilité des nouveaux collaborateurs
    collaborateur_matricules = [collab.matricule for collab in request.collaborateurs]
    is_available, conflicts = check_mission_availability(
        db=db,
        date_debut=mission_in_db.dateDebut,
        date_fin=mission_in_db.dateFin,
        collaborateur_matricules=collaborateur_matricules,
        exclude_mission_id=mission_id  # Exclure la mission actuelle
    )
    
    if not is_available:
        conflict_details = []
        for conflict in conflicts.get("collaborator_conflicts", []):
            if "error" in conflict:
                conflict_details.append(conflict["error"])
            else:
                conflict_details.append(
                    f"Collaborateur {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                    f"déjà affecté à la mission {conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                )
        
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Certains collaborateurs ne sont pas disponibles pour cette période",
                "conflicts": conflict_details
            }
        )

    # Supprimer toutes les affectations existantes pour cette mission
    db.query(Affectation).filter(Affectation.mission_id == mission_id).delete()
    db.commit()

    # Créer les nouvelles affectations
    new_affectations = []
    collaborateurs_not_found = []
    
    for collab_data in request.collaborateurs:
        collaborateur_in_db = db.query(Collaborateur).filter(
            Collaborateur.matricule == collab_data.matricule
        ).first()
        
        if not collaborateur_in_db:
            collaborateurs_not_found.append(collab_data.matricule)
            continue
        
        new_affectation = Affectation(
            mission_id=mission_id,
            collaborateur_id=collaborateur_in_db.id,
            dejeuner=collab_data.dejeuner if hasattr(collab_data, 'dejeuner') else 0,
            dinner=collab_data.dinner if hasattr(collab_data, 'dinner') else 0,
            accouchement=collab_data.accouchement if hasattr(collab_data, 'accouchement') else 0,
        )
        db.add(new_affectation)
        new_affectations.append(new_affectation)

    # Commit les nouvelles affectations
    if new_affectations:
        db.commit()
        for affectation in new_affectations:
            db.refresh(affectation)

    # Optionnel: log des collaborateurs non trouvés
    if collaborateurs_not_found:
        print(f"Collaborateurs non trouvés lors de la mise à jour: {collaborateurs_not_found}")

    return [AffectationResponse.model_validate(aff) for aff in new_affectations]

# --- NOUVELLE FONCTIONNALITÉ: Modifier partiellement les collaborateurs ---
@router.patch(
    "/{mission_id}/collaborators",
    response_model=List[AffectationResponse],
    status_code=status.HTTP_200_OK,
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:update"))] # Protégé
)
def partially_update_mission_collaborators(
    mission_id: int,
    request: UpdateCollaboratorsRequest,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Met à jour partiellement les collaborateurs d'une mission.
    Ajoute de nouveaux collaborateurs sans supprimer les existants.
    Si un collaborateur est déjà affecté, met à jour ses informations.
    Vérifie la disponibilité des nouveaux collaborateurs.
    """
    # Vérifier que la mission existe
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    # Identifier les nouveaux collaborateurs (non encore affectés)
    new_collaborateurs = []
    for collab_data in request.collaborateurs:
        collaborateur_in_db = db.query(Collaborateur).filter(
            Collaborateur.matricule == collab_data.matricule
        ).first()
        
        if collaborateur_in_db:
            existing_affectation = db.query(Affectation).filter(
                Affectation.mission_id == mission_id,
                Affectation.collaborateur_id == collaborateur_in_db.id
            ).first()
            
            if not existing_affectation:
                new_collaborateurs.append(collab_data.matricule)

    # Vérifier la disponibilité des nouveaux collaborateurs seulement
    if new_collaborateurs:
        is_available, conflicts = check_mission_availability(
            db=db,
            date_debut=mission_in_db.dateDebut,
            date_fin=mission_in_db.dateFin,
            collaborateur_matricules=new_collaborateurs,
            exclude_mission_id=mission_id
        )
        
        if not is_available:
            conflict_details = []
            for conflict in conflicts.get("collaborator_conflicts", []):
                if "error" in conflict:
                    conflict_details.append(conflict["error"])
                else:
                    conflict_details.append(
                        f"Collaborateur {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                        f"déjà affecté à la mission {conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                    )
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Certains nouveaux collaborateurs ne sont pas disponibles pour cette période",
                    "conflicts": conflict_details
                }
            )

    updated_affectations = []
    collaborateurs_not_found = []
    
    for collab_data in request.collaborateurs:
        collaborateur_in_db = db.query(Collaborateur).filter(
            Collaborateur.matricule == collab_data.matricule
        ).first()
        
        if not collaborateur_in_db:
            collaborateurs_not_found.append(collab_data.matricule)
            continue
        
        # Vérifier si le collaborateur est déjà affecté
        existing_affectation = db.query(Affectation).filter(
            Affectation.mission_id == mission_id,
            Affectation.collaborateur_id == collaborateur_in_db.id
        ).first()
        
        if existing_affectation:
            # Mettre à jour l'affectation existante
            if hasattr(collab_data, 'dejeuner'):
                existing_affectation.dejeuner = collab_data.dejeuner
            if hasattr(collab_data, 'dinner'):
                existing_affectation.dinner = collab_data.dinner
            if hasattr(collab_data, 'accouchement'):
                existing_affectation.accouchement = collab_data.accouchement
            
            updated_affectations.append(existing_affectation)
        else:
            # Créer une nouvelle affectation
            new_affectation = Affectation(
                mission_id=mission_id,
                collaborateur_id=collaborateur_in_db.id,
                dejeuner=collab_data.dejeuner if hasattr(collab_data, 'dejeuner') else 0,
                dinner=collab_data.dinner if hasattr(collab_data, 'dinner') else 0,
                accouchement=collab_data.accouchement if hasattr(collab_data, 'accouchement') else 0,
            )
            db.add(new_affectation)
            updated_affectations.append(new_affectation)

    # Commit les changements
    if updated_affectations:
        db.commit()
        for affectation in updated_affectations:
            db.refresh(affectation)

    # Optionnel: log des collaborateurs non trouvés
    if collaborateurs_not_found:
        print(f"Collaborateurs non trouvés lors de la mise à jour partielle: {collaborateurs_not_found}")

    return [AffectationResponse.model_validate(aff) for aff in updated_affectations]

# --- Endpoint pour récupérer tous les véhicules ---
@router.get(
    "/vehicules",
    response_model=List[VehiculeResponse],
    tags=["Vehicules"],
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("vehicule:read"))] # Protégé: Requiert la permission de lire les véhicules
)
def get_all_vehicules(
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Récupère la liste de tous les véhicules disponibles.
    """
    vehicules = db.query(Vehicule).all()
    return vehicules


@router.post(
    "/",
    response_model=MissionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("mission:create"))] 
)
def create_mission(
    mission: MissionCreate,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Permet à un directeur de créer une nouvelle mission avec affectation optionnelle de collaborateurs.
    L'ID du directeur connecté est automatiquement attribué.
    Vérifie la disponibilité du véhicule et des collaborateurs avant la création.
    """
    # --- DÉBUT DE LA MODIFICATION POUR L'ID DIRECTEUR ---
    # Créons un dictionnaire modifiable à partir des données de la mission
    # pour pouvoir manipuler le directeur_id
    mission_data_to_create = mission.model_dump() 

    if current_user.role == "directeur":
        directeur_associe = current_user.directeur
        if not directeur_associe:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="L'utilisateur connecté n'est pas associé à un directeur valide."
            )
        # Attribuer automatiquement l'ID du directeur connecté
        mission_data_to_create["directeur_id"] = directeur_associe.id

        # Si le directeur tente de spécifier un autre ID, rejeter la requête
        if mission.directeur_id is not None and mission.directeur_id != directeur_associe.id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Un directeur ne peut créer de mission que pour lui-même."
            )

    elif current_user.role == "administrateur":
        # Un administrateur doit fournir un directeur_id explicite
        if mission.directeur_id is None:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pour un administrateur, 'directeur_id' est requis lors de la création d'une mission."
            )
        # Vérifier si le directeur_id fourni par l'administrateur existe
        directeur_cible = db.query(Directeur).filter(Directeur.id == mission_data_to_create["directeur_id"]).first()
        if not directeur_cible:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Directeur avec l'ID {mission_data_to_create['directeur_id']} non trouvé."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas la permission de créer des missions."
        )
    # --- FIN DE LA MODIFICATION POUR L'ID DIRECTEUR ---


    # La logique suivante est inchangée, elle utilisera le `directeur_id` qui a été mis à jour
    # dans `mission_data_to_create` et les autres champs de `mission` directement.

    # Check if the director exists (cette vérification peut être simplifiée/retirée car elle est gérée au-dessus)
    # directeur_in_db = db.query(Directeur).filter(Directeur.id == mission_data_to_create["directeur_id"]).first()
    # if not directeur_in_db:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail=f"Directeur avec l'ID {mission_data_to_create['directeur_id']} non trouvé."
    #     )

    # Check if the vehicle exists (if provided)
    if mission.vehicule_id:
        vehicule_in_db = db.query(Vehicule).filter(Vehicule.id == mission.vehicule_id).first()
        if not vehicule_in_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Véhicule avec l'ID {mission.vehicule_id} non trouvé."
            )

    # Préparer la liste des matricules des collaborateurs si fournie
    collaborateur_matricules = []
    # Votre logique `hasattr` est conservée ici.
    # Note: Pour que `hasattr(mission, 'collaborateurs')` renvoie True si le client l'envoie,
    # le champ `collaborateurs` doit être défini comme `Optional` dans votre schéma `MissionCreate`.
    # Si vous NE VOULEZ PAS l'ajouter au schéma, alors `hasattr` sera toujours False ici,
    # et cette section ne sera jamais exécutée, ce qui pourrait être la cause de l'erreur initiale.
    # Si vous voulez que les clients puissent inclure des collaborateurs dans ce payload,
    # vous DEVEZ ajouter `collaborateurs: Optional[List[CollaborateurAssign]] = None` à `MissionCreate`.
    # Si la route fonctionnait avant sans cela, c'est que les collaborateurs étaient gérés différemment ou pas dans ce payload.
    if hasattr(mission, 'collaborateurs') and mission.collaborateurs:
        collaborateur_matricules = [collab.matricule for collab in mission.collaborateurs]

    # Vérifier la disponibilité du véhicule et des collaborateurs
    is_available, conflicts = check_mission_availability(
        db=db,
        date_debut=mission.dateDebut,
        date_fin=mission.dateFin,
        vehicule_id=mission.vehicule_id,
        collaborateur_matricules=collaborateur_matricules if collaborateur_matricules else None
    )
    
    if not is_available:
        conflict_details = []
        
        # Conflits de véhicule
        for conflict in conflicts.get("vehicle_conflicts", []):
            if "error" in conflict:
                conflict_details.append(conflict["error"])
            else:
                conflict_details.append(
                    f"Véhicule {conflict['vehicule_immatriculation']} déjà affecté à la mission "
                    f"{conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                )
        
        # Conflits de collaborateurs
        for conflict in conflicts.get("collaborator_conflicts", []):
            if "error" in conflict:
                conflict_details.append(conflict["error"])
            else:
                conflict_details.append(
                    f"Collaborateur {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                    f"déjà affecté à la mission {conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                )
        
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Ressources non disponibles pour cette période",
                "conflicts": conflict_details
            }
        )

    # Create the mission (utiliser `mission_data_to_create` qui contient le directeur_id correct)
    # Exclure 'collaborateurs' de `mission_data_to_create` si `MissionCreate` n'inclut PAS ce champ Pydantic.
    # Si `MissionCreate` a `collaborateurs: Optional[List[CollaborateurAssign]]`, alors `model_dump()` exclura déjà par défaut les attributs non mappés à la DB.
    final_mission_data = {k: v for k, v in mission_data_to_create.items() if k != 'collaborateurs'}
    
    db_mission = Mission(**final_mission_data)
    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)
    
    # Handle collaborators assignment if provided (logique inchangée)
    if hasattr(mission, 'collaborateurs') and mission.collaborateurs:
        for collab_data in mission.collaborateurs:
            # Find collaborator by matricule
            collaborateur_in_db = db.query(Collaborateur).filter(
                Collaborateur.matricule == collab_data.matricule
            ).first()
            
            if collaborateur_in_db:
                # Check if already assigned
                existing_affectation = db.query(Affectation).filter(
                    Affectation.mission_id == db_mission.id,
                    Affectation.collaborateur_id == collaborateur_in_db.id
                ).first()
                
                if not existing_affectation:
                    new_affectation = Affectation(
                        mission_id=db_mission.id,
                        collaborateur_id=collaborateur_in_db.id,
                        # Si `CollaborateurAssign` peut inclure dejeuner, dinner, accouchement,
                        # assurez-vous de les inclure ici. Sinon, ils seront par défaut 0.
                        dejeuner=getattr(collab_data, 'dejeuner', 0),
                        dinner=getattr(collab_data, 'dinner', 0),
                        accouchement=getattr(collab_data, 'accouchement', 0)
                    )
                    db.add(new_affectation)
            else:
                print(f"Collaborateur avec matricule {collab_data.matricule} non trouvé lors de la création.")
        
        db.commit()
        db.refresh(db_mission)
    
    return db_mission
@router.post(
    "/{mission_id}/assign_collaborators/",
    response_model=List[AffectationResponse],
    status_code=status.HTTP_200_OK,
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:update"))] # Protégé
)
def assign_collaborators_to_mission(
    mission_id: int,
    request: AssignCollaboratorsRequest,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Permet d'affecter un ou plusieurs collaborateurs à une mission existante
    en utilisant leur matricule. Vérifie la disponibilité avant l'affectation.
    """
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    # Préparer la liste des matricules
    collaborateur_matricules = [collab.matricule for collab in request.collaborateurs]
    
    # Vérifier la disponibilité des collaborateurs
    is_available, conflicts = check_mission_availability(
        db=db,
        date_debut=mission_in_db.dateDebut,
        date_fin=mission_in_db.dateFin,
        collaborateur_matricules=collaborateur_matricules,
        exclude_mission_id=mission_id
    )
    
    if not is_available:
        conflict_details = []
        for conflict in conflicts.get("collaborator_conflicts", []):
            if "error" in conflict:
                conflict_details.append(conflict["error"])
            else:
                conflict_details.append(
                    f"Collaborateur {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                    f"déjà affecté à la mission {conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                )
        
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Certains collaborateurs ne sont pas disponibles pour cette période",
                "conflicts": conflict_details
            }
        )

    assigned_affectations = []
    for collab_assign in request.collaborateurs:
        collaborateur_in_db = db.query(Collaborateur).filter(Collaborateur.matricule == collab_assign.matricule).first()
        if not collaborateur_in_db:
            print(f"Collaborateur avec matricule {collab_assign.matricule} non trouvé. Skipping.")
            continue

        existing_affectation = db.query(Affectation).filter(
            Affectation.mission_id == mission_id,
            Affectation.collaborateur_id == collaborateur_in_db.id
        ).first()

        if existing_affectation:
            print(f"Collaborateur {collab_assign.matricule} déjà affecté à la mission {mission_id}. Skipping.")
            assigned_affectations.append(existing_affectation)
            continue

        new_affectation = Affectation(
            mission_id=mission_id,
            collaborateur_id=collaborateur_in_db.id,
        )
        db.add(new_affectation)
        assigned_affectations.append(new_affectation)

    db.commit()
    for affectation in assigned_affectations:
        db.refresh(affectation)

    newly_added_affectations_response = [
        AffectationResponse.model_validate(aff)
        for aff in assigned_affectations
    ]
    return newly_added_affectations_response

@router.get(
    "/",
    response_model=List[MissionResponse],
    dependencies=[Depends(require_permission("mission:read"))]
)
@router.get(
    "/",
    response_model=List[MissionResponse],
    dependencies=[Depends(require_permission("mission:read"))]
)
def get_all_missions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Récupère toutes les missions.
    Si l'utilisateur connecté est un directeur, il ne voit que ses propres missions.
    Si l'utilisateur est un administrateur, il peut voir toutes les missions.
    """
    query = db.query(Mission)

    # Vérifie le rôle de l'utilisateur connecté
    if current_user.role == "directeur":
        # Grâce à la relation 'directeur' dans le modèle Utilisateur,
        # nous pouvons directement accéder à l'objet Directeur lié.
        directeur_associe = current_user.directeur
        
        if not directeur_associe:
            # Ceci gère le cas improbable où un Utilisateur avec le rôle 'directeur'
            # n'a pas d'entrée correspondante dans la table Directeur.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="L'utilisateur connecté n'est pas associé à un directeur valide."
            )
        
        # Filtre les missions par l'ID du directeur associé à l'utilisateur connecté
        query = query.filter(Mission.directeur_id == directeur_associe.id)
        
    elif current_user.role == "administrateur":
        # Un administrateur peut voir toutes les missions.
        # Si vous souhaitez lui donner la possibilité de filtrer par directeur_id
        # via un paramètre de requête (par exemple, `/missions?directeur_id=X`),
        # vous devriez ajouter `directeur_id: Optional[int] = None` à la signature de la fonction
        # et une condition ici : `if directeur_id: query = query.filter(Mission.directeur_id == directeur_id)`
        pass # Pas de filtre par défaut pour l'administrateur
    else:
        # Pour tout autre rôle qui ne devrait pas avoir accès à cette liste de missions
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas la permission d'accéder à cette ressource."
        )

    # Applique le filtre de statut si un statut est spécifié dans la requête
    if status:
        query = query.filter(Mission.statut == status)

    missions = query.all()
    return missions
@router.put(
    "/{mission_id}",
    response_model=MissionResponse,
    dependencies=[Depends(require_permission("mission:update"))] 
)
def update_mission(
    mission_id: int,
    mission_update: MissionUpdate,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Met à jour les informations d'une mission existante.
    L'ID du directeur est géré automatiquement.
    Vérifie la disponibilité du véhicule et des collaborateurs si les dates sont modifiées.
    """
    db_mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not db_mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    # --- DÉBUT DE LA MODIFICATION POUR L'ID DIRECTEUR ET LES PERMISSIONS ---
    update_data = mission_update.model_dump(exclude_unset=True) # Important: n'inclut que les champs fournis

    if current_user.role == "directeur":
        directeur_associe = current_user.directeur
        if not directeur_associe:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="L'utilisateur connecté n'est pas associé à un directeur valide."
            )
        # Un directeur ne peut modifier que SES PROPRES missions
        if db_mission.directeur_id != directeur_associe.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas autorisé à modifier cette mission. Elle ne vous appartient pas."
            )
        # Empêcher un directeur de modifier le directeur_id d'une mission (le sien ou un autre)
        if "directeur_id" in update_data:
            del update_data["directeur_id"] 
            
    elif current_user.role == "administrateur":
        # Un administrateur peut modifier le directeur_id. Vérifier que le directeur cible existe s'il est fourni.
        if "directeur_id" in update_data and update_data["directeur_id"] is not None:
            directeur_cible = db.query(Directeur).filter(Directeur.id == update_data["directeur_id"]).first()
            if not directeur_cible:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Directeur avec l'ID {update_data['directeur_id']} non trouvé."
                )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas la permission de modifier cette mission."
        )
    # --- FIN DE LA MODIFICATION POUR L'ID DIRECTEUR ET LES PERMISSIONS ---


    # La logique suivante est inchangée, elle utilisera les valeurs de `update_data`
    # pour les champs qui ont été potentiellement modifiés.

    # Check if the director exists if director_id is being updated (cette logique est maintenant couverte au-dessus)
    # if mission_update.directeur_id and mission_update.directeur_id != db_mission.directeur_id:
    #     directeur_in_db = db.query(Directeur).filter(Directeur.id == mission_update.directeur_id).first()
    #     if not directeur_in_db:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail=f"Directeur avec l'ID {mission_update.directeur_id} non trouvé."
    #         )

    # Check if the vehicle exists if vehicule_id is being updated
    if mission_update.vehicule_id is not None and mission_update.vehicule_id != db_mission.vehicule_id: # Utilisez is not None pour inclure None comme valeur valide
        if mission_update.vehicule_id == 0: # Ou toute autre valeur que vous considérez comme "non affecté"
             vehicule_in_db = None # Simule un véhicule retiré
        else:
            vehicule_in_db = db.query(Vehicule).filter(Vehicule.id == mission_update.vehicule_id).first()
        if not vehicule_in_db and mission_update.vehicule_id is not None and mission_update.vehicule_id != 0: # S'il est fourni et n'est pas None/0
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Véhicule avec l'ID {mission_update.vehicule_id} non trouvé."
            )

    # Déterminer les nouvelles dates et véhicule pour la vérification
    # Utilisez 'update_data.get()' pour prendre en compte les champs réellement fournis dans la requête
    new_date_debut = update_data.get("dateDebut", db_mission.dateDebut)
    new_date_fin = update_data.get("dateFin", db_mission.dateFin)
    # Si vehicule_id est présent dans update_data, utilisez sa valeur, sinon, utilisez celle de la DB
    new_vehicule_id = update_data.get("vehicule_id", db_mission.vehicule_id)
    
    # Vérifier si les dates ou le véhicule ont changé (en comparant avec les valeurs originales de db_mission)
    dates_changed = (update_data.get("dateDebut") is not None and update_data["dateDebut"] != db_mission.dateDebut) or \
                    (update_data.get("dateFin") is not None and update_data["dateFin"] != db_mission.dateFin)
    vehicle_changed = update_data.get("vehicule_id") is not None and update_data["vehicule_id"] != db_mission.vehicule_id
    
    # Si les dates ou le véhicule ont changé, vérifier la disponibilité
    if dates_changed or vehicle_changed:
        # Récupérer les collaborateurs actuellement affectés
        # Garder cette logique car elle est votre manière actuelle de récupérer les collaborateurs pour la vérif.
        current_affectations = db.query(Affectation).filter(Affectation.mission_id == mission_id).all()
        current_collaborateurs = []
        if current_affectations:
            # S'assurer que la relation collaborateur_rel est chargée ou la charger manuellement
            collaborateur_ids = [aff.collaborateur_id for aff in current_affectations]
            collaborateurs = db.query(Collaborateur).filter(Collaborateur.id.in_(collaborateur_ids)).all()
            current_collaborateurs = [c.matricule for c in collaborateurs]
        
        # Vérifier la disponibilité avec les nouvelles données
        is_available, conflicts = check_mission_availability(
            db=db,
            date_debut=new_date_debut,
            date_fin=new_date_fin,
            vehicule_id=new_vehicule_id,
            collaborateur_matricules=current_collaborateurs if current_collaborateurs else None,
            exclude_mission_id=mission_id
        )
        
        if not is_available:
            conflict_details = []
            
            # Conflits de véhicule
            for conflict in conflicts.get("vehicle_conflicts", []):
                if "error" in conflict:
                    conflict_details.append(conflict["error"])
                else:
                    conflict_details.append(
                        f"Véhicule {conflict['vehicule_immatriculation']} déjà affecté à la mission "
                        f"{conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                    )
            
            # Conflits de collaborateurs
            for conflict in conflicts.get("collaborator_conflicts", []):
                if "error" in conflict:
                    conflict_details.append(conflict["error"])
                else:
                    conflict_details.append(
                        f"Collaborateur {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                        f"déjà affecté à la mission {conflict['mission_id']} du {conflict['date_debut']} au {conflict['date_fin']}"
                    )
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Ressources non disponibles pour la nouvelle période/véhicule",
                    "conflicts": conflict_details
                }
            )
    
    # Update only the fields that are provided (update_data est déjà filtré par exclude_unset=True)
    # Et le directeur_id est déjà géré par la logique des permissions.
    for key, value in update_data.items():
        setattr(db_mission, key, value)
    
    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)
    return db_mission

@router.delete(
    "/{mission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:delete"))] # Protégé
)
def delete_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Supprime une mission spécifique par son ID.
    Note: Cela devrait également gérer la suppression des affectations associées.
    """
    db_mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not db_mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    db.delete(db_mission)
    db.commit()
    return {"message": "Mission supprimée avec succès."}

@router.get(
    "/{mission_id}/collaborators",
    response_model=List[DetailedAffectationResponse],
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:read"))] # Protégé
)
def get_mission_collaborators(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Récupère tous les collaborateurs affectés à une mission spécifique avec leurs informations détaillées.
    """
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )
    
    # Jointure pour récupérer les affectations avec les informations des collaborateurs
    affectations_with_collaborators = db.query(
        Affectation.id,
        Affectation.mission_id,
        Affectation.collaborateur_id,
        Collaborateur.matricule.label('collaborateur_matricule'),
        Collaborateur.nom.label('collaborateur_nom'),
        Affectation.dejeuner,
        Affectation.dinner,
        Affectation.accouchement,
        Affectation.montantCalcule,
        Affectation.created_at,
        Affectation.updated_at
    ).join(
        Collaborateur, Affectation.collaborateur_id == Collaborateur.id
    ).filter(
        Affectation.mission_id == mission_id
    ).all()
    
    # Convertir les résultats en dictionnaires pour DetailedAffectationResponse
    result = []
    for row in affectations_with_collaborators:
        result.append({
            "id": row.id,
            "mission_id": row.mission_id,
            "collaborateur_id": row.collaborateur_id,
            "collaborateur_matricule": row.collaborateur_matricule,
            "collaborateur_nom": row.collaborateur_nom,
            "dejeuner": row.dejeuner,
            "dinner": row.dinner,
            "accouchement": row.accouchement,
            "montantCalcule": float(row.montantCalcule),
            "created_at": row.created_at,
            "updated_at": row.updated_at
        })
    
    return result

@router.delete(
    "/{mission_id}/unassign_collaborator/{collaborator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:update"))] # Protégé
)
def unassign_collaborator_from_mission(
    mission_id: int,
    collaborator_id: int,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Désaffecte un collaborateur d'une mission spécifique.
    """
    affectation_to_delete = db.query(Affectation).filter(
        Affectation.mission_id == mission_id,
        Affectation.collaborateur_id == collaborator_id
    ).first()

    if not affectation_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Affectation non trouvée pour la mission {mission_id} et le collaborateur {collaborator_id}."
        )
    
    db.delete(affectation_to_delete)
    db.commit()
    return {"message": "Collaborateur désaffecté de la mission avec succès."}

@router.patch(
    "/{mission_id}/manage-collaborators",
    response_model=List[AffectationResponse],
    status_code=status.HTTP_200_OK,
    # MODIFICATION: Utilisation de la chaîne de permission correcte
    dependencies=[Depends(require_permission("mission:update"))] # Protégé
)
def manage_mission_collaborators(
    mission_id: int,
    request: ManageCollaboratorsRequest,
    db: Session = Depends(get_db),
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)] = None
):
    """
    Gère les collaborateurs d'une mission de manière flexible.
    Permet d'ajouter, modifier ou supprimer des collaborateurs en une seule requête.
    Vérifie la disponibilité des collaborateurs avant de les affecter.
    
    Actions possibles:
    - 'add': Ajoute un nouveau collaborateur à la mission
    - 'update': Met à jour les informations d'un collaborateur déjà affecté
    - 'remove': Supprime un collaborateur de la mission
    """
    # Import de la fonction de vérification
    from app.services.availability_check import check_collaborators_availability
    
    # Vérifier que la mission existe
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    results = []
    errors = []
    
    # Collecter les matricules des collaborateurs à ajouter pour vérification groupée
    collaborateurs_to_add = []
    for collab_action in request.collaborateurs:
        if collab_action.action == 'add':
            collaborateurs_to_add.append(collab_action.matricule)
    
    # Vérifier la disponibilité des collaborateurs à ajouter
    if collaborateurs_to_add:
        are_available, conflicts = check_collaborators_availability(
            db=db,
            collaborateur_matricules=collaborateurs_to_add,
            date_debut=mission_in_db.dateDebut,
            date_fin=mission_in_db.dateFin,
            exclude_mission_id=mission_id
        )
        
        if not are_available:
            # Construire un message d'erreur détaillé
            conflict_messages = []
            for conflict in conflicts:
                if "error" in conflict:
                    conflict_messages.append(conflict["error"])
                else:
                    conflict_messages.append(
                        f"Collaborateur {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                        f"est déjà affecté à la mission {conflict['mission_id']} ({conflict['mission_objet']}) "
                        f"du {conflict['date_debut'].strftime('%Y-%m-%d %H:%M')} "
                        f"au {conflict['date_fin'].strftime('%Y-%m-%d %H:%M')}"
                    )
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Certains collaborateurs ne sont pas disponibles pour cette période",
                    "conflicts": conflict_messages
                }
            )
    
    # Traiter chaque action individuellement
    for collab_action in request.collaborateurs:
        try:
            # Trouver le collaborateur par matricule
            collaborateur_in_db = db.query(Collaborateur).filter(
                Collaborateur.matricule == collab_action.matricule
            ).first()
            
            if not collaborateur_in_db:
                errors.append(f"Collaborateur avec matricule {collab_action.matricule} non trouvé")
                continue
            
            # Vérifier si le collaborateur est déjà affecté
            existing_affectation = db.query(Affectation).filter(
                Affectation.mission_id == mission_id,
                Affectation.collaborateur_id == collaborateur_in_db.id
            ).first()
            
            if collab_action.action == 'add':
                if existing_affectation:
                    errors.append(f"Collaborateur {collab_action.matricule} déjà affecté à la mission")
                    continue
                
                # Créer une nouvelle affectation (la disponibilité a déjà été vérifiée)
                new_affectation = Affectation(
                    mission_id=mission_id,
                    collaborateur_id=collaborateur_in_db.id,
                    dejeuner=collab_action.dejeuner or 0,
                    dinner=collab_action.dinner or 0,
                    accouchement=collab_action.accouchement or 0,
                )
                db.add(new_affectation)
                results.append(new_affectation)
                
            elif collab_action.action == 'update':
                if not existing_affectation:
                    errors.append(f"Collaborateur {collab_action.matricule} n'est pas affecté à la mission")
                    continue
                
                # Mettre à jour les champs fournis
                if collab_action.dejeuner is not None:
                    existing_affectation.dejeuner = collab_action.dejeuner
                if collab_action.dinner is not None:
                    existing_affectation.dinner = collab_action.dinner
                if collab_action.accouchement is not None:
                    existing_affectation.accouchement = collab_action.accouchement
                
                results.append(existing_affectation)

            elif collab_action.action == 'remove':
                if not existing_affectation:
                    errors.append(f"Collaborateur {collab_action.matricule} n'est pas affecté à la mission")
                    continue
                db.delete(existing_affectation)
                results.append({"message": f"Collaborateur {collab_action.matricule} désaffecté."}) # Pas une AffectationResponse

        except Exception as e:
            errors.append(f"Erreur lors du traitement de {collab_action.matricule}: {e}")
    
    # Commit les changements
    if results: # Commit seulement s'il y a des changements à sauvegarder
        db.commit()
        for affectation in results:
            if hasattr(affectation, 'id'): # S'assurer que ce n'est pas un dictionnaire de message de suppression
                db.refresh(affectation)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Certaines actions ont échoué", "errors": errors}
        )

    # Filtrer les résultats pour ne retourner que des objets AffectationResponse si besoin
    final_responses = []
    for item in results:
        if isinstance(item, dict) and "message" in item:
            # Gérer les messages de suppression différemment ou les ignorer pour la response_model
            # Ici, on les ignore car la response_model est List[AffectationResponse]
            pass
        else:
            final_responses.append(AffectationResponse.model_validate(item))

    return final_responses
