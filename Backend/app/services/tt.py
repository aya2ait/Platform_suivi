# services/tt.py 
import random
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from math import radians, cos, sin, asin, sqrt, atan2, degrees
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.schemas.anomaly_schema import AnomalyType, AnomalyConfig, AnomalyResponse
from app.schemas.simulator_schema import TrajectPoint, Mission
from app.models.models import Mission as MissionModel, Anomalie as AnomalieModel, Trajet as TrajetModel

logger = logging.getLogger(__name__)

class AnomalyGeneratorService:
    """Service pour générer des anomalies GPS simulées"""
    
    def __init__(self, db: Session):
        self.db = db
        self.MOROCCO_BOUNDS = {
            'min_lat': 21.0, 'max_lat': 36.0,
            'min_lon': -17.0, 'max_lon': -1.0
        }
        
        # Zones interdites (exemples)
        self.FORBIDDEN_ZONES = [
            {"name": "Zone Militaire", "lat": 33.5731, "lon": -7.5898, "radius": 5},
            {"name": "Zone Privée", "lat": 34.0209, "lon": -6.8417, "radius": 3},
        ]
        
        # Configuration par défaut des anomalies
        self.DEFAULT_ANOMALY_CONFIG = [
            AnomalyConfig(
                type=AnomalyType.RETOUR_PREMATURE,
                probability=0.15,
                severity="HIGH",
                parameters={"min_time_before_end": 2, "max_time_before_end": 6}
            ),
            AnomalyConfig(
                type=AnomalyType.TRAJET_DIVERGENT,
                probability=0.20,
                severity="MEDIUM",
                parameters={"max_deviation_km": 50, "min_deviation_km": 10}
            ),
            AnomalyConfig(
                type=AnomalyType.ARRET_PROLONGE,
                probability=0.25,
                severity="LOW",
                parameters={"min_stop_duration": 30, "max_stop_duration": 120}
            ),
            AnomalyConfig(
                type=AnomalyType.VITESSE_EXCESSIVE,
                probability=0.10,
                severity="HIGH",
                parameters={"max_speed": 150, "min_speed": 130}
            ),
            AnomalyConfig(
                type=AnomalyType.TRAJET_PERSONNEL,
                probability=0.12,
                severity="HIGH",
                parameters={"personal_locations": ["Centre Commercial", "Domicile", "Restaurant"]}
            )
        ]
    
    def get_mission_by_id(self, mission_id: int) -> Optional[MissionModel]:
        """Récupérer une mission par son ID"""
        return self.db.query(MissionModel).filter(MissionModel.id == mission_id).first()
    
    def get_mission_trajectory_points(self, mission_id: int) -> List[TrajetModel]:
        """Récupérer les points de trajectoire d'une mission"""
        return self.db.query(TrajetModel).filter(
            TrajetModel.mission_id == mission_id
        ).order_by(TrajetModel.timestamp).all()
    
    def convert_trajet_to_trajectory_point(self, trajet: TrajetModel) -> TrajectPoint:
        """Convertir un modèle Trajet en TrajectPoint"""
        return TrajectPoint(
            latitude=float(trajet.latitude),
            longitude=float(trajet.longitude),
            timestamp=trajet.timestamp,
            vitesse=float(trajet.vitesse),
            mission_id=trajet.mission_id
        )
    
    def generate_trajectory_points(self, mission: MissionModel) -> List[TrajectPoint]:
        """Générer des points de trajectoire pour une mission"""
        # Récupérer les points existants ou générer de nouveaux
        existing_points = self.get_mission_trajectory_points(mission.id)
        
        if existing_points:
            return [self.convert_trajet_to_trajectory_point(point) for point in existing_points]
        
        # Générer des points simulés (logique simplifiée)
        points = []
        duration = (mission.dateFin - mission.dateDebut).total_seconds()
        num_points = max(10, int(duration / 300))  # Point toutes les 5 minutes
        
        # Points de départ et d'arrivée simulés (Maroc)
        start_lat = random.uniform(31.0, 34.0)
        start_lon = random.uniform(-8.0, -5.0)
        end_lat = random.uniform(31.0, 34.0)
        end_lon = random.uniform(-8.0, -5.0)
        
        for i in range(num_points):
            ratio = i / max(1, num_points - 1)
            
            # Interpolation linéaire avec un peu de variabilité
            lat = start_lat + (end_lat - start_lat) * ratio + random.uniform(-0.01, 0.01)
            lon = start_lon + (end_lon - start_lon) * ratio + random.uniform(-0.01, 0.01)
            
            timestamp = mission.dateDebut + timedelta(seconds=duration * ratio)
            speed = random.uniform(30, 90)
            
            point = TrajectPoint(
                latitude=lat,
                longitude=lon,
                timestamp=timestamp,
                vitesse=speed,
                mission_id=mission.id
            )
            points.append(point)
        
        return points
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer la distance entre deux points GPS"""
        R = 6371  # Rayon de la Terre en km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    
    def generate_retour_premature(self, mission: MissionModel, points: List[TrajectPoint], 
                                 config: AnomalyConfig) -> Tuple[List[TrajectPoint], AnomalyResponse]:
        """Générer une anomalie de retour prématuré"""
        if len(points) < 10:
            return points, None
            
        # Calculer le moment du retour prématuré
        mission_duration = (mission.dateFin - mission.dateDebut).total_seconds() / 3600  # en heures
        early_return_hours = random.uniform(
            config.parameters.get("min_time_before_end", 2),
            config.parameters.get("max_time_before_end", 6)
        )
        
        if early_return_hours >= mission_duration:
            return points, None
            
        # Trouver le point de retour
        cutoff_time = mission.dateFin - timedelta(hours=early_return_hours)
        cutoff_index = len(points) - 1
        
        for i, point in enumerate(points):
            if point.timestamp >= cutoff_time:
                cutoff_index = i
                break
        
        # Modifier les points pour simuler le retour
        start_point = points[0]
        modified_points = points[:cutoff_index]
        
        # Ajouter des points de retour vers le point de départ
        return_points = self._generate_return_trajectory(
            points[cutoff_index-1] if cutoff_index > 0 else start_point,
            start_point,
            cutoff_time,
            mission.dateFin,
            mission.id
        )
        
        modified_points.extend(return_points)
        
        # Créer l'anomalie
        anomaly = AnomalyResponse(
            id=0,  # Sera défini lors de la sauvegarde
            mission_id=mission.id,
            type=AnomalyType.RETOUR_PREMATURE,
            description=f"Retour prématuré détecté {early_return_hours:.1f}h avant la fin prévue",
            timestamp=cutoff_time,
            latitude=points[cutoff_index-1].latitude if cutoff_index > 0 else start_point.latitude,
            longitude=points[cutoff_index-1].longitude if cutoff_index > 0 else start_point.longitude,
            severity=config.severity,
            details={
                "planned_end": mission.dateFin.isoformat(),
                "actual_return": cutoff_time.isoformat(),
                "early_by_hours": early_return_hours
            },
            detected_at=datetime.now()
        )
        
        return modified_points, anomaly
    
    def generate_trajet_divergent(self, mission: MissionModel, points: List[TrajectPoint], 
                                 config: AnomalyConfig) -> Tuple[List[TrajectPoint], AnomalyResponse]:
        """Générer une anomalie de trajet divergent"""
        if len(points) < 5:
            return points, None
            
        # Choisir un point de départ de la divergence
        divergence_start = random.randint(2, len(points) - 3)
        divergence_point = points[divergence_start]
        
        # Calculer la déviation
        deviation_km = random.uniform(
            config.parameters.get("min_deviation_km", 10),
            config.parameters.get("max_deviation_km", 50)
        )
        
        # Générer des points déviés
        modified_points = points[:divergence_start]
        
        # Créer une déviation réaliste
        deviation_points = self._generate_deviation_trajectory(
            divergence_point,
            points[divergence_start + 1],
            deviation_km,
            mission.id
        )
        
        modified_points.extend(deviation_points)
        modified_points.extend(points[divergence_start + 2:])
        
        # Créer l'anomalie
        anomaly = AnomalyResponse(
            id=0,
            mission_id=mission.id,
            type=AnomalyType.TRAJET_DIVERGENT,
            description=f"Déviation de {deviation_km:.1f}km détectée par rapport au trajet prévu",
            timestamp=divergence_point.timestamp,
            latitude=divergence_point.latitude,
            longitude=divergence_point.longitude,
            severity=config.severity,
            details={
                "deviation_km": deviation_km,
                "start_point": {"lat": divergence_point.latitude, "lon": divergence_point.longitude}
            },
            detected_at=datetime.now()
        )
        
        return modified_points, anomaly
    
    def generate_arret_prolonge(self, mission: MissionModel, points: List[TrajectPoint], 
                               config: AnomalyConfig) -> Tuple[List[TrajectPoint], AnomalyResponse]:
        """Générer une anomalie d'arrêt prolongé"""
        if len(points) < 10:
            return points, None
            
        # Choisir un point d'arrêt
        stop_index = random.randint(3, len(points) - 7)
        stop_point = points[stop_index]
        
        # Durée de l'arrêt en minutes
        stop_duration = random.randint(
            config.parameters.get("min_stop_duration", 30),
            config.parameters.get("max_stop_duration", 120)
        )
        
        # Générer des points d'arrêt
        modified_points = points[:stop_index]
        
        # Créer des points stationnaires
        stop_points = self._generate_stationary_points(
            stop_point,
            stop_duration,
            mission.id
        )
        
        # Ajuster les timestamps des points suivants
        time_shift = timedelta(minutes=stop_duration)
        remaining_points = []
        for point in points[stop_index + 1:]:
            adjusted_point = TrajectPoint(
                latitude=point.latitude,
                longitude=point.longitude,
                timestamp=point.timestamp + time_shift,
                vitesse=point.vitesse,
                mission_id=point.mission_id
            )
            remaining_points.append(adjusted_point)
        
        modified_points.extend(stop_points)
        modified_points.extend(remaining_points)
        
        # Créer l'anomalie
        anomaly = AnomalyResponse(
            id=0,
            mission_id=mission.id,
            type=AnomalyType.ARRET_PROLONGE,
            description=f"Arrêt prolongé de {stop_duration} minutes détecté",
            timestamp=stop_point.timestamp,
            latitude=stop_point.latitude,
            longitude=stop_point.longitude,
            severity=config.severity,
            details={
                "stop_duration_minutes": stop_duration,
                "stop_location": {"lat": stop_point.latitude, "lon": stop_point.longitude}
            },
            detected_at=datetime.now()
        )
        
        return modified_points, anomaly
    
    def generate_vitesse_excessive(self, mission: MissionModel, points: List[TrajectPoint], 
                                  config: AnomalyConfig) -> Tuple[List[TrajectPoint], AnomalyResponse]:
        """Générer une anomalie de vitesse excessive"""
        if len(points) < 5:
            return points, None
            
        # Choisir des points pour la vitesse excessive
        speed_start = random.randint(1, len(points) - 4)
        speed_end = min(speed_start + random.randint(2, 5), len(points) - 1)
        
        excessive_speed = random.uniform(
            config.parameters.get("min_speed", 130),
            config.parameters.get("max_speed", 150)
        )
        
        modified_points = points.copy()
        
        # Modifier les vitesses
        for i in range(speed_start, speed_end + 1):
            modified_points[i].vitesse = excessive_speed
        
        # Créer l'anomalie
        anomaly = AnomalyResponse(
            id=0,
            mission_id=mission.id,
            type=AnomalyType.VITESSE_EXCESSIVE,
            description=f"Vitesse excessive de {excessive_speed:.1f} km/h détectée",
            timestamp=points[speed_start].timestamp,
            latitude=points[speed_start].latitude,
            longitude=points[speed_start].longitude,
            severity=config.severity,
            details={
                "max_speed": excessive_speed,
                "duration_points": speed_end - speed_start + 1
            },
            detected_at=datetime.now()
        )
        
        return modified_points, anomaly
    
    def generate_trajet_personnel(self, mission: MissionModel, points: List[TrajectPoint], 
                                 config: AnomalyConfig) -> Tuple[List[TrajectPoint], AnomalyResponse]:
        """Générer une anomalie de trajet personnel"""
        if len(points) < 10:
            return points, None
            
        # Choisir un point de départ pour le trajet personnel
        personal_start = random.randint(2, len(points) - 8)
        
        # Lieux personnels simulés
        personal_locations = config.parameters.get("personal_locations", ["Centre Commercial", "Domicile"])
        location_name = random.choice(personal_locations)
        
        # Générer une position "personnelle"
        base_point = points[personal_start]
        personal_lat = base_point.latitude + random.uniform(-0.02, 0.02)
        personal_lon = base_point.longitude + random.uniform(-0.02, 0.02)
        
        # Créer un détour vers le lieu personnel
        modified_points = points[:personal_start]
        
        # Aller vers le lieu personnel
        personal_points = self._generate_personal_detour(
            base_point,
            personal_lat,
            personal_lon,
            location_name,
            mission.id
        )
        
        modified_points.extend(personal_points)
        modified_points.extend(points[personal_start + 3:])
        
        # Créer l'anomalie
        anomaly = AnomalyResponse(
            id=0,
            mission_id=mission.id,
            type=AnomalyType.TRAJET_PERSONNEL,
            description=f"Trajet personnel détecté vers {location_name}",
            timestamp=base_point.timestamp,
            latitude=personal_lat,
            longitude=personal_lon,
            severity=config.severity,
            details={
                "location_type": location_name,
                "personal_location": {"lat": personal_lat, "lon": personal_lon}
            },
            detected_at=datetime.now()
        )
        
        return modified_points, anomaly
    
    def _generate_return_trajectory(self, start_point: TrajectPoint, end_point: TrajectPoint, 
                                   start_time: datetime, end_time: datetime, mission_id: int) -> List[TrajectPoint]:
        """Générer une trajectoire de retour"""
        points = []
        duration = (end_time - start_time).total_seconds()
        num_points = max(3, int(duration / 300))  # Point toutes les 5 minutes
        
        for i in range(num_points):
            ratio = i / max(1, num_points - 1)
            
            lat = start_point.latitude + (end_point.latitude - start_point.latitude) * ratio
            lon = start_point.longitude + (end_point.longitude - start_point.longitude) * ratio
            
            timestamp = start_time + timedelta(seconds=duration * ratio)
            speed = random.uniform(40, 80)
            
            point = TrajectPoint(
                latitude=lat,
                longitude=lon,
                timestamp=timestamp,
                vitesse=speed,
                mission_id=mission_id
            )
            points.append(point)
        
        return points
    
    def _generate_deviation_trajectory(self, start_point: TrajectPoint, end_point: TrajectPoint, 
                                      deviation_km: float, mission_id: int) -> List[TrajectPoint]:
        """Générer une trajectoire déviée"""
        points = []
        
        # Calculer un point de déviation
        mid_lat = (start_point.latitude + end_point.latitude) / 2
        mid_lon = (start_point.longitude + end_point.longitude) / 2
        
        # Ajouter une déviation perpendiculaire
        deviation_lat = mid_lat + (deviation_km / 111) * random.choice([-1, 1])
        deviation_lon = mid_lon + (deviation_km / 111) * random.choice([-1, 1])
        
        # Créer 3 points: start -> deviation -> end
        trajectory_points = [
            (start_point.latitude, start_point.longitude),
            (deviation_lat, deviation_lon),
            (end_point.latitude, end_point.longitude)
        ]
        
        duration = (end_point.timestamp - start_point.timestamp).total_seconds()
        
        for i, (lat, lon) in enumerate(trajectory_points):
            timestamp = start_point.timestamp + timedelta(seconds=duration * i / 2)
            speed = random.uniform(30, 70)
            
            point = TrajectPoint(
                latitude=lat,
                longitude=lon,
                timestamp=timestamp,
                vitesse=speed,
                mission_id=mission_id
            )
            points.append(point)
        
        return points
    
    def _generate_stationary_points(self, base_point: TrajectPoint, duration_minutes: int, mission_id: int) -> List[TrajectPoint]:
        """Générer des points stationnaires"""
        points = []
        num_points = max(1, duration_minutes // 5)  # Point toutes les 5 minutes
        
        for i in range(num_points):
            timestamp = base_point.timestamp + timedelta(minutes=i * 5)
            
            # Petite variation pour simuler un véhicule à l'arrêt
            lat = base_point.latitude + random.uniform(-0.0001, 0.0001)
            lon = base_point.longitude + random.uniform(-0.0001, 0.0001)
            
            point = TrajectPoint(
                latitude=lat,
                longitude=lon,
                timestamp=timestamp,
                vitesse=0.0,  # Vitesse nulle pour l'arrêt
                mission_id=mission_id
            )
            points.append(point)
        
        return points
    
    def _generate_personal_detour(self, base_point: TrajectPoint, personal_lat: float, 
                                 personal_lon: float, location_name: str, mission_id: int) -> List[TrajectPoint]:
        """Générer un détour vers un lieu personnel"""
        points = []
        
        # Aller vers le lieu personnel
        go_point = TrajectPoint(
            latitude=personal_lat,
            longitude=personal_lon,
            timestamp=base_point.timestamp + timedelta(minutes=10),
            vitesse=random.uniform(30, 50),
            mission_id=mission_id
        )
        
        # Rester sur place
        stay_point = TrajectPoint(
            latitude=personal_lat,
            longitude=personal_lon,
            timestamp=base_point.timestamp + timedelta(minutes=25),
            vitesse=0.0,
            mission_id=mission_id
        )
        
        # Repartir
        return_point = TrajectPoint(
            latitude=base_point.latitude,
            longitude=base_point.longitude,
            timestamp=base_point.timestamp + timedelta(minutes=40),
            vitesse=random.uniform(30, 50),
            mission_id=mission_id
        )
        
        points.extend([go_point, stay_point, return_point])
        return points
    
    async def apply_anomalies_to_trajectory(self, mission: MissionModel, points: List[TrajectPoint], 
                                          anomaly_configs: List[AnomalyConfig] = None) -> Tuple[List[TrajectPoint], List[AnomalyResponse]]:
        """Appliquer des anomalies à une trajectoire"""
        if not anomaly_configs:
            anomaly_configs = self.DEFAULT_ANOMALY_CONFIG
        
        modified_points = points.copy()
        detected_anomalies = []
        
        for config in anomaly_configs:
            # Vérifier la probabilité
            if random.random() > config.probability:
                continue
                
            try:
                if config.type == AnomalyType.RETOUR_PREMATURE:
                    modified_points, anomaly = self.generate_retour_premature(mission, modified_points, config)
                elif config.type == AnomalyType.TRAJET_DIVERGENT:
                    modified_points, anomaly = self.generate_trajet_divergent(mission, modified_points, config)
                elif config.type == AnomalyType.ARRET_PROLONGE:
                    modified_points, anomaly = self.generate_arret_prolonge(mission, modified_points, config)
                elif config.type == AnomalyType.VITESSE_EXCESSIVE:
                    modified_points, anomaly = self.generate_vitesse_excessive(mission, modified_points, config)
                elif config.type == AnomalyType.TRAJET_PERSONNEL:
                    modified_points, anomaly = self.generate_trajet_personnel(mission, modified_points, config)
                else:
                    continue
                
                if anomaly:
                    detected_anomalies.append(anomaly)
                    logger.info(f"Anomalie générée: {anomaly.type} pour mission {mission.id}")
                    
            except Exception as e:
                logger.error(f"Erreur lors de la génération d'anomalie {config.type}: {e}")
                continue
        
        return modified_points, detected_anomalies
    
    async def save_anomalies(self, anomalies: List[AnomalyResponse]) -> bool:
        """Sauvegarder les anomalies en base de données"""
        try:
            for anomaly in anomalies:
                db_anomaly = AnomalieModel(
                    mission_id=anomaly.mission_id,
                    type=anomaly.type.value,
                    description=anomaly.description,
                    dateDetection=anomaly.detected_at
                )
                self.db.add(db_anomaly)
            
            self.db.commit()
            logger.info(f"Sauvegardé {len(anomalies)} anomalies")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors de la sauvegarde des anomalies: {e}")
            return False
    
    async def get_mission_anomalies(self, mission_id: int) -> List[AnomalyResponse]:
        """Récupérer les anomalies d'une mission"""
        try:
            anomalies = self.db.query(AnomalieModel).filter(
                AnomalieModel.mission_id == mission_id
            ).all()
            
            result = []
            for anomaly in anomalies:
                anomaly_response = AnomalyResponse(
                    id=anomaly.id,
                    mission_id=anomaly.mission_id,
                    type=AnomalyType(anomaly.type),
                    description=anomaly.description,
                    timestamp=anomaly.dateDetection,
                    latitude=0.0,  # Pas stocké dans le modèle actuel
                    longitude=0.0,  # Pas stocké dans le modèle actuel
                    severity="MEDIUM",  # Valeur par défaut
                    details={},
                    detected_at=anomaly.dateDetection
                )
                result.append(anomaly_response)
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des anomalies: {e}")
            return []
    
    async def get_anomaly_statistics(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """Obtenir des statistiques sur les anomalies"""
        try:
            query = self.db.query(AnomalieModel)
            
            if start_date:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(AnomalieModel.dateDetection >= start_dt)
            
            if end_date:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(AnomalieModel.dateDetection <= end_dt)
            
            anomalies = query.all()
            
            # Calculer les statistiques
            total_anomalies = len(anomalies)
            
            # Statistiques par type
            type_stats = {}
            for anomaly in anomalies:
                anomaly_type = anomaly.type
                type_stats[anomaly_type] = type_stats.get(anomaly_type, 0) + 1
            
            # Statistiques par mission
            mission_stats = {}
            for anomaly in anomalies:
                mission_id = anomaly.mission_id
                mission_stats[mission_id] = mission_stats.get(mission_id, 0) + 1
            
            return {
                "total_anomalies": total_anomalies,
                "type_distribution": type_stats,
                "mission_distribution": mission_stats,
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques: {e}")
            return {"error": str(e)}