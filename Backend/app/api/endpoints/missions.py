from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import from the new relative paths within the 'app' package
from app.core.database import get_db
from app.models.models import Directeur, Vehicule, Mission, Collaborateur, Affectation
from app.schemas.schemas import MissionCreate, MissionResponse, AssignCollaboratorsRequest, AffectationResponse

# Create an APIRouter instance for missions
router = APIRouter(
    prefix="/missions", # All routes in this router will start with /missions
    tags=["Missions"],  # Tags for organizing in Swagger UI
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission(mission: MissionCreate, db: Session = Depends(get_db)):
    """
    Permet à un directeur de créer une nouvelle mission.
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

    # Create the mission
    db_mission = Mission(**mission.model_dump())
    db.add(db_mission)
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
            # You can choose to raise an HTTPException here or simply ignore
            # and log, depending on the desired behavior. Here, we ignore and log.
            continue # Move to the next collaborator

        # Check if the collaborator is already assigned to this mission
        existing_affectation = db.query(Affectation).filter(
            Affectation.mission_id == mission_id,
            Affectation.collaborateur_id == collaborateur_in_db.id
        ).first()

        if existing_affectation:
            print(f"Collaborateur {collab_assign.matricule} déjà affecté à la mission {mission_id}. Skipping.")
            assigned_affectations.append(existing_affectation) # Add the existing assignment
            continue

        # Create a new assignment
        new_affectation = Affectation(
            mission_id=mission_id,
            collaborateur_id=collaborateur_in_db.id,
            # Indemnities (dejeuner, dinner, accouchement, montantCalcule)
            # are left to their default values of 0,
            # as they are calculated only after the end of the mission.
        )
        db.add(new_affectation)
        assigned_affectations.append(new_affectation)

    db.commit() # Commit all new assignments
    for affectation in assigned_affectations:
        db.refresh(affectation) # Refresh to get generated IDs

    # Filter the assignments actually added for the return (those that did not exist before)
    newly_added_affectations_response = [
        AffectationResponse.model_validate(aff)
        for aff in assigned_affectations
    ]
    return newly_added_affectations_response