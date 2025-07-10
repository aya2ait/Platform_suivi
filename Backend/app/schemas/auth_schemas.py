# app/schemas/auth_schemas.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime

class LoginRequest(BaseModel):
    """Schéma de requête de connexion"""
    username: str = Field(..., min_length=3, max_length=100, description="Nom d'utilisateur")
    password: str = Field(..., min_length=1, description="Mot de passe")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "directeur_rabat",
                "password": "monmotdepasse123"
            }
        }

class LoginResponse(BaseModel):
    """Schéma de réponse de connexion"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # en secondes
    user_info: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user_info": {
                    "id": 1,
                    "login": "directeur_rabat",
                    "role": "directeur",
                    "direction_id": 1,
                    "direction_nom": "Direction Régionale Rabat"
                }
            }
        }

class RefreshTokenRequest(BaseModel):
    """Schéma de requête de rafraîchissement de token"""
    refresh_token: str = Field(..., description="Token de rafraîchissement")

class UserInfoResponse(BaseModel):
    """Schéma de réponse d'informations utilisateur"""
    id: int
    login: str
    role: str
    direction_id: Optional[int] = None
    direction_nom: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True # Ancien 'orm_mode' est maintenant 'from_attributes' en Pydantic V2
        json_schema_extra = {
            "example": {
                "id": 1,
                "login": "directeur_rabat",
                "role": "directeur",
                "direction_id": 1,
                "direction_nom": "Direction Régionale Rabat",
                "created_at": "2024-01-15T10:30:00"
            }
        }

class ChangePasswordRequest(BaseModel):
    """Schéma de requête de changement de mot de passe"""
    current_password: str = Field(..., description="Mot de passe actuel")
    new_password: str = Field(
        ..., 
        min_length=8, 
        description="Nouveau mot de passe (min 8 caractères)"
    )
    confirm_password: str = Field(..., description="Confirmation du nouveau mot de passe")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Les mots de passe ne correspondent pas')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "ancien_mot_de_passe",
                "new_password": "NouveauMotDePasse123!",
                "confirm_password": "NouveauMotDePasse123!"
            }
        }

class ResetPasswordRequest(BaseModel):
    """Schéma de requête de réinitialisation de mot de passe"""
    username: str = Field(..., description="Nom d'utilisateur")
    
class CreateUserRequest(BaseModel):
    """Schéma de requête de création d'utilisateur"""
    login: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    # MODIFICATION CLÉ: 'regex' remplacé par 'pattern' pour Pydantic V2
    role: str = Field(..., pattern="^(admin|directeur|gestionnaire|collaborateur)$") 
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Valider la force du mot de passe"""
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        
        if not any(c.isupper() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule')
        
        if not any(c.islower() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre')
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial')
        
        return v

class UpdateUserRequest(BaseModel):
    """Schéma de requête de mise à jour d'utilisateur"""
    login: Optional[str] = Field(None, min_length=3, max_length=100)
    # MODIFICATION CLÉ: 'regex' remplacé par 'pattern' pour Pydantic V2
    role: Optional[str] = Field(None, pattern="^(admin|directeur|gestionnaire|collaborateur)$")

class UserResponse(BaseModel):
    """Schéma de réponse pour un utilisateur"""
    id: int
    login: str
    role: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True # Ancien 'orm_mode' est maintenant 'from_attributes' en Pydantic V2

class TokenValidationResponse(BaseModel):
    """Schéma de réponse de validation de token"""
    valid: bool
    username: Optional[str] = None
    role: Optional[str] = None
    direction_id: Optional[int] = None
    expires_at: Optional[datetime] = None

class PermissionsResponse(BaseModel):
    """Schéma de réponse des permissions"""
    role: str
    permissions: list[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "directeur",
                "permissions": [
                    "mission:create",
                    "mission:read",
                    "mission:update",
                    "collaborateur:read",
                    "stats:read",
                    "budget:read"
                ]
            }
        }

class SecurityHeadersResponse(BaseModel):
    """Schéma pour les en-têtes de sécurité"""
    headers: Dict[str, str]

# Schémas pour la gestion des sessions et CSRF
class CSRFTokenResponse(BaseModel):
    """Schéma de réponse pour le token CSRF"""
    csrf_token: str
    expires_in: int

class SessionInfo(BaseModel):
    """Informations de session"""
    user_id: int
    username: str
    role: str
    login_time: datetime
    last_activity: datetime
    ip_address: Optional[str] = None

# Schémas pour l'audit de sécurité
class LoginAttempt(BaseModel):
    """Tentative de connexion"""
    username: str
    success: bool
    ip_address: str
    user_agent: Optional[str] = None
    timestamp: datetime
    failure_reason: Optional[str] = None

class SecurityEvent(BaseModel):
    """Événement de sécurité"""
    event_type: str  # "login", "logout", "password_change", "unauthorized_access"
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    timestamp: datetime