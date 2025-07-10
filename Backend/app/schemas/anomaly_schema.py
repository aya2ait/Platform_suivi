# schemas/anomaly_schema.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class AnomalyType(str, Enum):
    RETOUR_PREMATURE = "RETOUR_PREMATURE"
    TRAJET_DIVERGENT = "TRAJET_DIVERGENT"
    ARRET_PROLONGE = "ARRET_PROLONGE"
    VITESSE_EXCESSIVE = "VITESSE_EXCESSIVE"
    ZONE_INTERDITE = "ZONE_INTERDITE"
    CONSOMMATION_ANORMALE = "CONSOMMATION_ANORMALE"
    DOUBLE_TRAJET = "DOUBLE_TRAJET"
    TRAJET_PERSONNEL = "TRAJET_PERSONNEL"

class AnomalyConfig(BaseModel):
    type: AnomalyType
    probability: float = Field(ge=0.0, le=1.0, description="Probabilité d'occurrence (0-1)")
    severity: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH")
    parameters: Dict[str, Any] = Field(default_factory=dict)

class AnomalyRequest(BaseModel):
    mission_id: int
    anomaly_types: List[AnomalyConfig]
    force_generate: bool = Field(default=False, description="Forcer la génération même si probabilité faible")

class AnomalyResponse(BaseModel):
    id: int
    mission_id: int
    type: AnomalyType
    description: str
    timestamp: datetime
    latitude: float
    longitude: float
    severity: str
    details: Dict[str, Any]
    detected_at: datetime

class SimulationConfig(BaseModel):
    enable_anomalies: bool = Field(default=True)
    anomaly_frequency: float = Field(default=0.3, ge=0.0, le=1.0)
    default_anomalies: List[AnomalyConfig] = Field(default_factory=list)