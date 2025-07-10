# app/schemas/map_schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

class TrajetPoint(BaseModel):
    """Point de trajet avec coordonnées GPS"""
    id: int
    timestamp: datetime
    latitude: float = Field(..., ge=-90, le=90, description="Latitude entre -90 et 90")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude entre -180 et 180")
    vitesse: Optional[float] = Field(default=0.0, ge=0, description="Vitesse en km/h")
    
    class Config:
        from_attributes = True

class TrajetResponse(BaseModel):
    """Trajet complet d'une mission"""
    mission_id: int
    points: List[TrajetPoint]
    distance_totale: Optional[float] = Field(default=0.0, description="Distance totale en km")
    duree_totale: Optional[int] = Field(default=0, description="Durée totale en minutes")
    vitesse_moyenne: Optional[float] = Field(default=0.0, description="Vitesse moyenne en km/h")
    
    class Config:
        from_attributes = True

class MissionMapInfo(BaseModel):
    """Informations d'une mission pour l'affichage sur carte"""
    id: int
    objet: str
    statut: str
    dateDebut: datetime
    dateFin: datetime
    moyenTransport: Optional[str] = None
    trajet_predefini: Optional[str] = None
    
    # Informations du directeur
    directeur_nom: str
    directeur_prenom: str
    direction_nom: str
    
    # Informations du véhicule (si applicable)
    vehicule_immatriculation: Optional[str] = None
    vehicule_marque: Optional[str] = None
    vehicule_modele: Optional[str] = None
    
    # Collaborateurs affectés
    collaborateurs: List[Dict[str, Any]] = []
    
    # Points de trajet
    trajet_points: List[TrajetPoint] = []
    
    # Anomalies détectées
    anomalies: List[Dict[str, Any]] = []
    
    class Config:
        from_attributes = True

class MissionMapFilter(BaseModel):
    """Filtres pour l'affichage des missions sur carte"""
    statut: Optional[List[str]] = Field(default=None, description="Filtrer par statut")
    direction_id: Optional[int] = Field(default=None, description="Filtrer par direction")
    date_debut: Optional[datetime] = Field(default=None, description="Date de début minimum")
    date_fin: Optional[datetime] = Field(default=None, description="Date de fin maximum")
    avec_anomalies: Optional[bool] = Field(default=None, description="Missions avec anomalies uniquement")
    moyen_transport: Optional[str] = Field(default=None, description="Filtrer par moyen de transport")
    vehicule_id: Optional[int] = Field(default=None, description="Filtrer par véhicule")

class MapBounds(BaseModel):
    """Limites géographiques de la carte"""
    nord: float = Field(..., ge=-90, le=90)
    sud: float = Field(..., ge=-90, le=90)
    est: float = Field(..., ge=-180, le=180)
    ouest: float = Field(..., ge=-180, le=180)

class MissionMapResponse(BaseModel):
    """Réponse complète pour l'affichage des missions sur carte"""
    missions: List[MissionMapInfo]
    bounds: Optional[MapBounds] = None
    total_missions: int
    missions_actives: int
    missions_terminees: int
    missions_avec_anomalies: int
    
    class Config:
        from_attributes = True

class AnomalieMapInfo(BaseModel):
    """Informations d'anomalie pour l'affichage sur carte"""
    id: int
    mission_id: int
    type: str
    description: Optional[str] = None
    dateDetection: datetime
    
    # Position de l'anomalie (si disponible)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    class Config:
        from_attributes = True

class TrajetStatistics(BaseModel):
    """Statistiques d'un trajet"""
    distance_totale: float
    duree_totale: int  # en minutes
    vitesse_moyenne: float
    vitesse_maximale: float
    nombre_arrets: int
    temps_arret_total: int  # en minutes
    consommation_estimee: Optional[float] = None  # en litres

class MissionAnalytics(BaseModel):
    """Analytics d'une mission pour l'affichage détaillé"""
    mission_id: int
    trajet_statistics: TrajetStatistics
    anomalies_detectees: List[AnomalieMapInfo]
    ecart_trajet_prevu: Optional[float] = Field(default=None, description="Écart en km par rapport au trajet prévu")
    respect_horaires: bool = Field(default=True, description="Respect des horaires prévus")
    zones_visitees: List[str] = Field(default_factory=list, description="Zones géographiques visitées")

class LiveTrackingUpdate(BaseModel):
    """Mise à jour en temps réel du suivi"""
    mission_id: int
    timestamp: datetime
    latitude: float
    longitude: float
    vitesse: float
    statut: str
    
    class Config:
        from_attributes = True

# Schémas pour la configuration de la carte
class MapConfiguration(BaseModel):
    """Configuration de la carte"""
    centre_latitude: float = 31.7917  # Centre du Maroc
    centre_longitude: float = -7.0926
    zoom_initial: int = 6
    couches_disponibles: List[str] = ["satellite", "terrain", "roadmap"]
    couleurs_statut: Dict[str, str] = {
        "CREEE": "#FFA500",
        "EN_COURS": "#0000FF", 
        "TERMINEE": "#008000",
        "ANNULEE": "#FF0000"
    }
    
class MapLayerConfig(BaseModel):
    """Configuration des couches de la carte"""
    missions_actives: bool = True
    trajets_complets: bool = True
    anomalies: bool = True
    zones_interdites: bool = False
    points_interesse: bool = False