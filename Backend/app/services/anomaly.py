import asyncio
import json
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from math import radians, cos, sin, asin, sqrt, atan2, degrees
from enum import Enum

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, not_, exists, select # Import 'select'

from app.models.models import Mission, Trajet, Anomalie  # Vos modèles SQLAlchemy
from app.schemas.anomaly import (
    AnomalyConfig, AnomalyType, TrajectPoint, 
    AnomalyInjectionResult, AnomalyRule
)

logger = logging.getLogger(__name__)

class AnomalyType(Enum):
    """Types d'anomalies possibles"""
    RETOUR_PREMATURE = "retour_premature"
    TRAJET_DIVERGENT = "trajet_divergent"
    ARRET_NON_AUTORISE = "arret_non_autorise"
    VITESSE_ANORMALE = "vitesse_anormale"
    DEPLACEMENT_HORS_HEURES = "deplacement_hors_heures"
    SORTIE_ZONE_AUTORISEE = "sortie_zone_autorisee"

class AnomalyInjectionService:
    """Service d'injection d'anomalies dans les trajectoires"""
    
    def __init__(self, db: Session):
        self.db = db
        self.config = self._load_default_config()
        
    def _load_default_config(self) -> AnomalyConfig:
        """Charger la configuration par défaut des anomalies"""
        return AnomalyConfig(
            injection_probability=1.0,  # Remis à 0.3 pour le comportement normal
            anomaly_types={
                AnomalyType.RETOUR_PREMATURE: AnomalyRule(
                    probability=0.15,
                    severity_range=(0.6, 0.9),
                    parameters={
                        "early_return_ratio": (0.3, 0.7),
                        "detour_distance_km": (5, 15)
                    }
                ),
                AnomalyType.TRAJET_DIVERGENT: AnomalyRule(
                    probability=0.25,
                    severity_range=(0.4, 0.8),
                    parameters={
                        "deviation_distance_km": (2, 10),
                        "deviation_duration_min": (15, 60)
                    }
                ),
                AnomalyType.ARRET_NON_AUTORISE: AnomalyRule(
                    probability=0.20,
                    severity_range=(0.3, 0.7),
                    parameters={
                        "stop_duration_min": (10, 120),
                        "stop_frequency": (1, 3)
                    }
                ),
                AnomalyType.VITESSE_ANORMALE: AnomalyRule(
                    probability=0.30,
                    severity_range=(0.2, 0.6),
                    parameters={
                        "speed_factor": (0.1, 2.5),
                        "duration_min": (5, 30)
                    }
                ),
                AnomalyType.DEPLACEMENT_HORS_HEURES: AnomalyRule(
                    probability=0.10,
                    severity_range=(0.5, 0.9),
                    parameters={
                        "early_start_hours": (1, 3),
                        "late_end_hours": (1, 4)
                    }
                )
            }
        )
    
    async def get_clean_trajectories(self, mission_id: Optional[int] = None) -> List[TrajectPoint]:
        """Récupérer les trajectoires propres (non contaminées)"""
        try:
            # Construire la requête avec jointure explicite
            query = self.db.query(Trajet).options(joinedload(Trajet.mission_rel))
            
            # Filtrer par mission si spécifiée
            if mission_id:
                query = query.filter(Trajet.mission_id == mission_id)
            
            # Exclure les missions contaminées
            # FIX SAWarning: Utiliser select() explicitement pour la sous-requête
            contaminated_subquery = select(Anomalie.mission_id).where(
                Anomalie.type == 'TRAJECTORY_CONTAMINATED'
            )
            
            query = query.filter(
                not_(Trajet.mission_id.in_(contaminated_subquery))
            )
            
            # Ordonner par mission et timestamp
            query = query.order_by(Trajet.mission_id, Trajet.timestamp)
            
            # Récupérer les résultats
            results = query.all()
            
            trajectories = []
            for trajet in results:
                if not trajet.mission_rel:
                    logger.warning(f"Mission non trouvée pour trajet {trajet.id}")
                    continue
                
                # Gérer les dates potentiellement None
                mission_start = trajet.mission_rel.dateDebut if trajet.mission_rel.dateDebut else datetime.now()
                mission_end = trajet.mission_rel.dateFin if trajet.mission_rel.dateFin else datetime.now() + timedelta(hours=1)
                
                point = TrajectPoint(
                    id=trajet.id,
                    mission_id=trajet.mission_id,
                    timestamp=trajet.timestamp,
                    latitude=float(trajet.latitude),
                    longitude=float(trajet.longitude),
                    vitesse=float(trajet.vitesse),
                    mission_start=mission_start,
                    mission_end=mission_end
                )
                trajectories.append(point)
            
            logger.info(f"Récupéré {len(trajectories)} points de trajectoire propres")
            return trajectories
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des trajectoires: {e}")
            return []
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer la distance entre deux points GPS"""
        try:
            R = 6371  # Rayon de la Terre en km
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return R * c
        except Exception as e:
            logger.error(f"Erreur dans le calcul de distance: {e}")
            return 0.0
    
    def _validate_trajectory(self, trajectory: List[TrajectPoint]) -> bool:
        """Valider une trajectoire avant traitement"""
        if not trajectory:
            return False
        
        # Vérifier que tous les points ont des coordonnées valides
        for point in trajectory:
            if not (-90 <= point.latitude <= 90) or not (-180 <= point.longitude <= 180):
                logger.warning(f"Point avec coordonnées invalides: {point.latitude}, {point.longitude}")
                return False
        
        return True
    
    def _inject_early_return_anomaly(self, trajectory: List[TrajectPoint]) -> List[TrajectPoint]:
        """Injecter une anomalie de retour prématuré"""
        if not self._validate_trajectory(trajectory) or len(trajectory) < 10:
            logger.warning("Trajectoire invalide pour injection retour prématuré")
            return trajectory
        
        try:
            rule = self.config.anomaly_types[AnomalyType.RETOUR_PREMATURE]
            early_ratio = random.uniform(*rule.parameters["early_return_ratio"])
            
            # Point de retour prématuré
            return_index = int(len(trajectory) * early_ratio)
            return_point = trajectory[return_index]
            
            # Créer le trajet de retour vers le point de départ
            start_point = trajectory[0]
            detour_distance = random.uniform(*rule.parameters["detour_distance_km"])
            
            # Modifier les points après le retour prématuré
            modified_trajectory = trajectory[:return_index].copy()
            
            # Ajouter des points de retour avec un détour
            return_duration = (return_point.mission_end - return_point.timestamp).total_seconds() / 2
            num_return_points = max(5, int(return_duration / 300))  # Un point toutes les 5 minutes
            
            for i in range(num_return_points):
                progress = i / num_return_points
                
                # Interpolation avec détour
                lat = return_point.latitude + (start_point.latitude - return_point.latitude) * progress
                lon = return_point.longitude + (start_point.longitude - return_point.longitude) * progress
                
                # Ajouter un détour aléatoire
                detour_lat = random.uniform(-0.001, 0.001) # Small random offset
                detour_lon = random.uniform(-0.001, 0.001) # Small random offset
                
                new_point = TrajectPoint(
                    mission_id=return_point.mission_id,
                    timestamp=return_point.timestamp + timedelta(seconds=i * (return_duration / num_return_points)),
                    latitude=lat + detour_lat,
                    longitude=lon + detour_lon,
                    vitesse=random.uniform(20, 60),
                    mission_start=return_point.mission_start,
                    mission_end=return_point.mission_end
                )
                modified_trajectory.append(new_point)
            
            logger.info(f"Anomalie retour prématuré injectée à {early_ratio:.1%} de la mission")
            return modified_trajectory
            
        except Exception as e:
            logger.error(f"Erreur lors de l'injection retour prématuré: {e}")
            return trajectory
    
    def _inject_route_deviation_anomaly(self, trajectory: List[TrajectPoint]) -> List[TrajectPoint]:
        """Injecter une anomalie de déviation de trajet"""
        if not self._validate_trajectory(trajectory) or len(trajectory) < 6:
            logger.warning("Trajectoire invalide pour injection déviation")
            return trajectory
        
        try:
            rule = self.config.anomaly_types[AnomalyType.TRAJET_DIVERGENT]
            deviation_distance = random.uniform(*rule.parameters["deviation_distance_km"])
            deviation_duration = random.uniform(*rule.parameters["deviation_duration_min"])
            
            # Point de début de déviation (milieu du trajet)
            start_index = random.randint(len(trajectory) // 4, 3 * len(trajectory) // 4)
            deviation_start = trajectory[start_index]
            
            # Calculer le nombre de points de déviation
            num_deviation_points = max(3, int(deviation_duration / 5))  # Un point toutes les 5 minutes
            
            modified_trajectory = trajectory[:start_index].copy()
            
            # Générer les points de déviation
            for i in range(num_deviation_points):
                angle = random.uniform(0, 2 * 3.14159)
                distance_factor = random.uniform(0.5, 1.0)
                
                # Calculer la déviation
                lat_offset = (deviation_distance * distance_factor * cos(angle)) / 111
                lon_offset = (deviation_distance * distance_factor * sin(angle)) / 111
                
                deviated_point = TrajectPoint(
                    mission_id=deviation_start.mission_id,
                    timestamp=deviation_start.timestamp + timedelta(minutes=i * 5),
                    latitude=deviation_start.latitude + lat_offset,
                    longitude=deviation_start.longitude + lon_offset,
                    vitesse=random.uniform(15, 45),
                    mission_start=deviation_start.mission_start,
                    mission_end=deviation_start.mission_end
                )
                modified_trajectory.append(deviated_point)
            
            # Reprendre le trajet normal après la déviation
            resume_index = min(start_index + num_deviation_points, len(trajectory) - 1)
            modified_trajectory.extend(trajectory[resume_index:])
            
            logger.info(f"Anomalie déviation de trajet injectée: {deviation_distance:.1f}km pendant {deviation_duration:.1f}min")
            return modified_trajectory
            
        except Exception as e:
            logger.error(f"Erreur lors de l'injection déviation: {e}")
            return trajectory
    
    def _inject_unauthorized_stop_anomaly(self, trajectory: List[TrajectPoint]) -> List[TrajectPoint]:
        """Injecter une anomalie d'arrêt non autorisé"""
        if not self._validate_trajectory(trajectory) or len(trajectory) < 5:
            logger.warning("Trajectoire invalide pour injection arrêt non autorisé")
            return trajectory
        
        try:
            rule = self.config.anomaly_types[AnomalyType.ARRET_NON_AUTORISE]
            stop_duration = random.uniform(*rule.parameters["stop_duration_min"])
            stop_frequency = random.randint(*rule.parameters["stop_frequency"])
            
            modified_trajectory = trajectory.copy()
            
            for _ in range(stop_frequency):
                # Choisir un point d'arrêt aléatoire
                stop_index = random.randint(len(trajectory) // 4, 3 * len(trajectory) // 4)
                stop_point = trajectory[stop_index]
                
                # Créer des points d'arrêt
                num_stop_points = max(2, int(stop_duration / 10))  # Un point toutes les 10 minutes
                
                for i in range(num_stop_points):
                    # Petite variation de position (véhicule qui se gare)
                    lat_variation = random.uniform(-0.001, 0.001)
                    lon_variation = random.uniform(-0.001, 0.001)
                    
                    stop_point_modified = TrajectPoint(
                        mission_id=stop_point.mission_id,
                        timestamp=stop_point.timestamp + timedelta(minutes=i * 10),
                        latitude=stop_point.latitude + lat_variation,
                        longitude=stop_point.longitude + lon_variation,
                        vitesse=random.uniform(0, 2),  # Vitesse très faible
                        mission_start=stop_point.mission_start,
                        mission_end=stop_point.mission_end
                    )
                    modified_trajectory.insert(stop_index + i + 1, stop_point_modified)
            
            logger.info(f"Anomalie arrêt non autorisé injectée: {stop_frequency} arrêts de {stop_duration:.1f}min")
            return modified_trajectory
            
        except Exception as e:
            logger.error(f"Erreur lors de l'injection arrêt non autorisé: {e}")
            return trajectory
    
    def _inject_abnormal_speed_anomaly(self, trajectory: List[TrajectPoint]) -> List[TrajectPoint]:
        """Injecter une anomalie de vitesse anormale"""
        if not self._validate_trajectory(trajectory) or len(trajectory) < 3:
            logger.warning("Trajectoire invalide pour injection vitesse anormale")
            return trajectory
        
        try:
            rule = self.config.anomaly_types[AnomalyType.VITESSE_ANORMALE]
            speed_factor = random.uniform(*rule.parameters["speed_factor"])
            duration_min = random.uniform(*rule.parameters["duration_min"])
            
            # Choisir une section pour modifier la vitesse
            start_index = random.randint(0, len(trajectory) // 2)
            end_index = min(start_index + int(duration_min / 5), len(trajectory) - 1)
            
            modified_trajectory = trajectory.copy()
            
            for i in range(start_index, end_index):
                original_speed = modified_trajectory[i].vitesse
                new_speed = original_speed * speed_factor
                
                # Limiter les vitesses extrêmes
                new_speed = max(0, min(150, new_speed))
                
                modified_trajectory[i].vitesse = new_speed
            
            logger.info(f"Anomalie vitesse anormale injectée: facteur {speed_factor:.2f} pendant {duration_min:.1f}min")
            return modified_trajectory
            
        except Exception as e:
            logger.error(f"Erreur lors de l'injection vitesse anormale: {e}")
            return trajectory
    
    def _inject_out_of_hours_anomaly(self, trajectory: List[TrajectPoint]) -> List[TrajectPoint]:
        """Injecter une anomalie de déplacement hors heures"""
        if not self._validate_trajectory(trajectory) or len(trajectory) < 2:
            logger.warning("Trajectoire invalide pour injection hors heures")
            return trajectory
        
        try:
            rule = self.config.anomaly_types[AnomalyType.DEPLACEMENT_HORS_HEURES]
            early_start_hours = random.uniform(*rule.parameters["early_start_hours"])
            late_end_hours = random.uniform(*rule.parameters["late_end_hours"])
            
            modified_trajectory = trajectory.copy()
            
            # Ajouter des points avant le début officiel
            mission_start = trajectory[0].mission_start
            early_start_time = mission_start - timedelta(hours=early_start_hours)
            
            # Points de déplacement précoce
            num_early_points = max(2, int(early_start_hours * 6))  # Un point toutes les 10 minutes
            for i in range(num_early_points):
                early_point = TrajectPoint(
                    mission_id=trajectory[0].mission_id,
                    timestamp=early_start_time + timedelta(minutes=i * 10),
                    latitude=trajectory[0].latitude + random.uniform(-0.01, 0.01),
                    longitude=trajectory[0].longitude + random.uniform(-0.01, 0.01),
                    vitesse=random.uniform(10, 30),
                    mission_start=trajectory[0].mission_start,
                    mission_end=trajectory[0].mission_end
                )
                modified_trajectory.insert(0, early_point)
            
            # Ajouter des points après la fin officielle
            mission_end = trajectory[-1].mission_end
            late_end_time = mission_end + timedelta(hours=late_end_hours)
            
            num_late_points = max(2, int(late_end_hours * 6))
            for i in range(num_late_points):
                late_point = TrajectPoint(
                    mission_id=trajectory[-1].mission_id,
                    timestamp=mission_end + timedelta(minutes=i * 10),
                    latitude=trajectory[-1].latitude + random.uniform(-0.01, 0.01),
                    longitude=trajectory[-1].longitude + random.uniform(-0.01, 0.01),
                    vitesse=random.uniform(10, 25),
                    mission_start=trajectory[-1].mission_start,
                    mission_end=trajectory[-1].mission_end
                )
                modified_trajectory.append(late_point)
            
            logger.info(f"Anomalie hors heures injectée: -{early_start_hours:.1f}h début, +{late_end_hours:.1f}h fin")
            return modified_trajectory
            
        except Exception as e:
            logger.error(f"Erreur lors de l'injection hors heures: {e}")
            return trajectory
    
    async def inject_anomalies_for_mission(self, mission_id: int) -> AnomalyInjectionResult:
        """Injecter des anomalies pour une mission spécifique"""
        try:
            # Récupérer la trajectoire propre
            trajectory = await self.get_clean_trajectories(mission_id)
            
            if not trajectory:
                logger.warning(f"Aucune trajectoire propre trouvée pour la mission {mission_id}")
                return AnomalyInjectionResult(
                    mission_id=mission_id,
                    success=False,
                    anomalies_injected=[],
                    original_points_count=0,
                    modified_points_count=0,
                    error_message="Aucune trajectoire propre trouvée"
                )
            
            original_count = len(trajectory)
            modified_trajectory = trajectory.copy()
            injected_anomalies = []
            
            # Décider si on injecte des anomalies
            if random.random() > self.config.injection_probability:
                logger.info(f"Aucune anomalie injectée pour la mission {mission_id} (probabilité)")
                return AnomalyInjectionResult(
                    mission_id=mission_id,
                    success=True,
                    anomalies_injected=[],
                    original_points_count=original_count,
                    modified_points_count=original_count
                )
            
            # Injecter les anomalies selon les probabilités
            for anomaly_type, rule in self.config.anomaly_types.items():
                if random.random() <= rule.probability:
                    try:
                        if anomaly_type == AnomalyType.RETOUR_PREMATURE:
                            modified_trajectory = self._inject_early_return_anomaly(modified_trajectory)
                        elif anomaly_type == AnomalyType.TRAJET_DIVERGENT:
                            modified_trajectory = self._inject_route_deviation_anomaly(modified_trajectory)
                        elif anomaly_type == AnomalyType.ARRET_NON_AUTORISE:
                            modified_trajectory = self._inject_unauthorized_stop_anomaly(modified_trajectory)
                        elif anomaly_type == AnomalyType.VITESSE_ANORMALE:
                            modified_trajectory = self._inject_abnormal_speed_anomaly(modified_trajectory)
                        elif anomaly_type == AnomalyType.DEPLACEMENT_HORS_HEURES:
                            modified_trajectory = self._inject_out_of_hours_anomaly(modified_trajectory)
                        
                        injected_anomalies.append(anomaly_type.value)
                        
                    except Exception as e:
                        logger.error(f"Erreur lors de l'injection de {anomaly_type.value}: {e}")
            
            # Sauvegarder la trajectoire modifiée
            if injected_anomalies:
                await self._save_contaminated_trajectory(modified_trajectory, injected_anomalies)
                await self._mark_mission_as_contaminated(mission_id, injected_anomalies)
            
            result = AnomalyInjectionResult(
                mission_id=mission_id,
                success=True,
                anomalies_injected=injected_anomalies,
                original_points_count=original_count,
                modified_points_count=len(modified_trajectory)
            )
            
            logger.info(f"Injection terminée pour mission {mission_id}: {len(injected_anomalies)} anomalies")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de l'injection d'anomalies pour mission {mission_id}: {e}")
            return AnomalyInjectionResult(
                mission_id=mission_id,
                success=False,
                anomalies_injected=[],
                original_points_count=0,
                modified_points_count=0,
                error_message=str(e)
            )
    
    async def _save_contaminated_trajectory(self, trajectory: List[TrajectPoint], anomaly_types: List[str]):
        """Sauvegarder la trajectoire contaminée"""
        try:
            if not trajectory:
                raise ValueError("Trajectoire vide")
            
            mission_id = trajectory[0].mission_id
            
            # --- FIX START ---
            # Identify missions that are currently marked as contaminated
            # This subquery correctly identifies contaminated mission IDs
            contaminated_mission_ids_subquery = select(Anomalie.mission_id).where(
                Anomalie.type == 'TRAJECTORY_CONTAMINATED'
            )

            # Delete all Trajet points for the current mission_id
            # ONLY if this mission_id is marked as contaminated (i.e., it was previously contaminated)
            # This avoids the ambiguous join by checking the mission_id directly.
            self.db.query(Trajet).filter(
                and_(
                    Trajet.mission_id == mission_id,
                    Trajet.mission_id.in_(contaminated_mission_ids_subquery)
                )
            ).delete(synchronize_session=False)
            # --- FIX END ---
            
            # Traiter les points de trajectoire
            for point in trajectory:
                if not point.id:  # Nouveaux points
                    nouveau_trajet = Trajet(
                        mission_id=point.mission_id,
                        timestamp=point.timestamp,
                        latitude=point.latitude,
                        longitude=point.longitude,
                        vitesse=point.vitesse
                    )
                    self.db.add(nouveau_trajet)
                else:  # Mise à jour des points existants
                    trajet_existant = self.db.query(Trajet).filter(Trajet.id == point.id).first()
                    if trajet_existant:
                        trajet_existant.timestamp = point.timestamp
                        trajet_existant.latitude = point.latitude
                        trajet_existant.longitude = point.longitude
                        trajet_existant.vitesse = point.vitesse
            
            self.db.commit()
            logger.info(f"Trajectoire contaminée sauvegardée: {len(trajectory)} points")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors de la sauvegarde de la trajectoire contaminée: {e}")
            raise
    
    async def _mark_mission_as_contaminated(self, mission_id: int, anomaly_types: List[str]):
        """Marquer la mission comme contaminée"""
        try:
            # Supprimer les anciens marqueurs de contamination
            self.db.query(Anomalie).filter(
                and_(
                    Anomalie.mission_id == mission_id,
                    Anomalie.type == 'TRAJECTORY_CONTAMINATED'
                )
            ).delete(synchronize_session=False)
            
            # Ajouter le nouveau marqueur
            description = f"Trajectoire contaminée avec anomalies: {', '.join(anomaly_types)}"
            nouvelle_anomalie = Anomalie(
                mission_id=mission_id,
                type='TRAJECTORY_CONTAMINATED',
                description=description,
                dateDetection=datetime.now()
            )
            self.db.add(nouvelle_anomalie)
            
            self.db.commit()
            logger.info(f"Mission {mission_id} marquée comme contaminée")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors du marquage de contamination: {e}")
            raise
    
    async def inject_anomalies_batch(self, mission_ids: List[int] = None) -> List[AnomalyInjectionResult]:
        """Injecter des anomalies en lot"""
        if mission_ids is None:
            # Récupérer toutes les missions avec trajectoires propres
            contaminated_missions = select(Anomalie.mission_id).where( # FIX SAWarning: Utiliser select() ici aussi
                Anomalie.type == 'TRAJECTORY_CONTAMINATED'
            )
            
            missions = self.db.query(Mission.id).join(Trajet).filter(
                and_(
                    Mission.statut == 'EN_COURS',
                    not_(Mission.id.in_(contaminated_missions))
                )
            ).distinct().all()
            
            mission_ids = [mission.id for mission in missions]
        
        results = []
        for mission_id in mission_ids:
            try:
                result = await self.inject_anomalies_for_mission(mission_id)
                results.append(result)
                
                # Pause entre les injections
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Erreur lors de l'injection pour mission {mission_id}: {e}")
                results.append(AnomalyInjectionResult(
                    mission_id=mission_id,
                    success=False,
                    anomalies_injected=[],
                    original_points_count=0,
                    modified_points_count=0,
                    error_message=str(e)
                ))
        
        logger.info(f"Injection en lot terminée: {len(results)} missions traitées")
        return results
    
    def update_config(self, new_config: AnomalyConfig):
        """Mettre à jour la configuration des anomalies"""
        self.config = new_config
        logger.info("Configuration d'anomalies mise à jour")
    
    async def get_contaminated_missions(self) -> List[int]:
        """Récupérer la liste des missions contaminées"""
        try:
            missions = self.db.query(Anomalie.mission_id).filter(
                Anomalie.type == 'TRAJECTORY_CONTAMINATED'
            ).distinct().order_by(Anomalie.mission_id).all()
            
            return [mission.mission_id for mission in missions]
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des missions contaminées: {e}")
            return []
    
    async def clean_contaminated_trajectories(self, mission_ids: List[int] = None):
        """Nettoyer les trajectoires contaminées"""
        try:
            query = self.db.query(Anomalie).filter(
                Anomalie.type == 'TRAJECTORY_CONTAMINATED'
            )
            
            if mission_ids:
                query = query.filter(Anomalie.mission_id.in_(mission_ids))
            
            # Supprimer les anomalies
            query.delete(synchronize_session=False)
            
            self.db.commit()
            logger.info("Trajectoires contaminées nettoyées")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors du nettoyage: {e}")
            raise
