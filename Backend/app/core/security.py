# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
from fastapi import HTTPException, status
from pydantic import BaseModel
import secrets
import os
from functools import wraps

class SecurityConfig:
    """Configuration de sécurité centralisée"""
    
    # JWT Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # Password Configuration
    PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Security Headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 900  # 15 minutes

class TokenData(BaseModel):
    """Modèle pour les données du token"""
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    direction_id: Optional[int] = None

class Token(BaseModel):
    """Modèle de réponse pour les tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: dict

class PasswordManager:
    """Gestionnaire des mots de passe"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifier un mot de passe"""
        try:
            return SecurityConfig.PWD_CONTEXT.verify(plain_password, hashed_password)
        except Exception:
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hasher un mot de passe"""
        return SecurityConfig.PWD_CONTEXT.hash(password)
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Valider la force d'un mot de passe"""
        if len(password) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères"
        
        if not any(c.isupper() for c in password):
            return False, "Le mot de passe doit contenir au moins une majuscule"
        
        if not any(c.islower() for c in password):
            return False, "Le mot de passe doit contenir au moins une minuscule"
        
        if not any(c.isdigit() for c in password):
            return False, "Le mot de passe doit contenir au moins un chiffre"
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Le mot de passe doit contenir au moins un caractère spécial"
        
        return True, "Mot de passe valide"

class JWTManager:
    """Gestionnaire des tokens JWT"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Créer un token d'accès"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        return jwt.encode(to_encode, SecurityConfig.SECRET_KEY, algorithm=SecurityConfig.ALGORITHM)
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Créer un token de rafraîchissement"""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=SecurityConfig.REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        return jwt.encode(to_encode, SecurityConfig.SECRET_KEY, algorithm=SecurityConfig.ALGORITHM)
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> TokenData:
        """Vérifier et décoder un token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, SecurityConfig.SECRET_KEY, algorithms=[SecurityConfig.ALGORITHM])
            
            # Vérifier le type de token
            if payload.get("type") != token_type:
                raise credentials_exception
            
            username: str = payload.get("sub")
            user_id: int = payload.get("user_id")
            role: str = payload.get("role")
            direction_id: int = payload.get("direction_id")
            
            if username is None:
                raise credentials_exception
                
            return TokenData(
                username=username,
                user_id=user_id,
                role=role,
                direction_id=direction_id
            )
            
        except JWTError:
            raise credentials_exception
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> str:
        """Rafraîchir un token d'accès"""
        token_data = JWTManager.verify_token(refresh_token, "refresh")
        
        # Créer un nouveau token d'accès avec les mêmes données
        new_token_data = {
            "sub": token_data.username,
            "user_id": token_data.user_id,
            "role": token_data.role,
            "direction_id": token_data.direction_id
        }
        
        return JWTManager.create_access_token(new_token_data)



class RolePermissions:
    """Gestion des rôles et permissions"""
    
    # Définition des rôles
    ADMIN = "admin"
    DIRECTEUR = "directeur"
    GESTIONNAIRE = "gestionnaire"
    COLLABORATEUR = "collaborateur"
    
    # Permissions par rôle - CORRIGÉES
    PERMISSIONS = {
        ADMIN: [
            
            # Utilisateurs
            "user:create", "user:read", "user:update", "user:delete",
            "users:read", "users:create", "users:update", "users:delete",
            # Directions
            "direction:create", "direction:read", "direction:update", "direction:delete",
            # Directeurs - AJOUTÉ
            "directeur:create", "directeur:read", "directeur:update", "directeur:delete",
            "directeurs:read", "directeurs:create", "directeurs:update", "directeurs:delete",
            
           
        ],
        DIRECTEUR: [
            "mission:create", "mission:read", "mission:update", "mission:delete",
            "vehicule:read", 
            "collaborateur:read", "collaborateur:create", "collaborateur:update", "collaborateur:delete",
            "stats:read", "budget:read","carte:read"
        ],
        GESTIONNAIRE: [
            "mission:read", "mission:update", 
            "collaborateur:read", "stats:read"
        ],
        COLLABORATEUR: [
            "collab:mission:read"
        ]
    }
    
    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        """Vérifier si un rôle a une permission spécifique"""
        return permission in RolePermissions.PERMISSIONS.get(role, [])
    
    @staticmethod
    def get_user_permissions(role: str) -> list:
        """Obtenir toutes les permissions d'un rôle"""
        return RolePermissions.PERMISSIONS.get(role, [])

class SecurityUtils:
    """Utilitaires de sécurité"""
    
    @staticmethod
    def sanitize_input(input_string: str) -> str:
        """Nettoyer les entrées utilisateur"""
        if not isinstance(input_string, str):
            return str(input_string)
        
        # Supprimer les caractères dangereux
        dangerous_chars = ['<', '>', '"', "'", '&', 'script', 'javascript:', 'onload=']
        cleaned = input_string
        
        for char in dangerous_chars:
            cleaned = cleaned.replace(char, '')
        
        return cleaned.strip()
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Générer un token CSRF"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_csrf_token(token: str, stored_token: str) -> bool:
        """Valider un token CSRF"""
        return secrets.compare_digest(token, stored_token)

# Décorateurs de sécurité
def require_permission(permission: str):
    """Décorateur pour vérifier les permissions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Cette logique sera utilisée avec les dépendances FastAPI
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(required_role: str):
    """Décorateur pour vérifier les rôles"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Cette logique sera utilisée avec les dépendances FastAPI
            return await func(*args, **kwargs)
        return wrapper
    return decorator