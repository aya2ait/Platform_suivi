from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.models import Mission, Affectation, Collaborateur, Vehicule

def check_date_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    # Si un datetime est aware et l’autre ne l’est pas, les aligner
    if start1.tzinfo and not start2.tzinfo:
        start2 = start2.replace(tzinfo=start1.tzinfo)
        end2 = end2.replace(tzinfo=start1.tzinfo)
    elif start2.tzinfo and not start1.tzinfo:
        start1 = start1.replace(tzinfo=start2.tzinfo)
        end1 = end1.replace(tzinfo=start2.tzinfo)
    
    return not (end1 <= start2 or start1 >= end2)


def check_vehicle_availability(
    db: Session, 
    vehicule_id: int, 
    date_debut: datetime, 
    date_fin: datetime, 
    exclude_mission_id: Optional[int] = None
) -> Tuple[bool, List[dict]]:
    """
    Vérifie si un véhicule est disponible pour une période donnée.
    
    Args:
        db: Session de base de données
        vehicule_id: ID du véhicule à vérifier
        date_debut: Date de début de la mission
        date_fin: Date de fin de la mission
        exclude_mission_id: ID de mission à exclure (pour les mises à jour)
    
    Returns:
        Tuple[bool, List[dict]]: (disponible, liste des missions en conflit)
    """
    if not vehicule_id:
        return True, []
    
    # Vérifier que le véhicule existe
    vehicule = db.query(Vehicule).filter(Vehicule.id == vehicule_id).first()
    if not vehicule:
        return False, [{"error": f"Véhicule avec l'ID {vehicule_id} non trouvé"}]
    
    # Requête pour trouver les missions en conflit
    query = db.query(Mission).filter(
        Mission.vehicule_id == vehicule_id,
        Mission.statut != "ANNULEE"  # Exclure les missions annulées
    )
    
    # Exclure la mission actuelle si on fait une mise à jour
    if exclude_mission_id:
        query = query.filter(Mission.id != exclude_mission_id)
    
    existing_missions = query.all()
    
    conflicting_missions = []
    for mission in existing_missions:
        if check_date_overlap(date_debut, date_fin, mission.dateDebut, mission.dateFin):
            conflicting_missions.append({
                "mission_id": mission.id,
                "objet": mission.objet,
                "date_debut": mission.dateDebut,
                "date_fin": mission.dateFin,
                "vehicule_immatriculation": vehicule.immatriculation
            })
    
    is_available = len(conflicting_missions) == 0
    return is_available, conflicting_missions


def check_collaborators_availability(
    db: Session, 
    collaborateur_matricules: List[str], 
    date_debut: datetime, 
    date_fin: datetime, 
    exclude_mission_id: Optional[int] = None
) -> Tuple[bool, List[dict]]:
    """
    Vérifie si les collaborateurs sont disponibles pour une période donnée.
    
    Args:
        db: Session de base de données
        collaborateur_matricules: Liste des matricules des collaborateurs
        date_debut: Date de début de la mission
        date_fin: Date de fin de la mission
        exclude_mission_id: ID de mission à exclure (pour les mises à jour)
    
    Returns:
        Tuple[bool, List[dict]]: (tous disponibles, liste des conflits)
    """
    if not collaborateur_matricules:
        return True, []
    
    # Récupérer les IDs des collaborateurs
    collaborateurs = db.query(Collaborateur).filter(
        Collaborateur.matricule.in_(collaborateur_matricules)
    ).all()
    
    collaborateur_ids = [c.id for c in collaborateurs]
    collaborateur_map = {c.id: c for c in collaborateurs}
    
    # Vérifier que tous les collaborateurs existent
    if len(collaborateurs) != len(collaborateur_matricules):
        found_matricules = [c.matricule for c in collaborateurs]
        missing_matricules = [m for m in collaborateur_matricules if m not in found_matricules]
        return False, [{"error": f"Collaborateurs non trouvés: {missing_matricules}"}]
    
    # Requête pour trouver les affectations en conflit
    query = db.query(Affectation, Mission).join(
        Mission, Affectation.mission_id == Mission.id
    ).filter(
        Affectation.collaborateur_id.in_(collaborateur_ids),
        Mission.statut != "ANNULEE"  # Exclure les missions annulées
    )
    
    # Exclure la mission actuelle si on fait une mise à jour
    if exclude_mission_id:
        query = query.filter(Mission.id != exclude_mission_id)
    
    existing_affectations = query.all()
    
    conflicting_collaborators = []
    for affectation, mission in existing_affectations:
        if check_date_overlap(date_debut, date_fin, mission.dateDebut, mission.dateFin):
            collaborateur = collaborateur_map[affectation.collaborateur_id]
            conflicting_collaborators.append({
                "collaborateur_matricule": collaborateur.matricule,
                "collaborateur_nom": collaborateur.nom,
                "mission_id": mission.id,
                "mission_objet": mission.objet,
                "date_debut": mission.dateDebut,
                "date_fin": mission.dateFin
            })
    
    is_available = len(conflicting_collaborators) == 0
    return is_available, conflicting_collaborators

def check_mission_availability(
    db: Session,
    date_debut: datetime,
    date_fin: datetime,
    vehicule_id: Optional[int] = None,
    collaborateur_matricules: Optional[List[str]] = None,
    exclude_mission_id: Optional[int] = None
) -> Tuple[bool, dict]:
    """
    Vérifie la disponibilité complète pour une mission (véhicule + collaborateurs).
    
    Args:
        db: Session de base de données
        date_debut: Date de début de la mission
        date_fin: Date de fin de la mission
        vehicule_id: ID du véhicule (optionnel)
        collaborateur_matricules: Liste des matricules des collaborateurs (optionnel)
        exclude_mission_id: ID de mission à exclure (pour les mises à jour)
    
    Returns:
        Tuple[bool, dict]: (disponible, détails des conflits)
    """
    conflicts = {
        "vehicle_conflicts": [],
        "collaborator_conflicts": []
    }
    
    # Vérifier la disponibilité du véhicule
    vehicle_available = True
    if vehicule_id:
        vehicle_available, vehicle_conflicts = check_vehicle_availability(
            db, vehicule_id, date_debut, date_fin, exclude_mission_id
        )
        conflicts["vehicle_conflicts"] = vehicle_conflicts
    
    # Vérifier la disponibilité des collaborateurs
    collaborators_available = True
    if collaborateur_matricules:
        collaborators_available, collaborator_conflicts = check_collaborators_availability(
            db, collaborateur_matricules, date_debut, date_fin, exclude_mission_id
        )
        conflicts["collaborator_conflicts"] = collaborator_conflicts
    
    is_available = vehicle_available and collaborators_available
    
    return is_available, conflicts