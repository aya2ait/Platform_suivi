from typing import List, Optional, Union, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

# Import from the new relative paths within the 'app' package
from app.core.database import get_db
from app.models.models import Directeur, Vehicule, Mission, Collaborateur, Affectation
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

# Create an APIRouter instance for missions
router = APIRouter(
    prefix="/missions",
    tags=["Missions"],
    responses={404: {"description": "Not found"}},
)

# --- NOUVELLE FONCTIONNALITÉ: Modifier les collaborateurs affectés ---
@router.put("/{mission_id}/collaborators", response_model=List[AffectationResponse], status_code=status.HTTP_200_OK)
def update_mission_collaborators(
    mission_id: int,
    request: UpdateCollaboratorsRequest,
    db: Session = Depends(get_db)
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
@router.patch("/{mission_id}/collaborators", response_model=List[AffectationResponse], status_code=status.HTTP_200_OK)
def partially_update_mission_collaborators(
    mission_id: int,
    request: UpdateCollaboratorsRequest,
    db: Session = Depends(get_db)
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

# --- CORRECTED ORDER: Endpoint to get all vehicles moved to the top ---
@router.get("/vehicules", response_model=List[VehiculeResponse], tags=["Vehicules"])
def get_all_vehicules(db: Session = Depends(get_db)):
    """
    Récupère la liste de tous les véhicules disponibles.
    """
    vehicules = db.query(Vehicule).all()
    return vehicules

@router.post("/", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission(mission: MissionCreate, db: Session = Depends(get_db)):
    """
    Permet à un directeur de créer une nouvelle mission avec affectation optionnelle de collaborateurs.
    Vérifie la disponibilité du véhicule et des collaborateurs avant la création.
    """
    # Check if the director exists
    directeur_in_db = db.query(Directeur).filter(Directeur.id == mission.directeur_id).first()
    if not directeur_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directeur avec l'ID {mission.directeur_id} non trouvé."
        )

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

    # Create the mission (exclude collaborateurs from the mission data)
    mission_data = mission.model_dump(exclude={'collaborateurs'} if hasattr(mission, 'collaborateurs') else set())
    db_mission = Mission(**mission_data)
    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)
    
    # Handle collaborators assignment if provided
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
                    )
                    db.add(new_affectation)
            else:
                print(f"Collaborateur avec matricule {collab_data.matricule} non trouvé lors de la création.")
        
        db.commit()
        db.refresh(db_mission)
    
    return db_mission

@router.post("/{mission_id}/assign_collaborators/", response_model=List[AffectationResponse], status_code=status.HTTP_200_OK)
def assign_collaborators_to_mission(
    mission_id: int,
    request: AssignCollaboratorsRequest,
    db: Session = Depends(get_db)
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

@router.get("/", response_model=List[MissionResponse])
def get_all_missions(
    status: Optional[str] = None,
    directeur_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Récupère toutes les missions, avec la possibilité de filtrer par statut ou par ID de directeur.
    """
    query = db.query(Mission)

    if status:
        query = query.filter(Mission.statut == status)
    if directeur_id:
        query = query.filter(Mission.directeur_id == directeur_id)

    missions = query.all()
    return missions

@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission_by_id(mission_id: int, db: Session = Depends(get_db)):
    """
    Récupère une mission spécifique par son ID.
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )
    return mission

@router.put("/{mission_id}", response_model=MissionResponse)
def update_mission(mission_id: int, mission_update: MissionUpdate, db: Session = Depends(get_db)):
    """
    Met à jour les informations d'une mission existante.
    Vérifie la disponibilité du véhicule et des collaborateurs si les dates sont modifiées.
    """
    db_mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not db_mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )

    # Check if the director exists if director_id is being updated
    if mission_update.directeur_id and mission_update.directeur_id != db_mission.directeur_id:
        directeur_in_db = db.query(Directeur).filter(Directeur.id == mission_update.directeur_id).first()
        if not directeur_in_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Directeur avec l'ID {mission_update.directeur_id} non trouvé."
            )

    # Check if the vehicle exists if vehicule_id is being updated
    if mission_update.vehicule_id and mission_update.vehicule_id != db_mission.vehicule_id:
        vehicule_in_db = db.query(Vehicule).filter(Vehicule.id == mission_update.vehicule_id).first()
        if not vehicule_in_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Véhicule avec l'ID {mission_update.vehicule_id} non trouvé."
            )

    # Déterminer les nouvelles dates et véhicule pour la vérification
    new_date_debut = mission_update.dateDebut if mission_update.dateDebut else db_mission.dateDebut
    new_date_fin = mission_update.dateFin if mission_update.dateFin else db_mission.dateFin
    new_vehicule_id = mission_update.vehicule_id if mission_update.vehicule_id is not None else db_mission.vehicule_id
    
    # Vérifier si les dates ou le véhicule ont changé
    dates_changed = (mission_update.dateDebut and mission_update.dateDebut != db_mission.dateDebut) or \
                   (mission_update.dateFin and mission_update.dateFin != db_mission.dateFin)
    vehicle_changed = mission_update.vehicule_id is not None and mission_update.vehicule_id != db_mission.vehicule_id
    
    # Si les dates ou le véhicule ont changé, vérifier la disponibilité
    if dates_changed or vehicle_changed:
        # Récupérer les collaborateurs actuellement affectés
        current_affectations = db.query(Affectation).filter(Affectation.mission_id == mission_id).all()
        current_collaborateurs = []
        if current_affectations:
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
    
    # Update only the fields that are provided (exclude_unset=True)
    update_data = mission_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_mission, key, value)
    
    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)
    return db_mission

@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mission(mission_id: int, db: Session = Depends(get_db)):
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

@router.get("/{mission_id}/collaborators", response_model=List[DetailedAffectationResponse])
def get_mission_collaborators(mission_id: int, db: Session = Depends(get_db)):
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

@router.delete("/{mission_id}/unassign_collaborator/{collaborator_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_collaborator_from_mission(mission_id: int, collaborator_id: int, db: Session = Depends(get_db)):
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

@router.patch("/{mission_id}/manage-collaborators", response_model=List[AffectationResponse], status_code=status.HTTP_200_OK)
def manage_mission_collaborators(
    mission_id: int,
    request: ManageCollaboratorsRequest,
    db: Session = Depends(get_db)
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
                
                # Mettre à jour l'affectation existante
                existing_affectation.dejeuner = collab_action.dejeuner or existing_affectation.dejeuner
                existing_affectation.dinner = collab_action.dinner or existing_affectation.dinner
                existing_affectation.accouchement = collab_action.accouchement or existing_affectation.accouchement
                results.append(existing_affectation)
                
            elif collab_action.action == 'remove':
                if not existing_affectation:
                    errors.append(f"Collaborateur {collab_action.matricule} n'est pas affecté à la mission")
                    continue
                
                # Supprimer l'affectation
                db.delete(existing_affectation)
                # Note: On n'ajoute pas à results car l'affectation sera supprimée
                
        except Exception as e:
            errors.append(f"Erreur lors du traitement de {collab_action.matricule}: {str(e)}")
    
    # Valider les changements
    db.commit()
    
    # Rafraîchir les objets modifiés/ajoutés
    for affectation in results:
        if affectation in db:  # Vérifier que l'objet n'a pas été supprimé
            db.refresh(affectation)
    
    # Filtrer les affectations supprimées
    active_results = [aff for aff in results if aff in db]
    
    # Optionnel: log des erreurs
    if errors:
        print(f"Erreurs lors de la gestion des collaborateurs: {errors}")
    
    return [AffectationResponse.model_validate(aff) for aff in active_results]