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
    VehiculeResponse 
)

# Create an APIRouter instance for missions
router = APIRouter(
    prefix="/missions",
    tags=["Missions"],
    responses={404: {"description": "Not found"}},
)

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
    en utilisant leur matricule.
    """
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
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

# ... (rest of the endpoints remain the same)
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

@router.get("/{mission_id}/collaborators", response_model=List[AffectationResponse])
def get_mission_collaborators(mission_id: int, db: Session = Depends(get_db)):
    """
    Récupère tous les collaborateurs affectés à une mission spécifique.
    """
    mission_in_db = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission_in_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission avec l'ID {mission_id} non trouvée."
        )
    
    affectations = db.query(Affectation).filter(Affectation.mission_id == mission_id).all()
    return affectations

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