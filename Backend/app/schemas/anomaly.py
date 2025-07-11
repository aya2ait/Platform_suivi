from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum

class AnomalyType(str, Enum):
    """Types d'anomalies possibles"""
    RETOUR_PREMATURE = "retour_premature"
    TRAJET_DIVERGENT = "trajet_divergent"
    ARRET_NON_AUTORISE = "arret_non_autorise"
    VITESSE_ANORMALE = "vitesse_anormale"
    DEPLACEMENT_HORS_HEURES = "deplacement_hors_heures"
    SORTIE_ZONE_AUTORISEE = "sortie_zone_autorisee"

class AnomalyRule(BaseModel):
    """Règle de configuration pour un type d'anomalie"""
    probability: float = Field(..., ge=0.0, le=1.0, description="Probabilité d'occurrence (0-1)")
    severity_range: tuple[float, float] = Field(..., description="Plage de sévérité (min, max)")
    parameters: Dict[str, Any] = Field(..., description="Paramètres spécifiques à l'anomalie")
    
    @validator('severity_range')
    def validate_severity_range(cls, v):
        if len(v) != 2 or v[0] >= v[1]:
            raise ValueError('severity_range doit être un tuple (min, max) avec min < max')
        if v[0] < 0 or v[1] > 1:
            raise ValueError('severity_range doit être entre 0 et 1')
        return v

class AnomalyConfig(BaseModel):
    """Configuration globale pour l'injection d'anomalies"""
    injection_probability: float = Field(0.3, ge=0.0, le=1.0, description="Probabilité globale d'injection")
    anomaly_types: Dict[AnomalyType, AnomalyRule] = Field(..., description="Règles par type d'anomalie")
    max_anomalies_per_mission: int = Field(3, ge=1, le=10, description="Nombre maximum d'anomalies par mission")
    cooldown_period_hours: int = Field(24, ge=1, description="Période de refroidissement entre injections (heures)")
    
    @validator('anomaly_types')
    def validate_anomaly_types(cls, v):
        if not v:
            raise ValueError('Au moins un type d\'anomalie doit être configuré')
        return v

class TrajectPoint(BaseModel):
    """Point de trajectoire"""
    id: Optional[int] = Field(None, description="ID du point (None pour les nouveaux points)")
    mission_id: int = Field(..., description="ID de la mission")
    timestamp: datetime = Field(..., description="Horodatage du point")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude GPS")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude GPS")
    vitesse: float = Field(..., ge=0.0, le=200.0, description="Vitesse en km/h")
    mission_start: datetime = Field(..., description="Début de la mission")
    mission_end: datetime = Field(..., description="Fin de la mission")
    
    @validator('timestamp')
    def validate_timestamp(cls, v, values):
        if 'mission_start' in values and 'mission_end' in values:
            if not (values['mission_start'] <= v <= values['mission_end']):
                raise ValueError('timestamp doit être entre mission_start et mission_end')
        return v

class AnomalyInjectionResult(BaseModel):
    """Résultat d'injection d'anomalies"""
    mission_id: int = Field(..., description="ID de la mission")
    success: bool = Field(..., description="Succès de l'injection")
    anomalies_injected: List[str] = Field(default=[], description="Types d'anomalies injectées")
    original_points_count: int = Field(..., ge=0, description="Nombre de points originaux")
    modified_points_count: int = Field(..., ge=0, description="Nombre de points après modification")
    injection_timestamp: datetime = Field(default_factory=datetime.now, description="Horodatage de l'injection")
    error_message: Optional[str] = Field(None, description="Message d'erreur si applicable")
    
    @validator('modified_points_count')
    def validate_modified_points_count(cls, v, values):
        if 'original_points_count' in values and v < values['original_points_count']:
            raise ValueError('modified_points_count ne peut pas être inférieur à original_points_count')
        return v

class BatchInjectionRequest(BaseModel):
    """Requête d'injection en lot"""
    mission_ids: Optional[List[int]] = Field(None, description="IDs des missions (None pour toutes)")
    config_override: Optional[AnomalyConfig] = Field(None, description="Configuration personnalisée")
    dry_run: bool = Field(False, description="Simulation sans sauvegarde")
    max_concurrent: int = Field(5, ge=1, le=20, description="Nombre maximum de traitements simultanés")

class BatchInjectionResponse(BaseModel):
    """Réponse d'injection en lot"""
    total_processed: int = Field(..., ge=0, description="Total de missions traitées")
    successful_injections: int = Field(..., ge=0, description="Injections réussies")
    failed_injections: int = Field(..., ge=0, description="Injections échouées")
    results: List[AnomalyInjectionResult] = Field(..., description="Résultats détaillés")
    processing_time_seconds: float = Field(..., ge=0, description="Temps de traitement total")
    
    @validator('total_processed')
    def validate_total_processed(cls, v, values):
        if 'successful_injections' in values and 'failed_injections' in values:
            if v != values['successful_injections'] + values['failed_injections']:
                raise ValueError('total_processed doit égaler successful_injections + failed_injections')
        return v

class ContaminationStatus(BaseModel):
    """Statut de contamination d'une mission"""
    mission_id: int = Field(..., description="ID de la mission")
    is_contaminated: bool = Field(..., description="Mission contaminée")
    contamination_types: List[str] = Field(default=[], description="Types de contamination")
    contamination_date: Optional[datetime] = Field(None, description="Date de contamination")
    original_points_count: Optional[int] = Field(None, ge=0, description="Nombre de points originaux")
    contaminated_points_count: Optional[int] = Field(None, ge=0, description="Nombre de points contaminés")

class CleanupRequest(BaseModel):
    """Requête de nettoyage"""
    mission_ids: Optional[List[int]] = Field(None, description="IDs des missions à nettoyer (None pour toutes)")
    confirmation: bool = Field(False, description="Confirmation du nettoyage")
    backup_before_cleanup: bool = Field(True, description="Créer une sauvegarde avant nettoyage")

class CleanupResponse(BaseModel):
    """Réponse de nettoyage"""
    missions_cleaned: int = Field(..., ge=0, description="Nombre de missions nettoyées")
    anomalies_removed: int = Field(..., ge=0, description="Nombre d'anomalies supprimées")
    backup_created: bool = Field(..., description="Sauvegarde créée")
    backup_path: Optional[str] = Field(None, description="Chemin de la sauvegarde")
    cleanup_timestamp: datetime = Field(default_factory=datetime.now, description="Horodatage du nettoyage")

class AnomalyStatistics(BaseModel):
    """Statistiques des anomalies"""
    total_missions: int = Field(..., ge=0, description="Total de missions")
    contaminated_missions: int = Field(..., ge=0, description="Missions contaminées")
    contamination_rate: float = Field(..., ge=0.0, le=1.0, description="Taux de contamination")
    anomaly_type_counts: Dict[str, int] = Field(..., description="Nombre par type d'anomalie")
    average_anomalies_per_mission: float = Field(..., ge=0.0, description="Moyenne d'anomalies par mission")
    last_injection_date: Optional[datetime] = Field(None, description="Date de dernière injection")

class ConfigUpdateRequest(BaseModel):
    """Requête de mise à jour de configuration"""
    new_config: AnomalyConfig = Field(..., description="Nouvelle configuration")
    apply_immediately: bool = Field(False, description="Appliquer immédiatement")
    backup_current_config: bool = Field(True, description="Sauvegarder la configuration actuelle")

class ConfigUpdateResponse(BaseModel):
    """Réponse de mise à jour de configuration"""
    success: bool = Field(..., description="Succès de la mise à jour")
    previous_config: Optional[AnomalyConfig] = Field(None, description="Configuration précédente")
    new_config: AnomalyConfig = Field(..., description="Nouvelle configuration")
    update_timestamp: datetime = Field(default_factory=datetime.now, description="Horodatage de la mise à jour")

class TrajectoryValidationRequest(BaseModel):
    """Requête de validation de trajectoire"""
    mission_id: int = Field(..., description="ID de la mission")
    check_anomalies: bool = Field(True, description="Vérifier les anomalies")
    check_continuity: bool = Field(True, description="Vérifier la continuité")
    check_speed_limits: bool = Field(True, description="Vérifier les limites de vitesse")
    max_speed_kmh: float = Field(150.0, ge=0.0, description="Vitesse maximale autorisée")

class TrajectoryValidationResponse(BaseModel):
    """Réponse de validation de trajectoire"""
    mission_id: int = Field(..., description="ID de la mission")
    is_valid: bool = Field(..., description="Trajectoire valide")
    validation_errors: List[str] = Field(default=[], description="Erreurs de validation")
    validation_warnings: List[str] = Field(default=[], description="Avertissements")
    points_analyzed: int = Field(..., ge=0, description="Nombre de points analysés")
    anomalies_detected: List[str] = Field(default=[], description="Anomalies détectées")
    validation_timestamp: datetime = Field(default_factory=datetime.now, description="Horodatage de la validation")

# Schémas pour les paramètres spécifiques des anomalies
class EarlyReturnParameters(BaseModel):
    """Paramètres pour anomalie de retour prématuré"""
    early_return_ratio: tuple[float, float] = Field((0.3, 0.7), description="Ratio de retour prématuré")
    detour_distance_km: tuple[float, float] = Field((5, 15), description="Distance de détour en km")

class RouteDeviationParameters(BaseModel):
    """Paramètres pour anomalie de déviation de trajet"""
    deviation_distance_km: tuple[float, float] = Field((2, 10), description="Distance de déviation en km")
    deviation_duration_min: tuple[float, float] = Field((15, 60), description="Durée de déviation en minutes")

class UnauthorizedStopParameters(BaseModel):
    """Paramètres pour anomalie d'arrêt non autorisé"""
    stop_duration_min: tuple[float, float] = Field((10, 120), description="Durée d'arrêt en minutes")
    stop_frequency: tuple[int, int] = Field((1, 3), description="Fréquence d'arrêts")

class AbnormalSpeedParameters(BaseModel):
    """Paramètres pour anomalie de vitesse anormale"""
    speed_factor: tuple[float, float] = Field((0.1, 2.5), description="Facteur de vitesse")
    duration_min: tuple[float, float] = Field((5, 30), description="Durée en minutes")

class OutOfHoursParameters(BaseModel):
    """Paramètres pour anomalie de déplacement hors heures"""
    early_start_hours: tuple[float, float] = Field((1, 3), description="Heures de début prématuré")
    late_end_hours: tuple[float, float] = Field((1, 4), description="Heures de fin tardive")

class GeofenceParameters(BaseModel):
    """Paramètres pour anomalie de sortie de zone autorisée"""
    zone_breach_distance_km: tuple[float, float] = Field((1, 5), description="Distance de sortie de zone")
    breach_duration_min: tuple[float, float] = Field((10, 60), description="Durée de sortie de zone")
    authorized_zones: List[Dict[str, float]] = Field(default=[], description="Zones autorisées (lat, lon, rayon)")

# Union type pour tous les paramètres d'anomalies
AnomalyParameters = Union[
    EarlyReturnParameters,
    RouteDeviationParameters,
    UnauthorizedStopParameters,
    AbnormalSpeedParameters,
    OutOfHoursParameters,
    GeofenceParameters
]
