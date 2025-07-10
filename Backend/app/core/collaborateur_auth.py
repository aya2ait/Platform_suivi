# app/core/collaborateur_auth.py
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_dependencies import get_current_active_user # Assurez-vous que ce chemin est correct
from app.models.models import Utilisateur, Collaborateur, Mission, Affectation

async def get_current_collaborateur(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Collaborateur:
    """
    Récupère le profil Collaborateur associé à l'Utilisateur actuellement connecté.
    Soulève une HTTPException si l'utilisateur n'est pas un 'COLLABORATEUR' ou si le profil n'est pas trouvé.
    """
    if current_user.role.upper() != 'COLLABORATEUR':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux collaborateurs."
        )
    
    collaborateur = current_user.collaborateur
    
    if not collaborateur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil collaborateur non trouvé pour l'utilisateur connecté."
        )
    
    return collaborateur

async def can_read_own_missions(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
) -> Utilisateur:
    """
    Vérifie que l'utilisateur connecté a le rôle 'COLLABORATEUR' pour accéder à ses propres missions.
    Cette fonction retourne l'objet Utilisateur si la condition est remplie.
    """
    if current_user.role.upper() != 'COLLABORATEUR':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux collaborateurs."
        )
    return current_user

async def check_collaborateur_mission_access(
    mission_id: int,
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
) -> bool:
    """
    Vérifie si le collaborateur connecté a accès à une mission spécifique.
    Il doit avoir le rôle 'COLLABORATEUR' et être affecté à la mission.
    """
    if current_user.role.upper() != 'collaborateur':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux collaborateurs."
        )
    
    collaborateur = current_user.collaborateur
    
    if not collaborateur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil collaborateur non trouvé pour l'utilisateur connecté."
        )
    
    affectation = db.query(Affectation).filter(
        Affectation.mission_id == mission_id,
        Affectation.collaborateur_id == collaborateur.id
    ).first()
    
    if not affectation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé à cette mission ou collaborateur non affecté."
        )
    
    return True