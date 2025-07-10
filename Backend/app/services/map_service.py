# app/services/map_service.py - Version corrigée
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
import math
from decimal import Decimal

from app.models.models import (
    Mission, Trajet, Anomalie, Directeur, Direction, 
    Vehicule, Affectation, Collaborateur, Utilisateur
)
from app.schemas.map_schemas import (
    MissionMapInfo, MissionMapFilter, MissionMapResponse,
    TrajetPoint, TrajetResponse, TrajetStatistics,
    AnomalieMapInfo, MissionAnalytics, MapBounds
)

class MapService:
    """Service pour la gestion de l'affichage cartographique des missions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_missions_for_map(
        self, 
        filters: MissionMapFilter,
        user_role: str,
        user_id: int,
        limit: int = 100
    ) -> MissionMapResponse:
        """Récupérer les missions pour l'affichage sur carte avec filtres"""
        
        print(f"DEBUG: Filtrage pour user_id={user_id}, role={user_role}")
        
        # Construction de la requête de base avec joins explicites
        query = self.db.query(Mission).join(
            Directeur, Mission.directeur_id == Directeur.id
        ).join(
            Direction, Directeur.direction_id == Direction.id
        )
        
        # Filtres de sécurité basés sur le rôle
        if user_role == "directeur":
            # Récupérer le directeur connecté par son utilisateur_id
            directeur = self.db.query(Directeur).filter(
                Directeur.utilisateur_id == user_id
            ).first()
            
            print(f"DEBUG: Directeur trouvé: {directeur}")
            
            if not directeur:
                print("DEBUG: Aucun profil directeur trouvé pour cet utilisateur")
                return MissionMapResponse(
                    missions=[],
                    bounds=None,
                    total_missions=0,
                    missions_actives=0,
                    missions_terminees=0,
                    missions_avec_anomalies=0
                )
            
            print(f"DEBUG: Filtrage par directeur_id={directeur.id}")
            # Filtrer SEULEMENT les missions de ce directeur
            query = query.filter(Mission.directeur_id == directeur.id)
        
        # Application des autres filtres APRÈS le filtrage de sécurité
        if filters.statut:
            query = query.filter(Mission.statut.in_(filters.statut))
        
        if filters.direction_id:
            query = query.filter(Direction.id == filters.direction_id)
        
        if filters.date_debut:
            query = query.filter(Mission.dateDebut >= filters.date_debut)
        
        if filters.date_fin:
            query = query.filter(Mission.dateFin <= filters.date_fin)
        
        if filters.moyen_transport:
            query = query.filter(Mission.moyenTransport == filters.moyen_transport)
        
        if filters.vehicule_id:
            query = query.filter(Mission.vehicule_id == filters.vehicule_id)
        
        if filters.avec_anomalies:
            # Sous-requête pour les missions avec anomalies
            missions_avec_anomalies = self.db.query(Anomalie.mission_id).distinct()
            query = query.filter(Mission.id.in_(missions_avec_anomalies))
        
        # Debug: afficher la requête SQL
        print(f"DEBUG: Requête SQL générée: {query}")
        
        # Limitation du nombre de résultats
        missions = query.limit(limit).all()
        
        print(f"DEBUG: Nombre de missions récupérées: {len(missions)}")
        for mission in missions:
            print(f"DEBUG: Mission {mission.id} - Directeur ID: {mission.directeur_id}")
        
        # Conversion en objets de réponse
        missions_info = []
        for mission in missions:
            mission_info = self._convert_mission_to_map_info(mission)
            missions_info.append(mission_info)
        
        # Calcul des statistiques
        total_missions = len(missions_info)
        missions_actives = len([m for m in missions_info if m.statut == "EN_COURS"])
        missions_terminees = len([m for m in missions_info if m.statut == "TERMINEE"])
        missions_avec_anomalies = len([m for m in missions_info if m.anomalies])
        
        # Calcul des limites géographiques
        bounds = self._calculate_map_bounds(missions_info)
        
        return MissionMapResponse(
            missions=missions_info,
            bounds=bounds,
            total_missions=total_missions,
            missions_actives=missions_actives,
            missions_terminees=missions_terminees,
            missions_avec_anomalies=missions_avec_anomalies
        )
    
    def get_live_mission_updates(self, mission_ids: List[int]) -> List[Dict[str, Any]]:
        """Obtenir les mises à jour en temps réel des missions"""
        updates = []
        
        for mission_id in mission_ids:
            # Récupérer le dernier point de trajet
            last_point = self.db.query(Trajet).filter(
                Trajet.mission_id == mission_id
            ).order_by(Trajet.timestamp.desc()).first()
            
            if last_point:
                mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
                updates.append({
                    'mission_id': mission_id,
                    'timestamp': last_point.timestamp,
                    'latitude': float(last_point.latitude),
                    'longitude': float(last_point.longitude),
                    'vitesse': float(last_point.vitesse),
                    'statut': mission.statut if mission else 'INCONNUE'
                })
        
        return updates
    
    def _convert_mission_to_map_info(self, mission: Mission) -> MissionMapInfo:
        """Convertir une mission en informations pour la carte"""
        
        # Récupération des trajets
        trajets = self.db.query(Trajet).filter(
            Trajet.mission_id == mission.id
        ).order_by(Trajet.timestamp).all()
        
        trajet_points = [
            TrajetPoint(
                id=trajet.id,
                timestamp=trajet.timestamp,
                latitude=float(trajet.latitude),
                longitude=float(trajet.longitude),
                vitesse=float(trajet.vitesse) if trajet.vitesse else 0.0
            )
            for trajet in trajets
        ]
        
        # Récupération des collaborateurs
        affectations = self.db.query(Affectation).join(Collaborateur).filter(
            Affectation.mission_id == mission.id
        ).all()
        
        collaborateurs = [
            {
                "id": aff.collaborateur_rel.id,
                "nom": aff.collaborateur_rel.nom,
                "matricule": aff.collaborateur_rel.matricule
            }
            for aff in affectations
        ]
        
        # Récupération des anomalies
        anomalies_db = self.db.query(Anomalie).filter(
            Anomalie.mission_id == mission.id
        ).all()
        
        anomalies = [
            {
                "id": anom.id,
                "type": anom.type,
                "description": anom.description,
                "dateDetection": anom.dateDetection
            }
            for anom in anomalies_db
        ]
        
        return MissionMapInfo(
            id=mission.id,
            objet=mission.objet,
            statut=mission.statut,
            dateDebut=mission.dateDebut,
            dateFin=mission.dateFin,
            moyenTransport=mission.moyenTransport,
            trajet_predefini=mission.trajet_predefini,
            directeur_nom=mission.directeur_rel.nom,
            directeur_prenom=mission.directeur_rel.prenom,
            direction_nom=mission.directeur_rel.direction_rel.nom,
            vehicule_immatriculation=mission.vehicule_rel.immatriculation if mission.vehicule_rel else None,
            vehicule_marque=mission.vehicule_rel.marque if mission.vehicule_rel else None,
            vehicule_modele=mission.vehicule_rel.modele if mission.vehicule_rel else None,
            collaborateurs=collaborateurs,
            trajet_points=trajet_points,
            anomalies=anomalies
        )
    
    def get_mission_trajet(self, mission_id: int) -> TrajetResponse:
        """Récupérer le trajet complet d'une mission"""
        
        trajets = self.db.query(Trajet).filter(
            Trajet.mission_id == mission_id
        ).order_by(Trajet.timestamp).all()
        
        if not trajets:
            return TrajetResponse(
                mission_id=mission_id,
                points=[],
                distance_totale=0.0,
                duree_totale=0,
                vitesse_moyenne=0.0
            )
        
        trajet_points = [
            TrajetPoint(
                id=trajet.id,
                timestamp=trajet.timestamp,
                latitude=float(trajet.latitude),
                longitude=float(trajet.longitude),
                vitesse=float(trajet.vitesse) if trajet.vitesse else 0.0
            )
            for trajet in trajets
        ]
        
        # Calcul des statistiques
        distance_totale = self._calculate_total_distance(trajet_points)
        duree_totale = self._calculate_total_duration(trajet_points)
        vitesse_moyenne = self._calculate_average_speed(trajet_points)
        
        return TrajetResponse(
            mission_id=mission_id,
            points=trajet_points,
            distance_totale=distance_totale,
            duree_totale=duree_totale,
            vitesse_moyenne=vitesse_moyenne
        )
    
    def get_mission_analytics(self, mission_id: int) -> MissionAnalytics:
        """Obtenir les analytics détaillées d'une mission"""
        
        trajet_response = self.get_mission_trajet(mission_id)
        
        # Calcul des statistiques détaillées
        statistics = self._calculate_detailed_statistics(trajet_response.points)
        
        # Récupération des anomalies
        anomalies_db = self.db.query(Anomalie).filter(
            Anomalie.mission_id == mission_id
        ).all()
        
        anomalies = [
            AnomalieMapInfo(
                id=anom.id,
                mission_id=anom.mission_id,
                type=anom.type,
                description=anom.description,
                dateDetection=anom.dateDetection
            )
            for anom in anomalies_db
        ]
        
        # Calcul de l'écart par rapport au trajet prévu
        ecart_trajet = self._calculate_route_deviation(mission_id, trajet_response.points)
        
        # Vérification du respect des horaires
        respect_horaires = self._check_schedule_compliance(mission_id, trajet_response.points)
        
        return MissionAnalytics(
            mission_id=mission_id,
            trajet_statistics=statistics,
            anomalies_detectees=anomalies,
            ecart_trajet_prevu=ecart_trajet,
            respect_horaires=respect_horaires,
            zones_visitees=self._get_visited_zones(trajet_response.points)
        )
    
    def _calculate_map_bounds(self, missions: List[MissionMapInfo]) -> Optional[MapBounds]:
        """Calculer les limites géographiques pour centrer la carte"""
        
        all_points = []
        for mission in missions:
            all_points.extend(mission.trajet_points)
        
        if not all_points:
            return None
        
        latitudes = [p.latitude for p in all_points]
        longitudes = [p.longitude for p in all_points]
        
        return MapBounds(
            nord=max(latitudes),
            sud=min(latitudes),
            est=max(longitudes),
            ouest=min(longitudes)
        )
    
    def _calculate_total_distance(self, points: List[TrajetPoint]) -> float:
        """Calculer la distance totale d'un trajet"""
        if len(points) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(points)):
            distance = self._haversine_distance(
                points[i-1].latitude, points[i-1].longitude,
                points[i].latitude, points[i].longitude
            )
            total_distance += distance
        
        return round(total_distance, 2)
    
    def _calculate_total_duration(self, points: List[TrajetPoint]) -> int:
        """Calculer la durée totale d'un trajet en minutes"""
        if len(points) < 2:
            return 0
        
        start_time = points[0].timestamp
        end_time = points[-1].timestamp
        duration = (end_time - start_time).total_seconds() / 60
        
        return int(duration)
    
    def _calculate_average_speed(self, points: List[TrajetPoint]) -> float:
        """Calculer la vitesse moyenne d'un trajet"""
        if not points:
            return 0.0
        
        total_speed = sum(p.vitesse for p in points)
        return round(total_speed / len(points), 2)
    
    def _calculate_detailed_statistics(self, points: List[TrajetPoint]) -> TrajetStatistics:
        """Calculer des statistiques détaillées du trajet"""
        
        if not points:
            return TrajetStatistics(
                distance_totale=0.0,
                duree_totale=0,
                vitesse_moyenne=0.0,
                vitesse_maximale=0.0,
                nombre_arrets=0,
                temps_arret_total=0
            )
        
        distance_totale = self._calculate_total_distance(points)
        duree_totale = self._calculate_total_duration(points)
        vitesse_moyenne = self._calculate_average_speed(points)
        vitesse_maximale = max(p.vitesse for p in points)
        
        # Calcul des arrêts (vitesse < 5 km/h pendant plus de 5 minutes)
        arrets = self._detect_stops(points)
        
        return TrajetStatistics(
            distance_totale=distance_totale,
            duree_totale=duree_totale,
            vitesse_moyenne=vitesse_moyenne,
            vitesse_maximale=vitesse_maximale,
            nombre_arrets=len(arrets),
            temps_arret_total=sum(arret['duree'] for arret in arrets)
        )
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer la distance haversine entre deux points GPS"""
        R = 6371  # Rayon de la Terre en km
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def _detect_stops(self, points: List[TrajetPoint]) -> List[Dict[str, Any]]:
        """Détecter les arrêts dans un trajet"""
        arrets = []
        arret_actuel = None
        
        for i, point in enumerate(points):
            if point.vitesse < 5:  # Considéré comme arrêté si vitesse < 5 km/h
                if arret_actuel is None:
                    arret_actuel = {
                        'debut': point.timestamp,
                        'latitude': point.latitude,
                        'longitude': point.longitude,
                        'index_debut': i
                    }
            else:
                if arret_actuel is not None:
                    duree = (point.timestamp - arret_actuel['debut']).total_seconds() / 60
                    if duree >= 5:  # Arrêt significatif si >= 5 minutes
                        arret_actuel['fin'] = points[i-1].timestamp
                        arret_actuel['duree'] = int(duree)
                        arrets.append(arret_actuel)
                    arret_actuel = None
        
        # Gérer le cas où le trajet se termine par un arrêt
        if arret_actuel is not None:
            duree = (points[-1].timestamp - arret_actuel['debut']).total_seconds() / 60
            if duree >= 5:
                arret_actuel['fin'] = points[-1].timestamp
                arret_actuel['duree'] = int(duree)
                arrets.append(arret_actuel)
        
        return arrets
    
    def _calculate_route_deviation(self, mission_id: int, points: List[TrajetPoint]) -> Optional[float]:
        """Calculer l'écart par rapport au trajet prévu"""
        return None
    
    def _check_schedule_compliance(self, mission_id: int, points: List[TrajetPoint]) -> bool:
        """Vérifier le respect des horaires"""
        mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission or not points:
            return True
        
        # Vérifier si la mission a commencé et fini dans les créneaux prévus
        actual_start = points[0].timestamp
        actual_end = points[-1].timestamp
        
        # Tolérance de 30 minutes
        tolerance = timedelta(minutes=30)
        
        start_on_time = abs((actual_start - mission.dateDebut).total_seconds()) <= tolerance.total_seconds()
        end_on_time = abs((actual_end - mission.dateFin).total_seconds()) <= tolerance.total_seconds()
        
        return start_on_time and end_on_time
    
    def _get_visited_zones(self, points: List[TrajetPoint]) -> List[str]:
        """Identifier les zones géographiques visitées"""
        return []