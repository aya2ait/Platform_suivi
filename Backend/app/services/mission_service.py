from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.models import Mission, Vehicule, Collaborateur, Affectation, Directeur
from app.schemas.schemas import (
    MissionCreate, MissionUpdate, AssignCollaboratorsRequest,
    UpdateCollaboratorsRequest, ManageCollaboratorsRequest,
    CollaboratorAssignmentInput
)
from app.services.availability_check import check_mission_availability # Assuming this is well-defined

class MissionService:
    def __init__(self, db: Session):
        self.db = db

    def _get_mission(self, mission_id: int) -> Mission:
        mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission with ID {mission_id} not found."
            )
        return mission

    def _get_directeur(self, directeur_id: int) -> Directeur:
        directeur = self.db.query(Directeur).filter(Directeur.id == directeur_id).first()
        if not directeur:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Directeur with ID {directeur_id} not found."
            )
        return directeur

    def _get_vehicule(self, vehicule_id: int) -> Vehicule:
        vehicule = self.db.query(Vehicule).filter(Vehicule.id == vehicule_id).first()
        if not vehicule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle with ID {vehicule_id} not found."
            )
        return vehicule

    def _handle_availability_conflicts(self, is_available: bool, conflicts: Dict[str, Any]):
        if not is_available:
            conflict_details = []
            for conflict_type in ["vehicle_conflicts", "collaborator_conflicts"]:
                for conflict in conflicts.get(conflict_type, []):
                    if "error" in conflict:
                        conflict_details.append(conflict["error"])
                    elif conflict_type == "vehicle_conflicts":
                        conflict_details.append(
                            f"Vehicle {conflict['vehicule_immatriculation']} already assigned to mission "
                            f"{conflict['mission_id']} from {conflict['date_debut']} to {conflict['date_fin']}"
                        )
                    elif conflict_type == "collaborator_conflicts":
                        conflict_details.append(
                            f"Collaborator {conflict['collaborateur_matricule']} ({conflict['collaborateur_nom']}) "
                            f"already assigned to mission {conflict['mission_id']} from {conflict['date_debut']} to {conflict['date_fin']}"
                        )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Resources not available for this period",
                    "conflicts": conflict_details
                }
            )

    def create_mission(self, mission_data: MissionCreate) -> Mission:
        self._get_directeur(mission_data.directeur_id)
        if mission_data.vehicule_id:
            self._get_vehicule(mission_data.vehicule_id)

        collaborator_matricules = [c.matricule for c in mission_data.collaborateurs] if mission_data.collaborateurs else []

        is_available, conflicts = check_mission_availability(
            db=self.db,
            date_debut=mission_data.dateDebut,
            date_fin=mission_data.dateFin,
            vehicule_id=mission_data.vehicule_id,
            collaborateur_matricules=collaborator_matricules
        )
        self._handle_availability_conflicts(is_available, conflicts)

        db_mission = Mission(**mission_data.model_dump(exclude={'collaborateurs'}))
        self.db.add(db_mission)
        self.db.commit()
        self.db.refresh(db_mission)

        if mission_data.collaborateurs:
            for collab_data in mission_data.collaborateurs:
                collaborateur_in_db = self.db.query(Collaborateur).filter(Collaborateur.matricule == collab_data.matricule).first()
                if collaborateur_in_db:
                    new_affectation = Affectation(
                        mission_id=db_mission.id,
                        collaborateur_id=collaborateur_in_db.id,
                        dejeuner=collab_data.dejeuner if hasattr(collab_data, 'dejeuner') else 0,
                        dinner=collab_data.dinner if hasattr(collab_data, 'dinner') else 0,
                        accouchement=collab_data.accouchement if hasattr(collab_data, 'accouchement') else 0,
                    )
                    self.db.add(new_affectation)
                else:
                    print(f"Collaborator with matricule {collab_data.matricule} not found during mission creation.")
            self.db.commit()
            self.db.refresh(db_mission) # Refresh again to include new affectations if needed by MissionResponse

        return db_mission

    def get_missions(self, status_filter: Optional[str] = None, directeur_id: Optional[int] = None) -> List[Mission]:
        query = self.db.query(Mission)
        if status_filter:
            query = query.filter(Mission.statut == status_filter)
        if directeur_id:
            query = query.filter(Mission.directeur_id == directeur_id)
        return query.all()

    def get_mission_by_id(self, mission_id: int) -> Mission:
        return self._get_mission(mission_id)

    def update_mission(self, mission_id: int, mission_update: MissionUpdate) -> Mission:
        db_mission = self._get_mission(mission_id)

        if mission_update.directeur_id and mission_update.directeur_id != db_mission.directeur_id:
            self._get_directeur(mission_update.directeur_id)
        if mission_update.vehicule_id is not None and mission_update.vehicule_id != db_mission.vehicule_id:
            # Allow vehicule_id to be set to None (unassigned)
            if mission_update.vehicule_id is not None:
                self._get_vehicule(mission_update.vehicule_id)

        new_date_debut = mission_update.dateDebut if mission_update.dateDebut else db_mission.dateDebut
        new_date_fin = mission_update.dateFin if mission_update.dateFin else db_mission.dateFin
        new_vehicule_id = mission_update.vehicule_id if mission_update.vehicule_id is not None else db_mission.vehicule_id

        dates_changed = (mission_update.dateDebut and mission_update.dateDebut != db_mission.dateDebut) or \
                       (mission_update.dateFin and mission_update.dateFin != db_mission.dateFin)
        vehicle_changed = mission_update.vehicule_id is not None and mission_update.vehicule_id != db_mission.vehicule_id

        if dates_changed or vehicle_changed:
            current_affectations = self.db.query(Affectation).filter(Affectation.mission_id == mission_id).all()
            current_collaborator_matricules = []
            if current_affectations:
                collaborator_ids = [aff.collaborateur_id for aff in current_affectations]
                collaborators = self.db.query(Collaborateur).filter(Collaborateur.id.in_(collaborator_ids)).all()
                current_collaborator_matricules = [c.matricule for c in collaborators]

            is_available, conflicts = check_mission_availability(
                db=self.db,
                date_debut=new_date_debut,
                date_fin=new_date_fin,
                vehicule_id=new_vehicule_id,
                collaborateur_matricules=current_collaborator_matricules,
                exclude_mission_id=mission_id
            )
            self._handle_availability_conflicts(is_available, conflicts)

        update_data = mission_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_mission, key, value)

        self.db.add(db_mission)
        self.db.commit()
        self.db.refresh(db_mission)
        return db_mission

    def delete_mission(self, mission_id: int):
        db_mission = self._get_mission(mission_id)
        self.db.delete(db_mission)
        self.db.commit()

    def update_mission_collaborators(self, mission_id: int, request: UpdateCollaboratorsRequest) -> List[Affectation]:
        mission_in_db = self._get_mission(mission_id)

        collaborator_matricules = [collab.matricule for collab in request.collaborateurs]
        is_available, conflicts = check_mission_availability(
            db=self.db,
            date_debut=mission_in_db.dateDebut,
            date_fin=mission_in_db.dateFin,
            collaborateur_matricules=collaborator_matricules,
            exclude_mission_id=mission_id
        )
        self._handle_availability_conflicts(is_available, conflicts)

        self.db.query(Affectation).filter(Affectation.mission_id == mission_id).delete()
        self.db.commit()

        new_affectations = []
        for collab_data in request.collaborateurs:
            collaborateur_in_db = self.db.query(Collaborateur).filter(Collaborateur.matricule == collab_data.matricule).first()
            if not collaborateur_in_db:
                print(f"Collaborator with matricule {collab_data.matricule} not found. Skipping.")
                continue
            new_affectation = Affectation(
                mission_id=mission_id,
                collaborateur_id=collaborateur_in_db.id,
                dejeuner=collab_data.dejeuner if hasattr(collab_data, 'dejeuner') else 0,
                dinner=collab_data.dinner if hasattr(collab_data, 'dinner') else 0,
                accouchement=collab_data.accouchement if hasattr(collab_data, 'accouchement') else 0,
            )
            self.db.add(new_affectation)
            new_affectations.append(new_affectation)

        self.db.commit()
        for affectation in new_affectations:
            self.db.refresh(affectation)
        return new_affectations

    def partially_update_mission_collaborators(self, mission_id: int, request: UpdateCollaboratorsRequest) -> List[Affectation]:
        mission_in_db = self._get_mission(mission_id)

        new_collaborator_matricules = []
        for collab_data in request.collaborateurs:
            collaborateur_in_db = self.db.query(Collaborateur).filter(Collaborateur.matricule == collab_data.matricule).first()
            if collaborateur_in_db:
                existing_affectation = self.db.query(Affectation).filter(
                    Affectation.mission_id == mission_id,
                    Affectation.collaborateur_id == collaborateur_in_db.id
                ).first()
                if not existing_affectation:
                    new_collaborator_matricules.append(collab_data.matricule)

        if new_collaborator_matricules:
            is_available, conflicts = check_mission_availability(
                db=self.db,
                date_debut=mission_in_db.dateDebut,
                date_fin=mission_in_db.dateFin,
                collaborateur_matricules=new_collaborator_matricules,
                exclude_mission_id=mission_id
            )
            if not is_available: # Only raise if new collaborators conflict
                self._handle_availability_conflicts(is_available, conflicts)

        updated_affectations = []
        for collab_data in request.collaborateurs:
            collaborateur_in_db = self.db.query(Collaborateur).filter(Collaborateur.matricule == collab_data.matricule).first()
            if not collaborateur_in_db:
                print(f"Collaborator with matricule {collab_data.matricule} not found. Skipping.")
                continue

            existing_affectation = self.db.query(Affectation).filter(
                Affectation.mission_id == mission_id,
                Affectation.collaborateur_id == collaborateur_in_db.id
            ).first()

            if existing_affectation:
                if hasattr(collab_data, 'dejeuner'): existing_affectation.dejeuner = collab_data.dejeuner
                if hasattr(collab_data, 'dinner'): existing_affectation.dinner = collab_data.dinner
                if hasattr(collab_data, 'accouchement'): existing_affectation.accouchement = collab_data.accouchement
                updated_affectations.append(existing_affectation)
            else:
                new_affectation = Affectation(
                    mission_id=mission_id,
                    collaborateur_id=collaborateur_in_db.id,
                    dejeuner=collab_data.dejeuner if hasattr(collab_data, 'dejeuner') else 0,
                    dinner=collab_data.dinner if hasattr(collab_data, 'dinner') else 0,
                    accouchement=collab_data.accouchement if hasattr(collab_data, 'accouchement') else 0,
                )
                self.db.add(new_affectation)
                updated_affectations.append(new_affectation)

        self.db.commit()
        for affectation in updated_affectations:
            self.db.refresh(affectation)
        return updated_affectations


    def assign_collaborators_to_mission(self, mission_id: int, request: AssignCollaboratorsRequest) -> List[Affectation]:
        mission_in_db = self._get_mission(mission_id)

        collaborator_matricules = [collab.matricule for collab in request.collaborateurs]
        is_available, conflicts = check_mission_availability(
            db=self.db,
            date_debut=mission_in_db.dateDebut,
            date_fin=mission_in_db.dateFin,
            collaborateur_matricules=collaborator_matricules,
            exclude_mission_id=mission_id
        )
        self._handle_availability_conflicts(is_available, conflicts)

        assigned_affectations = []
        for collab_assign in request.collaborateurs:
            collaborateur_in_db = self.db.query(Collaborateur).filter(Collaborateur.matricule == collab_assign.matricule).first()
            if not collaborateur_in_db:
                print(f"Collaborator with matricule {collab_assign.matricule} not found. Skipping.")
                continue

            existing_affectation = self.db.query(Affectation).filter(
                Affectation.mission_id == mission_id,
                Affectation.collaborateur_id == collaborateur_in_db.id
            ).first()

            if existing_affectation:
                print(f"Collaborator {collab_assign.matricule} already assigned to mission {mission_id}. Skipping.")
                assigned_affectations.append(existing_affectation)
                continue

            new_affectation = Affectation(
                mission_id=mission_id,
                collaborateur_id=collaborateur_in_db.id,
            )
            self.db.add(new_affectation)
            assigned_affectations.append(new_affectation)

        self.db.commit()
        for affectation in assigned_affectations:
            self.db.refresh(affectation)
        return assigned_affectations

    def get_mission_collaborators(self, mission_id: int) -> List[Dict[str, Any]]:
        self._get_mission(mission_id)
        
        affectations_with_collaborators = self.db.query(
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
        
        return [row._asdict() for row in affectations_with_collaborators] # Convert Row to dict

    def unassign_collaborator_from_mission(self, mission_id: int, collaborator_id: int):
        affectation_to_delete = self.db.query(Affectation).filter(
            Affectation.mission_id == mission_id,
            Affectation.collaborateur_id == collaborator_id
        ).first()

        if not affectation_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Affectation not found for mission {mission_id} and collaborator {collaborator_id}."
            )
        self.db.delete(affectation_to_delete)
        self.db.commit()
        return {"message": "Collaborator unassigned from mission successfully."}

    def manage_mission_collaborators(self, mission_id: int, request: ManageCollaboratorsRequest) -> List[Affectation]:
        mission_in_db = self._get_mission(mission_id)
        
        # Collect all collaborators involved in add/update operations for availability check
        collaborators_to_check_availability = []
        for action_data in request.actions:
            if action_data.action in ["add", "update"] and action_data.collaborateur:
                collaborators_to_check_availability.append(action_data.collaborateur.matricule)

        if collaborators_to_check_availability:
            is_available, conflicts = check_mission_availability(
                db=self.db,
                date_debut=mission_in_db.dateDebut,
                date_fin=mission_in_db.dateFin,
                collaborateur_matricules=collaborators_to_check_availability,
                exclude_mission_id=mission_id
            )
            self._handle_availability_conflicts(is_available, conflicts)

        processed_affectations = []
        for action_data in request.actions:
            action = action_data.action
            collab_data = action_data.collaborateur

            if collab_data: # Should always be present for add/update, sometimes for remove (by matricule)
                collaborateur_in_db = self.db.query(Collaborateur).filter(Collaborateur.matricule == collab_data.matricule).first()
                if not collaborateur_in_db:
                    print(f"Collaborator with matricule {collab_data.matricule} not found for action '{action}'. Skipping.")
                    continue

                existing_affectation = self.db.query(Affectation).filter(
                    Affectation.mission_id == mission_id,
                    Affectation.collaborateur_id == collaborateur_in_db.id
                ).first()

                if action == "add":
                    if existing_affectation:
                        print(f"Collaborator {collab_data.matricule} already assigned. Skipping add.")
                        processed_affectations.append(existing_affectation) # Include it in the response
                    else:
                        new_affectation = Affectation(
                            mission_id=mission_id,
                            collaborateur_id=collaborateur_in_db.id,
                            dejeuner=collab_data.dejeuner if hasattr(collab_data, 'dejeuner') else 0,
                            dinner=collab_data.dinner if hasattr(collab_data, 'dinner') else 0,
                            accouchement=collab_data.accouchement if hasattr(collab_data, 'accouchement') else 0,
                        )
                        self.db.add(new_affectation)
                        processed_affectations.append(new_affectation)
                elif action == "update":
                    if existing_affectation:
                        if hasattr(collab_data, 'dejeuner'): existing_affectation.dejeuner = collab_data.dejeuner
                        if hasattr(collab_data, 'dinner'): existing_affectation.dinner = collab_data.dinner
                        if hasattr(collab_data, 'accouchement'): existing_affectation.accouchement = collab_data.accouchement
                        processed_affectations.append(existing_affectation)
                    else:
                        print(f"Collaborator {collab_data.matricule} not assigned, cannot update. Skipping.")
                elif action == "remove":
                    if existing_affectation:
                        self.db.delete(existing_affectation)
                    else:
                        print(f"Collaborator {collab_data.matricule} not assigned, cannot remove. Skipping.")
            elif action == "remove" and action_data.collaborator_id: # Allow removal by ID directly
                affectation_to_delete = self.db.query(Affectation).filter(
                    Affectation.mission_id == mission_id,
                    Affectation.collaborateur_id == action_data.collaborator_id
                ).first()
                if affectation_to_delete:
                    self.db.delete(affectation_to_delete)
                else:
                    print(f"Affectation with mission_id {mission_id} and collaborator_id {action_data.collaborator_id} not found. Skipping remove.")

        self.db.commit()
        for affectation in processed_affectations:
            self.db.refresh(affectation)
        
        # After commits, retrieve the *current* list of affectations for the mission
        return self.db.query(Affectation).filter(Affectation.mission_id == mission_id).all()

# Dependency to inject MissionService
def get_mission_service(db: Session = Depends(get_db)) -> MissionService:
    return MissionService(db)