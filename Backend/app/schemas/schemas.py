from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# ====================================================================
# Pydantic Schemas
# ====================================================================

# Base schemas for common attributes
class BaseSchema(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # updated from orm_mode = True

# Schemas for Mission
class MissionBase(BaseModel):
    objet: str
    dateDebut: datetime
    dateFin: datetime
    moyenTransport: Optional[str] = None
    vehicule_id: Optional[int] = None
    directeur_id: int

class MissionCreate(MissionBase):
    pass

class MissionResponse(MissionBase):
    id: int
    statut: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Schemas for Collaborator assignment
class CollaborateurAssign(BaseModel):
    matricule: str = Field(..., description="Matricule du collaborateur à affecter")

class AssignCollaboratorsRequest(BaseModel):
    collaborateurs: List[CollaborateurAssign] = Field(..., min_length=1, description="Liste des matricules des collaborateurs à affecter")

class AffectationResponse(BaseModel):
    id: int
    mission_id: int
    collaborateur_id: int
    dejeuner: int
    dinner: int
    accouchement: int
    montantCalcule: float # Use float for Pydantic for Decimal fields
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
