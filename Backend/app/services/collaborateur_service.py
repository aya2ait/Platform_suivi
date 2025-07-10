from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from datetime import datetime
from decimal import Decimal

from app.models.models import (
    Collaborateur, Mission, Affectation, Vehicule, Directeur, 
    Trajet, Anomalie, TypeCollaborateur, Direction, TauxIndemnite
)
from app.schemas.collaborateur_schemas import (
    MissionFilterRequest, MissionSearchRequest, MissionStatsResponse,
    CollaborateurProfileResponse, MissionCollaborateurResponse
)

class CollaborateurService:
    """Service pour gérer les missions des collaborateurs"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_collaborateur_by_matricule(self, matricule: str) -> Optional[Collaborateur]:
        """Récupérer un collaborateur par son matricule"""
        return self.db.query(Collaborateur).filter(
            Collaborateur.matricule == matricule
        ).first()
    
    def get_collaborateur_missions(
        self, 
        collaborateur_id: int, 
        filters: Optional[MissionFilterRequest] = None
    ) -> Tuple[List[MissionCollaborateurResponse], int]:
        """Récupérer les missions d'un collaborateur avec filtres et pagination"""
        
        # Requête de base avec jointures
        query = self.db.query(Mission).join(
            Affectation, Mission.id == Affectation.mission_id
        ).filter(
            Affectation.collaborateur_id == collaborateur_id
        ).options(
            joinedload(Mission.vehicule_rel),
            joinedload(Mission.directeur_rel),
            joinedload(Mission.affectations).joinedload(Affectation.collaborateur_rel),
            joinedload(Mission.trajets),
            joinedload(Mission.anomalies)
        )
        
        # Appliquer les filtres
        if filters:
            if filters.statut:
                query = query.filter(Mission.statut == filters.statut)
            
            if filters.date_debut:
                query = query.filter(Mission.dateDebut >= filters.date_debut)
            
            if filters.date_fin:
                query = query.filter(Mission.dateFin <= filters.date_fin)
        
        # Compter le total avant la pagination
        total = query.count()
        
        # Appliquer l'ordre avant la pagination (CORRECTION APPORTÉE ICI)
        query = query.order_by(desc(Mission.created_at))
        
        # Appliquer la pagination
        if filters:
            offset = (filters.page - 1) * filters.per_page
            query = query.offset(offset).limit(filters.per_page)
        
        missions = query.all()
        
        # Convertir en réponse avec l'affectation du collaborateur
        mission_responses = []
        for mission in missions:
            # Trouver l'affectation du collaborateur pour cette mission
            affectation = next(
                (aff for aff in mission.affectations if aff.collaborateur_id == collaborateur_id),
                None
            )
            
            mission_response = MissionCollaborateurResponse(
                id=mission.id,
                objet=mission.objet,
                dateDebut=mission.dateDebut,
                dateFin=mission.dateFin,
                moyenTransport=mission.moyenTransport,
                trajet_predefini=mission.trajet_predefini,
                statut=mission.statut,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
                vehicule=mission.vehicule_rel,
                directeur=mission.directeur_rel,
                affectation=affectation,
                trajets=mission.trajets,
                anomalies=mission.anomalies
            )
            mission_responses.append(mission_response)
        
        return mission_responses, total
    
    def get_mission_by_id(self, mission_id: int, collaborateur_id: int) -> Optional[MissionCollaborateurResponse]:
        """Récupérer une mission spécifique d'un collaborateur"""
        mission = self.db.query(Mission).join(
            Affectation, Mission.id == Affectation.mission_id
        ).filter(
            Mission.id == mission_id,
            Affectation.collaborateur_id == collaborateur_id
        ).options(
            joinedload(Mission.vehicule_rel),
            joinedload(Mission.directeur_rel),
            joinedload(Mission.affectations).joinedload(Affectation.collaborateur_rel),
            joinedload(Mission.trajets),
            joinedload(Mission.anomalies)
        ).first()
        
        if not mission:
            return None
        
        # Trouver l'affectation du collaborateur
        affectation = next(
            (aff for aff in mission.affectations if aff.collaborateur_id == collaborateur_id),
            None
        )
        
        return MissionCollaborateurResponse(
            id=mission.id,
            objet=mission.objet,
            dateDebut=mission.dateDebut,
            dateFin=mission.dateFin,
            moyenTransport=mission.moyenTransport,
            trajet_predefini=mission.trajet_predefini,
            statut=mission.statut,
            created_at=mission.created_at,
            updated_at=mission.updated_at,
            vehicule=mission.vehicule_rel,
            directeur=mission.directeur_rel,
            affectation=affectation,
            trajets=mission.trajets,
            anomalies=mission.anomalies
        )
    
    def search_collaborateur_missions(
        self, 
        collaborateur_id: int, 
        search_request: MissionSearchRequest
    ) -> Tuple[List[MissionCollaborateurResponse], int]:
        """Rechercher dans les missions d'un collaborateur"""
        
        query = self.db.query(Mission).join(
            Affectation, Mission.id == Affectation.mission_id
        ).filter(
            Affectation.collaborateur_id == collaborateur_id
        ).filter(
            or_(
                Mission.objet.ilike(f"%{search_request.query}%"),
                Mission.moyenTransport.ilike(f"%{search_request.query}%"),
                Mission.statut.ilike(f"%{search_request.query}%")
            )
        ).options(
            joinedload(Mission.vehicule_rel),
            joinedload(Mission.directeur_rel),
            joinedload(Mission.affectations).joinedload(Affectation.collaborateur_rel),
            joinedload(Mission.trajets),
            joinedload(Mission.anomalies)
        )
        
        total = query.count()
        
        # L'ordre est déjà avant la pagination ici
        offset = (search_request.page - 1) * search_request.per_page
        missions = query.order_by(desc(Mission.created_at)).offset(offset).limit(search_request.per_page).all()
        
        # Convertir en réponse
        mission_responses = []
        for mission in missions:
            affectation = next(
                (aff for aff in mission.affectations if aff.collaborateur_id == collaborateur_id),
                None
            )
            
            mission_response = MissionCollaborateurResponse(
                id=mission.id,
                objet=mission.objet,
                dateDebut=mission.dateDebut,
                dateFin=mission.dateFin,
                moyenTransport=mission.moyenTransport,
                trajet_predefini=mission.trajet_predefini,
                statut=mission.statut,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
                vehicule=mission.vehicule_rel,
                directeur=mission.directeur_rel,
                affectation=affectation,
                trajets=mission.trajets,
                anomalies=mission.anomalies
            )
            mission_responses.append(mission_response)
        
        return mission_responses, total
    
    def get_collaborateur_mission_stats(self, collaborateur_id: int) -> MissionStatsResponse:
        """Obtenir les statistiques des missions d'un collaborateur"""
        
        # Compter les missions par statut
        mission_counts = self.db.query(
            Mission.statut,
            func.count(Mission.id).label('count')
        ).join(
            Affectation, Mission.id == Affectation.mission_id
        ).filter(
            Affectation.collaborateur_id == collaborateur_id
        ).group_by(Mission.statut).all()
        
        # Calculer le total des indemnités
        total_indemnites = self.db.query(
            func.sum(Affectation.montantCalcule).label('total')
        ).filter(
            Affectation.collaborateur_id == collaborateur_id
        ).scalar() or Decimal('0.00')
        
        # Organiser les statistiques
        stats = {
            'total_missions': 0,
            'missions_en_cours': 0,
            'missions_terminees': 0,
            'missions_annulees': 0
        }
        
        for statut, count in mission_counts:
            stats['total_missions'] += count
            if statut.upper() in ['EN_COURS', 'CREEE']:
                stats['missions_en_cours'] += count
            elif statut.upper() in ['TERMINEE', 'VALIDEE']:
                stats['missions_terminees'] += count
            elif statut.upper() in ['ANNULEE']:
                stats['missions_annulees'] += count
        
        return MissionStatsResponse(
            total_missions=stats['total_missions'],
            missions_en_cours=stats['missions_en_cours'],
            missions_terminees=stats['missions_terminees'],
            missions_annulees=stats['missions_annulees'],
            total_indemnites=total_indemnites
        )
    
    def get_collaborateur_profile(self, collaborateur_id: int) -> Optional[CollaborateurProfileResponse]:
        """Obtenir le profil complet d'un collaborateur"""
        collaborateur = self.db.query(Collaborateur).filter(
            Collaborateur.id == collaborateur_id
        ).options(
            joinedload(Collaborateur.type_collaborateur_rel),
            joinedload(Collaborateur.direction_rel),
            joinedload(Collaborateur.taux_indemnite_rel),
            joinedload(Collaborateur.utilisateur_rel) # Charger la relation utilisateur
        ).first()
        
        if not collaborateur:
            return None
        
        return CollaborateurProfileResponse(
            id=collaborateur.id,
            nom=collaborateur.nom,
            matricule=collaborateur.matricule,
            disponible=collaborateur.disponible,
            type_collaborateur=collaborateur.type_collaborateur_rel.nom,
            direction=collaborateur.direction_rel.nom,
            # Vous pourriez vouloir ajouter l'ID de l'utilisateur ou son login ici si nécessaire pour la réponse
            # utilisateur_id=collaborateur.utilisateur_id
            # login_utilisateur=collaborateur.utilisateur_rel.login if collaborateur.utilisateur_rel else None
        )
    
    def get_collaborateur_recent_missions(
        self, 
        collaborateur_id: int, 
        limit: int = 5
    ) -> List[MissionCollaborateurResponse]:
        """Récupérer les missions récentes d'un collaborateur"""
        missions = self.db.query(Mission).join(
            Affectation, Mission.id == Affectation.mission_id
        ).filter(
            Affectation.collaborateur_id == collaborateur_id
        ).options(
            joinedload(Mission.vehicule_rel),
            joinedload(Mission.directeur_rel),
            joinedload(Mission.affectations),
            joinedload(Mission.trajets),
            joinedload(Mission.anomalies)
        ).order_by(desc(Mission.created_at)).limit(limit).all()
        
        # Convertir en réponse
        mission_responses = []
        for mission in missions:
            affectation = next(
                (aff for aff in mission.affectations if aff.collaborateur_id == collaborateur_id),
                None
            )
            
            mission_response = MissionCollaborateurResponse(
                id=mission.id,
                objet=mission.objet,
                dateDebut=mission.dateDebut,
                dateFin=mission.dateFin,
                moyenTransport=mission.moyenTransport,
                trajet_predefini=mission.trajet_predefini,
                statut=mission.statut,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
                vehicule=mission.vehicule_rel,
                directeur=mission.directeur_rel,
                affectation=affectation,
                trajets=mission.trajets,
                anomalies=mission.anomalies
            )
            mission_responses.append(mission_response)
        
        return mission_responses
    
    def get_collaborateur_missions_by_period(
        self, 
        collaborateur_id: int, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[MissionCollaborateurResponse]:
        """Récupérer les missions d'un collaborateur sur une période"""
        missions = self.db.query(Mission).join(
            Affectation, Mission.id == Affectation.mission_id
        ).filter(
            Affectation.collaborateur_id == collaborateur_id,
            Mission.dateDebut >= start_date,
            Mission.dateFin <= end_date
        ).options(
            joinedload(Mission.vehicule_rel),
            joinedload(Mission.directeur_rel),
            joinedload(Mission.affectations),
            joinedload(Mission.trajets),
            joinedload(Mission.anomalies)
        ).order_by(Mission.dateDebut).all()
        
        # Convertir en réponse
        mission_responses = []
        for mission in missions:
            affectation = next(
                (aff for aff in mission.affectations if aff.collaborateur_id == collaborateur_id),
                None
            )
            
            mission_response = MissionCollaborateurResponse(
                id=mission.id,
                objet=mission.objet,
                dateDebut=mission.dateDebut,
                dateFin=mission.dateFin,
                moyenTransport=mission.moyenTransport,
                trajet_predefini=mission.trajet_predefini,
                statut=mission.statut,
                created_at=mission.created_at,
                updated_at=mission.updated_at,
                vehicule=mission.vehicule_rel,
                directeur=mission.directeur_rel,
                affectation=affectation,
                trajets=mission.trajets,
                anomalies=mission.anomalies
            )
            mission_responses.append(mission_response)
        
        return mission_responses
    
    def get_mission_affectation(self, mission_id: int, collaborateur_id: int) -> Optional[Affectation]:
        """Récupérer l'affectation d'un collaborateur à une mission"""
        return self.db.query(Affectation).filter(
            Affectation.mission_id == mission_id,
            Affectation.collaborateur_id == collaborateur_id
        ).first()