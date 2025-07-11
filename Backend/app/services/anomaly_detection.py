import asyncio
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import pickle
import os
from collections import defaultdict

from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import LocalOutlierFactor
from scipy import stats
from scipy.spatial.distance import euclidean
from scipy.signal import savgol_filter

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from app.models.models import Mission, Trajet, Anomalie
from app.schemas.anomaly import TrajectPoint, AnomalyType

logger = logging.getLogger(__name__)

@dataclass
class AnomalyScore:
    """Score d'anomalie pour un point ou une trajectoire"""
    anomaly_type: str
    score: float  # 0-1, 1 étant le plus anormal
    confidence: float  # 0-1, confiance dans la détection
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    details: Dict[str, Any]
    timestamp: datetime
    affected_points: List[int] = None

@dataclass
class TrajectoryFeatures:
    """Caractéristiques extraites d'une trajectoire"""
    mission_id: int
    total_distance: float
    average_speed: float
    max_speed: float
    min_speed: float
    speed_variance: float
    total_duration: float
    stop_count: int
    direction_changes: int
    acceleration_variance: float
    path_efficiency: float  # Ratio distance directe / distance parcourue
    time_efficiency: float  # Ratio temps théorique / temps réel
    out_of_bounds_ratio: float
    night_travel_ratio: float
    speed_violations: int
    anomaly_indicators: Dict[str, float]

class AnomalyDetectionService:
    """Service principal de détection d'anomalies par IA"""
    
    def __init__(self, db: Session, models_path: str = "models/"):
        self.db = db
        self.models_path = models_path
        self.models = {}
        self.scalers = {}
        self.feature_extractors = {}
        
        # Seuils de détection
        self.thresholds = {
            'isolation_forest': 0.1,
            'local_outlier_factor': 2.0,
            'speed_anomaly': 0.8,
            'route_deviation': 0.7,
            'time_anomaly': 0.6,
            'pattern_anomaly': 0.75
        }
        
        # Configuration des modèles
        self.model_config = {
            'isolation_forest': {
                'contamination': 0.1,
                'n_estimators': 100,
                'max_samples': 'auto',
                'random_state': 42
            },
            'dbscan': {
                'eps': 0.5,
                'min_samples': 5
            },
            'lof': {
                'n_neighbors': 20,
                'contamination': 0.1
            }
        }
        
        # Initialiser ou charger les modèles
        self._initialize_models()
        self._load_models()
    
    def _initialize_models(self):
        """Initialiser les modèles de ML pour la première fois si nécessaire"""
        try:
            # Créer le dossier des modèles s'il n'existe pas
            os.makedirs(self.models_path, exist_ok=True)
            
            # Modèle principal : Isolation Forest
            self.models['isolation_forest'] = IsolationForest(
                **self.model_config['isolation_forest']
            )
            
            # Modèle de clustering : DBSCAN
            self.models['dbscan'] = DBSCAN(
                **self.model_config['dbscan']
            )
            
            # Modèle LOF pour détection d'outliers locaux
            self.models['lof'] = LocalOutlierFactor(
                **self.model_config['lof']
            )
            
            # Classificateur pour types d'anomalies
            self.models['anomaly_classifier'] = RandomForestClassifier(
                n_estimators=100,
                random_state=42,
                max_depth=10
            )
            
            # Scalers pour normalisation
            self.scalers['standard'] = StandardScaler()
            self.scalers['minmax'] = MinMaxScaler()
            
            logger.info("Modèles ML initialisés (modèles vierges)")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation des modèles: {e}")
    
    def _load_models(self):
        """Charger les modèles et scalers pré-entraînés depuis le disque"""
        try:
            model_files = {
                'isolation_forest': 'isolation_forest.pkl',
                'anomaly_classifier': 'anomaly_classifier.pkl',
            }
            scaler_files = {
                'standard': 'standard_scaler.pkl',
                'minmax': 'minmax_scaler.pkl',
            }
            
            all_files_exist = True
            for name, filename in model_files.items():
                file_path = os.path.join(self.models_path, filename)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        self.models[name] = pickle.load(f)
                        logger.info(f"Modèle {name} chargé avec succès.")
                else:
                    all_files_exist = False
                    logger.warning(f"Fichier de modèle manquant: {file_path}")
            
            for name, filename in scaler_files.items():
                file_path = os.path.join(self.models_path, filename)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        self.scalers[name] = pickle.load(f)
                        logger.info(f"Scaler {name} chargé avec succès.")
                else:
                    all_files_exist = False
                    logger.warning(f"Fichier de scaler manquant: {file_path}")
            
            if all_files_exist:
                logger.info("Tous les modèles et scalers ont été chargés.")
            else:
                logger.warning("Un ou plusieurs fichiers de modèle/scaler sont manquants. Un entraînement est nécessaire.")
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement des modèles: {e}")
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer la distance entre deux points GPS"""
        R = 6371  # Rayon de la Terre en km
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    
    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer le cap entre deux points"""
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        y = sin(dlon) * cos(lat2)
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        bearing = atan2(y, x)
        return (degrees(bearing) + 360) % 360
    
    def _smooth_trajectory(self, points: List[TrajectPoint]) -> List[TrajectPoint]:
        """Lisser la trajectoire pour réduire le bruit"""
        if len(points) < 5:
            return points
        
        try:
            # Extraire les coordonnées
            latitudes = [p.latitude for p in points]
            longitudes = [p.longitude for p in points]
            speeds = [p.vitesse for p in points]
            
            # Appliquer un filtre de Savitzky-Golay
            window_length = min(5, len(points) if len(points) % 2 == 1 else len(points) - 1)
            if window_length >= 5:
                smooth_lats = savgol_filter(latitudes, window_length, 2)
                smooth_lons = savgol_filter(longitudes, window_length, 2)
                smooth_speeds = savgol_filter(speeds, window_length, 2)
                
                # Créer les nouveaux points
                smoothed_points = []
                for i, point in enumerate(points):
                    new_point = TrajectPoint(
                        id=point.id,
                        mission_id=point.mission_id,
                        timestamp=point.timestamp,
                        latitude=float(smooth_lats[i]),
                        longitude=float(smooth_lons[i]),
                        vitesse=float(smooth_speeds[i]),
                        mission_start=point.mission_start,
                        mission_end=point.mission_end
                    )
                    smoothed_points.append(new_point)
                
                return smoothed_points
            
            return points
            
        except Exception as e:
            logger.warning(f"Erreur lors du lissage: {e}")
            return points
    
    def extract_trajectory_features(self, trajectory: List[TrajectPoint]) -> TrajectoryFeatures:
        """Extraire les caractéristiques d'une trajectoire"""
        if not trajectory:
            return None
        
        try:
            # Lisser la trajectoire
            smooth_trajectory = self._smooth_trajectory(trajectory)
            
            # Calculs de base
            total_distance = 0
            speeds = []
            accelerations = []
            direction_changes = 0
            stop_count = 0
            previous_bearing = None
            
            # Parcourir les points
            for i in range(len(smooth_trajectory)):
                current_point = smooth_trajectory[i]
                speeds.append(current_point.vitesse)
                
                # Calcul de distance et direction
                if i > 0:
                    prev_point = smooth_trajectory[i-1]
                    distance = self._calculate_distance(
                        prev_point.latitude, prev_point.longitude,
                        current_point.latitude, current_point.longitude
                    )
                    total_distance += distance
                    
                    # Changements de direction
                    bearing = self._calculate_bearing(
                        prev_point.latitude, prev_point.longitude,
                        current_point.latitude, current_point.longitude
                    )
                    
                    if previous_bearing is not None:
                        bearing_diff = abs(bearing - previous_bearing)
                        if bearing_diff > 180:
                            bearing_diff = 360 - bearing_diff
                        
                        if bearing_diff > 45:  # Changement significatif
                            direction_changes += 1
                    
                    previous_bearing = bearing
                    
                    # Calcul d'accélération
                    if i > 1:
                        time_diff = (current_point.timestamp - prev_point.timestamp).total_seconds()
                        if time_diff > 0:
                            acceleration = (current_point.vitesse - prev_point.vitesse) / time_diff
                            accelerations.append(acceleration)
                
                # Détection d'arrêts
                if current_point.vitesse < 5:
                    stop_count += 1
            
            # Calculs statistiques
            avg_speed = np.mean(speeds) if speeds else 0
            max_speed = np.max(speeds) if speeds else 0
            min_speed = np.min(speeds) if speeds else 0
            speed_variance = np.var(speeds) if speeds else 0
            acceleration_variance = np.var(accelerations) if accelerations else 0
            
            # Durée totale
            total_duration = (trajectory[-1].timestamp - trajectory[0].timestamp).total_seconds()
            
            # Efficacité du trajet
            direct_distance = self._calculate_distance(
                trajectory[0].latitude, trajectory[0].longitude,
                trajectory[-1].latitude, trajectory[-1].longitude
            )
            path_efficiency = direct_distance / total_distance if total_distance > 0 else 0
            
            # Efficacité temporelle
            expected_time = total_distance / max(avg_speed, 1) * 3600  # en secondes
            time_efficiency = expected_time / total_duration if total_duration > 0 else 0
            
            # Détection de voyages nocturnes
            night_points = sum(1 for p in trajectory if p.timestamp.hour < 6 or p.timestamp.hour > 22)
            night_travel_ratio = night_points / len(trajectory)
            
            # Violations de vitesse
            speed_violations = sum(1 for s in speeds if s > 120)  # > 120 km/h
            
            # Indicateurs d'anomalies
            anomaly_indicators = {
                'speed_inconsistency': speed_variance / max(avg_speed, 1),
                'route_inefficiency': 1 - path_efficiency,
                'excessive_stops': stop_count / len(trajectory),
                'erratic_movement': direction_changes / len(trajectory),
                'acceleration_anomaly': acceleration_variance
            }
            
            return TrajectoryFeatures(
                mission_id=trajectory[0].mission_id,
                total_distance=total_distance,
                average_speed=avg_speed,
                max_speed=max_speed,
                min_speed=min_speed,
                speed_variance=speed_variance,
                total_duration=total_duration,
                stop_count=stop_count,
                direction_changes=direction_changes,
                acceleration_variance=acceleration_variance,
                path_efficiency=path_efficiency,
                time_efficiency=time_efficiency,
                out_of_bounds_ratio=0.0,  # À implémenter selon les zones autorisées
                night_travel_ratio=night_travel_ratio,
                speed_violations=speed_violations,
                anomaly_indicators=anomaly_indicators
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des caractéristiques: {e}")
            return None
    
    def _prepare_features_for_ml(self, features: TrajectoryFeatures) -> np.ndarray:
        """Préparer les caractéristiques pour les modèles ML"""
        feature_vector = [
            features.total_distance,
            features.average_speed,
            features.max_speed,
            features.min_speed,
            features.speed_variance,
            features.total_duration,
            features.stop_count,
            features.direction_changes,
            features.acceleration_variance,
            features.path_efficiency,
            features.time_efficiency,
            features.night_travel_ratio,
            features.speed_violations,
            features.anomaly_indicators['speed_inconsistency'],
            features.anomaly_indicators['route_inefficiency'],
            features.anomaly_indicators['excessive_stops'],
            features.anomaly_indicators['erratic_movement'],
            features.anomaly_indicators['acceleration_anomaly']
        ]
        
        return np.array(feature_vector).reshape(1, -1)
    
    async def train_models(self, training_data: List[TrajectoryFeatures] = None):
        """Entraîner les modèles avec les données disponibles"""
        try:
            if training_data is None:
                training_data = await self._get_training_data()
            
            if not training_data:
                logger.warning("Aucune donnée d'entraînement disponible")
                return False
            
            # Préparer les données d'entraînement
            X = []
            y = []
            
            for features in training_data:
                feature_vector = self._prepare_features_for_ml(features)
                X.append(feature_vector[0])
                
                # Déterminer si c'est une anomalie (basé sur les seuils)
                is_anomaly = self._is_anomaly_by_rules(features)
                y.append(1 if is_anomaly else 0)
            
            X = np.array(X)
            y = np.array(y)
            
            # Normaliser les données
            X_scaled = self.scalers['standard'].fit_transform(X)
            
            # Entraîner Isolation Forest
            self.models['isolation_forest'].fit(X_scaled)
            
            # Entraîner le classificateur d'anomalies
            if len(np.unique(y)) > 1:  # S'assurer qu'il y a des classes différentes
                X_train, X_test, y_train, y_test = train_test_split(
                    X_scaled, y, test_size=0.2, random_state=42
                )
                self.models['anomaly_classifier'].fit(X_train, y_train)
                
                # Évaluer le modèle
                score = self.models['anomaly_classifier'].score(X_test, y_test)
                logger.info(f"Précision du classificateur: {score:.2f}")
            
            # Sauvegarder les modèles
            await self._save_models()
            
            logger.info(f"Modèles entraînés avec {len(training_data)} échantillons")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement: {e}")
            return False
    
    def _is_anomaly_by_rules(self, features: TrajectoryFeatures) -> bool:
        """Déterminer si une trajectoire est anormale selon des règles"""
        # Règles simples pour étiqueter les données
        anomaly_indicators = 0
        
        if features.speed_variance > 500:  # Variance de vitesse élevée
            anomaly_indicators += 1
        
        if features.path_efficiency < 0.3:  # Trajet très inefficace
            anomaly_indicators += 1
        
        if features.night_travel_ratio > 0.5:  # Beaucoup de conduite nocturne
            anomaly_indicators += 1
        
        if features.speed_violations > 10:  # Nombreuses violations
            anomaly_indicators += 1
        
        if features.stop_count > len(features.anomaly_indicators) * 0.3:  # Trop d'arrêts
            anomaly_indicators += 1
        
        return anomaly_indicators >= 2
    
    async def _get_training_data(self) -> List[TrajectoryFeatures]:
        """Récupérer les données d'entraînement depuis la base"""
        try:
            # Récupérer les trajectoires des 30 derniers jours
            cutoff_date = datetime.now() - timedelta(days=30)
            
            missions = self.db.query(Mission).filter(
                Mission.dateDebut >= cutoff_date
            ).limit(100).all()
            
            training_features = []
            
            for mission in missions:
                # Récupérer les points de trajectoire
                trajets = self.db.query(Trajet).filter(
                    Trajet.mission_id == mission.id
                ).order_by(Trajet.timestamp).all()
                
                if len(trajets) < 5:
                    continue
                
                # Convertir en TrajectPoint
                trajectory = []
                for trajet in trajets:
                    point = TrajectPoint(
                        id=trajet.id,
                        mission_id=mission.id,
                        timestamp=trajet.timestamp,
                        latitude=float(trajet.latitude),
                        longitude=float(trajet.longitude),
                        vitesse=float(trajet.vitesse),
                        mission_start=mission.dateDebut,
                        mission_end=mission.dateFin
                    )
                    trajectory.append(point)
                
                # Extraire les caractéristiques
                features = self.extract_trajectory_features(trajectory)
                if features:
                    training_features.append(features)
            
            logger.info(f"Données d'entraînement récupérées: {len(training_features)} trajectoires")
            return training_features
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données d'entraînement: {e}")
            return []
    
    async def detect_anomalies(self, trajectory: List[TrajectPoint]) -> List[AnomalyScore]:
        """Détecter les anomalies dans une trajectoire"""
        try:
            if not trajectory:
                return []
            
            # Extraire les caractéristiques
            features = self.extract_trajectory_features(trajectory)
            if not features:
                return []
            
            anomaly_scores = []
            
            # Préparer les données pour ML
            X = self._prepare_features_for_ml(features)
            
            # Vérifier si les scalers sont entraînés
            if hasattr(self.scalers['standard'], 'scale_'):
                X_scaled = self.scalers['standard'].transform(X)
            else:
                X_scaled = X
            
            # Détection par Isolation Forest
            if hasattr(self.models['isolation_forest'], 'decision_function'):
                isolation_score = self.models['isolation_forest'].decision_function(X_scaled)[0]
                isolation_anomaly = self.models['isolation_forest'].predict(X_scaled)[0] == -1
                
                if isolation_anomaly:
                    anomaly_scores.append(AnomalyScore(
                        anomaly_type="ISOLATION_FOREST_ANOMALY",
                        score=abs(isolation_score),
                        confidence=min(abs(isolation_score) * 2, 1.0),
                        severity="HIGH" if abs(isolation_score) > 0.5 else "MEDIUM",
                        details={"isolation_score": isolation_score, "features": features.__dict__},
                        timestamp=datetime.now()
                    ))
            
            # Détection par règles spécifiques
            rule_based_anomalies = self._detect_rule_based_anomalies(features, trajectory)
            anomaly_scores.extend(rule_based_anomalies)
            
            # Détection par analyse des patterns
            pattern_anomalies = self._detect_pattern_anomalies(trajectory)
            anomaly_scores.extend(pattern_anomalies)
            
            # Détection par analyse temporelle
            temporal_anomalies = self._detect_temporal_anomalies(trajectory)
            anomaly_scores.extend(temporal_anomalies)
            
            return anomaly_scores
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection d'anomalies: {e}")
            return []
    
    def _detect_rule_based_anomalies(self, features: TrajectoryFeatures, trajectory: List[TrajectPoint]) -> List[AnomalyScore]:
        """Détection d'anomalies basée sur des règles"""
        anomalies = []
        
        # Anomalie de vitesse
        if features.max_speed > 150:
            anomalies.append(AnomalyScore(
                anomaly_type="EXCESSIVE_SPEED",
                score=min(features.max_speed / 200, 1.0),
                confidence=0.9,
                severity="CRITICAL" if features.max_speed > 180 else "HIGH",
                details={"max_speed": features.max_speed, "violations": features.speed_violations},
                timestamp=datetime.now()
            ))
        
        # Anomalie d'efficacité de trajet
        if features.path_efficiency < 0.3:
            anomalies.append(AnomalyScore(
                anomaly_type="ROUTE_INEFFICIENCY",
                score=1 - features.path_efficiency,
                confidence=0.8,
                severity="MEDIUM" if features.path_efficiency > 0.1 else "HIGH",
                details={"efficiency": features.path_efficiency, "total_distance": features.total_distance},
                timestamp=datetime.now()
            ))
        
        # Anomalie de conduite nocturne
        if features.night_travel_ratio > 0.6:
            anomalies.append(AnomalyScore(
                anomaly_type="EXCESSIVE_NIGHT_TRAVEL",
                score=features.night_travel_ratio,
                confidence=0.7,
                severity="MEDIUM",
                details={"night_ratio": features.night_travel_ratio},
                timestamp=datetime.now()
            ))
        
        # Anomalie d'arrêts excessifs
        excessive_stops_ratio = features.stop_count / len(trajectory)
        if excessive_stops_ratio > 0.4:
            anomalies.append(AnomalyScore(
                anomaly_type="EXCESSIVE_STOPS",
                score=excessive_stops_ratio,
                confidence=0.8,
                severity="MEDIUM",
                details={"stop_count": features.stop_count, "stop_ratio": excessive_stops_ratio},
                timestamp=datetime.now()
            ))
        
        return anomalies
    
    def _detect_pattern_anomalies(self, trajectory: List[TrajectPoint]) -> List[AnomalyScore]:
        """Détection d'anomalies de patterns"""
        anomalies = []
        
        if len(trajectory) < 5:
            return anomalies
        
        try:
            # Analyser les patterns de vitesse
            speeds = [p.vitesse for p in trajectory]
            speed_pattern_score = self._analyze_speed_patterns(speeds)
            
            if speed_pattern_score > 0.7:
                anomalies.append(AnomalyScore(
                    anomaly_type="ABNORMAL_SPEED_PATTERN",
                    score=speed_pattern_score,
                    confidence=0.75,
                    severity="MEDIUM",
                    details={"pattern_score": speed_pattern_score},
                    timestamp=datetime.now()
                ))
            
            # Analyser les patterns de mouvement
            movement_pattern_score = self._analyze_movement_patterns(trajectory)
            
            if movement_pattern_score > 0.6:
                anomalies.append(AnomalyScore(
                    anomaly_type="ABNORMAL_MOVEMENT_PATTERN",
                    score=movement_pattern_score,
                    confidence=0.7,
                    severity="MEDIUM",
                    details={"movement_score": movement_pattern_score},
                    timestamp=datetime.now()
                ))
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Erreur dans la détection de patterns: {e}")
            return []
    
    def _analyze_speed_patterns(self, speeds: List[float]) -> float:
        """Analyser les patterns de vitesse"""
        if len(speeds) < 3:
            return 0.0
        
        # Calculer les changements de vitesse
        speed_changes = []
        for i in range(1, len(speeds)):
            change = abs(speeds[i] - speeds[i-1])
            speed_changes.append(change)
        
        # Détecter les changements brusques
        mean_change = np.mean(speed_changes)
        std_change = np.std(speed_changes)
        
        # Compter les changements anormaux
        abnormal_changes = sum(1 for change in speed_changes if change > mean_change + 2 * std_change)
        
        # Score basé sur le ratio de changements anormaux
        pattern_score = abnormal_changes / len(speed_changes)
        
        return min(pattern_score, 1.0)
    
    def _analyze_movement_patterns(self, trajectory: List[TrajectPoint]) -> float:
        """Analyser les patterns de mouvement"""
        if len(trajectory) < 4:
            return 0.0
        
        try:
            # Calculer les distances entre points consécutifs
            distances = []
            for i in range(1, len(trajectory)):
                dist = self._calculate_distance(
                    trajectory[i-1].latitude, trajectory[i-1].longitude,
                    trajectory[i].latitude, trajectory[i].longitude
                )
                distances.append(dist)
            
            # Analyser la régularité des mouvements
            if len(distances) > 2:
                distances_std = np.std(distances)
                distances_mean = np.mean(distances)
                
                # Score basé sur la variabilité
                if distances_mean > 0:
                    variability_score = distances_std / distances_mean
                    return min(variability_score, 1.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Erreur dans l'analyse des mouvements: {e}")
            return 0.0
    
    def _detect_temporal_anomalies(self, trajectory: List[TrajectPoint]) -> List[AnomalyScore]:
        """Détection d'anomalies temporelles"""
        anomalies = []
        
        if len(trajectory) < 2:
            return anomalies
        
        try:
            # Analyser les intervalles de temps
            time_intervals = []
            for i in range(1, len(trajectory)):
                interval = (trajectory[i].timestamp - trajectory[i-1].timestamp).total_seconds()
                time_intervals.append(interval)
            
            # Détecter les gaps temporels anormaux
            if time_intervals:
                mean_interval = np.mean(time_intervals)
                std_interval = np.std(time_intervals)
                
                # Chercher les gaps anormaux
                for i, interval in enumerate(time_intervals):
                    if interval > mean_interval + 3 * std_interval and interval > 3600:  # Plus d'1 heure
                        anomalies.append(AnomalyScore(
                            anomaly_type="TEMPORAL_GAP",
                            score=min(interval / 7200, 1.0),  # Normaliser sur 2 heures
                            confidence=0.8,
                            severity="HIGH" if interval > 7200 else "MEDIUM",
                            details={"gap_seconds": interval, "gap_position": i},
                            timestamp=datetime.now(),
                            affected_points=[trajectory[i].id, trajectory[i+1].id]
                        ))
            
            # Détecter les déplacements en dehors des heures normales
            night_points = [p for p in trajectory if p.timestamp.hour < 6 or p.timestamp.hour > 22]
            if len(night_points) > len(trajectory) * 0.7:
                anomalies.append(AnomalyScore(
                    anomaly_type="OUT_OF_HOURS_MOVEMENT",
                    score=len(night_points) / len(trajectory),
                    confidence=0.9,
                    severity="MEDIUM",
                    details={"night_points": len(night_points), "total_points": len(trajectory)},
                    timestamp=datetime.now()
                ))
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Erreur dans la détection temporelle: {e}")
            return []
    
    async def _save_models(self):
        """Sauvegarder les modèles entraînés"""
        try:
            # Sauvegarder chaque modèle
            for name, model in self.models.items():
                # On ne sauvegarde que les modèles qui ont une méthode 'fit'
                if hasattr(model, 'fit') or hasattr(model, 'n_estimators'):
                    model_path = os.path.join(self.models_path, f"{name}.pkl")
                    with open(model_path, 'wb') as f:
                        pickle.dump(model, f)
            
            # Sauvegarder les scalers
            for name, scaler in self.scalers.items():
                if hasattr(scaler, 'scale_'):  # Vérifier si le scaler a été entraîné
                    scaler_path = os.path.join(self.models_path, f"{name}_scaler.pkl")
                    with open(scaler_path, 'wb') as f:
                        pickle.dump(scaler, f)
            
            logger.info("Modèles sauvegardés avec succès.")
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des modèles: {e}")