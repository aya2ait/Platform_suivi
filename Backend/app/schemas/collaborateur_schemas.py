# app/schemas/collaborateur_schemas.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal

# ====================================================================
# Schémas pour les réponses des missions d'un collaborateur
# ====================================================================

class VehiculeResponse(BaseModel):
    """Schéma pour les informations du véhicule"""
    id: int
    immatriculation: str
    marque: str
    modele: Optional[str] = None
    
    class Config:
        from_attributes = True

class DirecteurResponse(BaseModel):
    """Schéma pour les informations du directeur"""
    id: int
    nom: str
    prenom: str
    
    class Config:
        from_attributes = True

class AffectationResponse(BaseModel):
    """Schéma pour les informations d'affectation"""
    id: int
    dejeuner: int = 0
    dinner: int = 0
    accouchement: int = 0
    montantCalcule: Decimal = Field(default=Decimal('0.00'))
    created_at: datetime
    
    class Config:
        from_attributes = True

class TrajetResponse(BaseModel):
    """Schéma pour les informations de trajet"""
    id: int
    timestamp: datetime
    latitude: Decimal
    longitude: Decimal
    vitesse: Decimal = Field(default=Decimal('0.00'))
    
    class Config:
        from_attributes = True

class AnomalieResponse(BaseModel):
    """Schéma pour les informations d'anomalie"""
    id: int
    type: str
    description: Optional[str] = None
    dateDetection: datetime
    
    class Config:
        from_attributes = True

class MissionCollaborateurResponse(BaseModel):
    """Schéma pour les missions d'un collaborateur"""
    id: int
    objet: str
    dateDebut: datetime
    dateFin: datetime
    moyenTransport: Optional[str] = None
    trajet_predefini: Optional[str] = None
    statut: str = "CREEE"
    created_at: datetime
    updated_at: datetime
    
    # Relations
    vehicule: Optional[VehiculeResponse] = None
    directeur: DirecteurResponse
    affectation: Optional[AffectationResponse] = None
    trajets: List[TrajetResponse] = []
    anomalies: List[AnomalieResponse] = []
    
    class Config:
        from_attributes = True

class MissionListResponse(BaseModel):
    """Schéma pour la liste des missions avec pagination"""
    missions: List[MissionCollaborateurResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    
class MissionDetailResponse(BaseModel):
    """Schéma détaillé pour une mission spécifique"""
    mission: MissionCollaborateurResponse
    
class MissionStatsResponse(BaseModel):
    """Schéma pour les statistiques des missions d'un collaborateur"""
    total_missions: int
    missions_en_cours: int
    missions_terminees: int
    missions_annulees: int
    total_indemnites: Decimal
    
class CollaborateurProfileResponse(BaseModel):
    """Schéma pour le profil du collaborateur"""
    id: int
    nom: str
    matricule: str
    disponible: bool
    
    # Relations
    type_collaborateur: str
    direction: str
    
    class Config:
        from_attributes = True

# ====================================================================
# Schémas pour les requêtes/filtres
# ====================================================================

class MissionFilterRequest(BaseModel):
    """Schéma pour les filtres de missions"""
    statut: Optional[str] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    
class MissionSearchRequest(BaseModel):
    """Schéma pour la recherche de missions"""
    query: str = Field(..., min_length=1, max_length=255)
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)