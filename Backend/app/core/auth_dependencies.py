# app/core/auth_dependencies.py
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import JWTManager, TokenData, RolePermissions
from app.models.models import Utilisateur, Directeur
import time
from collections import defaultdict

# Configuration du security scheme
security = HTTPBearer()

# Stockage en mémoire pour le rate limiting (en production, utilisez Redis)
request_counts = defaultdict(list)

class RateLimiter:
    """Gestionnaire de limitation de taux"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 900):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def is_allowed(self, identifier: str) -> bool:
        """Vérifier si la requête est autorisée"""
        now = time.time()
        
        # Nettoyer les anciennes requêtes
        request_counts[identifier] = [
            req_time for req_time in request_counts[identifier]
            if now - req_time < self.window_seconds
        ]
        
        # Vérifier le nombre de requêtes
        if len(request_counts[identifier]) >= self.max_requests:
            return False
        
        # Ajouter la requête actuelle
        request_counts[identifier].append(now)
        return True

# Instance globale du rate limiter
rate_limiter = RateLimiter()

async def get_current_user_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> TokenData:
    """Extraire et valider le token JWT"""
    try:
        token = credentials.credentials
        token_data = JWTManager.verify_token(token)
        return token_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    token_data: Annotated[TokenData, Depends(get_current_user_token)],
    db: Annotated[Session, Depends(get_db)]
) -> Utilisateur:
    """Obtenir l'utilisateur actuel depuis la base de données"""
    if not token_data.username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
        )
    
    user = db.query(Utilisateur).filter(
        Utilisateur.login == token_data.username
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
        )
    
    return user

async def get_current_active_user(
    current_user: Annotated[Utilisateur, Depends(get_current_user)]
) -> Utilisateur:
    """Obtenir l'utilisateur actuel s'il est actif"""
    # Ici, vous pouvez ajouter des vérifications d'état (actif/inactif)
    # Pour l'instant, nous retournons l'utilisateur tel quel
    return current_user

async def get_current_directeur(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Directeur:
    """Obtenir le directeur actuel"""
    if current_user.role != RolePermissions.DIRECTEUR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé - Rôle directeur requis",
        )

    directeur = db.query(Directeur).filter(
        # CHANGE THIS LINE:
        Directeur.utilisateur_id == current_user.id # Corrected from Directeur.user_id
    ).first()

    if not directeur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil directeur non trouvé",
        )

    return directeur

# Fonctions de création de dépendances pour les permissions
def require_permission(permission: str):
    """Créer une dépendance qui vérifie une permission spécifique"""
    async def permission_dependency(
        current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
    ) -> Utilisateur:
        if not RolePermissions.has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise: {permission}",
            )
        return current_user
    
    return permission_dependency

def require_role(required_role: str):
    """Créer une dépendance qui vérifie un rôle spécifique"""
    async def role_dependency(
        current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
    ) -> Utilisateur:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis: {required_role}",
            )
        return current_user
    
    return role_dependency

def require_roles(allowed_roles: list[str]):
    """Créer une dépendance qui vérifie plusieurs rôles autorisés"""
    async def roles_dependency(
        current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
    ) -> Utilisateur:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Un des rôles suivants est requis: {', '.join(allowed_roles)}",
            )
        return current_user
    
    return roles_dependency

async def check_rate_limit(request: Request):
    """Middleware de limitation de taux"""
    client_ip = request.client.host
    
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de requêtes. Veuillez réessayer plus tard.",
        )
    
    return True

# Dépendances d'autorisation pour les missions
async def can_create_mission(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """Vérifier si l'utilisateur peut créer des missions"""
    if not RolePermissions.has_permission(current_user.role, "mission:create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation de créer des missions",
        )
    return current_user

async def can_read_mission(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """Vérifier si l'utilisateur peut lire des missions"""
    if not RolePermissions.has_permission(current_user.role, "mission:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation de consulter des missions",
        )
    return current_user

async def can_update_mission(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """Vérifier si l'utilisateur peut modifier des missions"""
    if not RolePermissions.has_permission(current_user.role, "mission:update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation de modifier des missions",
        )
    return current_user

async def can_delete_mission(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """Vérifier si l'utilisateur peut supprimer des missions"""
    if not RolePermissions.has_permission(current_user.role, "mission:delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation de supprimer des missions",
        )
    return current_user

async def can_access_stats(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """Vérifier si l'utilisateur peut accéder aux statistiques"""
    if not RolePermissions.has_permission(current_user.role, "stats:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation d'accéder aux statistiques",
        )
    return current_user

async def can_manage_budget(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """Vérifier si l'utilisateur peut gérer le budget"""
    if not RolePermissions.has_permission(current_user.role, "budget:update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas l'autorisation de gérer le budget",
        )
    return current_user

# Dépendance pour vérifier l'accès aux missions par direction
async def check_mission_access(
    mission_id: int,
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
) -> bool:
    """Vérifier si l'utilisateur peut accéder à une mission spécifique"""
    from app.models.models import Mission
    
    # Les admins peuvent accéder à toutes les missions
    if current_user.role == RolePermissions.ADMIN:
        return True
    
    # Les directeurs ne peuvent accéder qu'aux missions de leur direction
    if current_user.role == RolePermissions.DIRECTEUR:
        directeur = db.query(Directeur).filter(
            Directeur.utilisateur_id == current_user.id
        ).first()
        
        if directeur:
            mission = db.query(Mission).filter(Mission.id == mission_id).first()
            if mission and mission.directeur_id == directeur.id:
                return True
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Vous n'avez pas l'autorisation d'accéder à cette mission",
    )