from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class TrajectPoint:
    """Point de trajet avec coordonnées GPS"""
    latitude: float
    longitude: float
    timestamp: datetime
    vitesse: float
    mission_id: int

@dataclass
class Mission:
    """Informations de mission"""
    id: int
    objet: str
    statut: str
    dateDebut: datetime
    dateFin: datetime
    trajet_predefini: Optional[str]
    vehicule_id: Optional[int]