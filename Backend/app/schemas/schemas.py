from datetime import datetime
from typing import List, Optional, Union, Any
# Import field_validator from pydantic.fields
from pydantic import BaseModel, Field, field_validator
import json

# ====================================================================
# Pydantic Schemas
# ====================================================================

class GeoPoint(BaseModel):
    latitude: float
    longitude: float

# Base schemas for common attributes
class BaseSchema(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# --- NEW: Schema for Vehicule Response (Adjusted to allow nullable 'modele') ---
class VehiculeResponse(BaseModel):
    id: int
    immatriculation: str
    marque: str
    modele: Optional[str] = None # Corrected: Made 'modele' optional to match SQLAlchemy model's nullability
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schemas for Mission
class MissionBase(BaseModel):
    objet: str
    dateDebut: datetime
    dateFin: datetime
    moyenTransport: Optional[str] = None
    vehicule_id: Optional[int] = None
    directeur_id: int
    statut: Optional[str] = "CREEE"  # Default value
    
    class Config:
        from_attributes = True

# --- MissionCreate and MissionUpdate (for incoming requests) ---
class MissionCreate(MissionBase):
    # Accepter Union de types pour permettre JSON string ou liste
    trajet_predefini: Optional[Union[List[GeoPoint], str]] = None
    
    @field_validator('trajet_predefini', mode='before')
    def convert_trajet_to_json_string_for_db(cls, v):
        if v is None:
            return None
        
        # Si c'est déjà une chaîne vide ou null
        if isinstance(v, str) and v.strip() == "":
            return None
        
        if isinstance(v, str):
            try:
                parsed_v = json.loads(v)
                if isinstance(parsed_v, list):
                    v = parsed_v
                else:
                    raise ValueError('If trajet_predefini is a string, it must be a JSON list.')
            except json.JSONDecodeError:
                raise ValueError('trajet_predefini string must be valid JSON.')

        if isinstance(v, list):
            if not v:
                return None
            
            list_of_dicts = []
            for item in v:
                if isinstance(item, dict):
                    if 'latitude' not in item or 'longitude' not in item:
                        raise ValueError('Each point must have latitude and longitude')
                    list_of_dicts.append({
                        'latitude': float(item['latitude']),
                        'longitude': float(item['longitude'])
                    })
                elif isinstance(item, GeoPoint):
                    list_of_dicts.append({
                        'latitude': item.latitude,
                        'longitude': item.longitude
                    })
                else:
                    raise ValueError(f'Invalid item in trajet_predefini: expected dict or GeoPoint, got {type(item)}')
            
            return json.dumps(list_of_dicts)
        
        raise ValueError('trajet_predefini must be a list of GeoPoints, a JSON string, or null')

# Update schema for updates - similar to create, but all fields are Optional
class MissionUpdate(BaseModel):
    objet: Optional[str] = None
    dateDebut: Optional[datetime] = None
    dateFin: Optional[datetime] = None
    moyenTransport: Optional[str] = None
    vehicule_id: Optional[int] = None
    directeur_id: Optional[int] = None
    statut: Optional[str] = None
    # Accepter Union de types pour permettre JSON string ou liste
    trajet_predefini: Optional[Union[List[GeoPoint], str]] = None
    
    @field_validator('trajet_predefini', mode='before')
    def convert_trajet_to_json_string_for_db_update(cls, v):
        if v is None:
            return None
        
        # Si c'est déjà une chaîne vide ou null
        if isinstance(v, str) and v.strip() == "":
            return None
        
        if isinstance(v, str):
            try:
                parsed_v = json.loads(v)
                if isinstance(parsed_v, list):
                    v = parsed_v
                else:
                    raise ValueError('If trajet_predefini is a string, it must be a JSON list.')
            except json.JSONDecodeError:
                raise ValueError('trajet_predefini string must be valid JSON.')

        if isinstance(v, list):
            if not v:
                return None
            
            list_of_dicts = []
            for item in v:
                if isinstance(item, dict):
                    if 'latitude' not in item or 'longitude' not in item:
                        raise ValueError('Each point must have latitude and longitude')
                    list_of_dicts.append({
                        'latitude': float(item['latitude']),
                        'longitude': float(item['longitude'])
                    })
                elif isinstance(item, GeoPoint):
                    list_of_dicts.append({
                        'latitude': item.latitude,
                        'longitude': item.longitude
                    })
                else:
                    raise ValueError(f'Invalid item in trajet_predefini: expected dict or GeoPoint, got {type(item)}')
            
            return json.dumps(list_of_dicts)
        
        raise ValueError('trajet_predefini must be a list of GeoPoints, a JSON string, or null')

    @field_validator('directeur_id')
    def validate_directeur_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError('directeur_id must be a positive integer')
        return v

    @field_validator('vehicule_id')
    def validate_vehicule_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError('vehicule_id must be a positive integer')
        return v

    @field_validator('dateFin')
    def validate_dates(cls, v, info):
        if v is not None and 'dateDebut' in info.data and info.data['dateDebut'] is not None:
            if v <= info.data['dateDebut']:
                raise ValueError('dateFin must be after dateDebut')
        return v

# --- MissionResponse (for outgoing responses) ---
class MissionResponse(MissionBase):
    id: int
    statut: str
    created_at: datetime
    updated_at: datetime
    trajet_predefini: Optional[List[GeoPoint]] = None
    
    @field_validator('trajet_predefini', mode='before')
    def parse_trajet_from_json_string(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        
        if isinstance(v, list):
            return [GeoPoint(**item) if isinstance(item, dict) else item for item in v]
        
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [GeoPoint(**point) for point in parsed]
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"Warning: Could not parse trajet_predefini string '{v}': {e}")
                return None
        
        # If it's a list already, ensure it's converted to GeoPoint objects
        if isinstance(v, list):
            return [GeoPoint(**item) if isinstance(item, dict) else item for item in v]
            
        raise ValueError(f"Unexpected type for trajet_predefini: {type(v)}")


    class Config:
        from_attributes = True

# Schemas for Collaborator assignment (no changes needed if they don't have custom validators)
class CollaborateurAssign(BaseModel):
    matricule: str = Field(..., description="Matricule du collaborateur à affecter")

class AssignCollaboratorsRequest(BaseModel):
    collaborateurs: List[CollaborateurAssign] = Field(
        ...,
        min_length=1,
        description="Liste des matricules des collaborateurs à affecter"
    )

class AffectationResponse(BaseModel):
    id: int
    mission_id: int
    collaborateur_id: int
    dejeuner: int
    dinner: int
    accouchement: int
    montantCalcule: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
