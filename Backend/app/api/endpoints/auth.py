# app/endpoints/auth.py

from typing import Annotated, Optional # Ensure Optional is imported
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone # Ensure datetime and timezone are imported
import logging

from app.core.database import get_db
from app.core.security import (
    JWTManager,
    PasswordManager,
    # Token, # Token n'est plus nécessaire d'être importé ici car LoginResponse le gère
    SecurityConfig,
    SecurityUtils,
    RolePermissions # Add this import if not already there
)
from app.core.auth_dependencies import (
    get_current_user_token,
    get_current_active_user,
    check_rate_limit
)
from app.models.models import Utilisateur, Directeur, Direction # Ensure Direction is imported if used with directeur.direction_rel
from app.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    UserInfoResponse,
    ChangePasswordRequest,
    ResetPasswordRequest,
    PermissionsResponse, # Add this import if not already there
    TokenValidationResponse # Add this import if not already there
)

# Configurer le logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentification"])

@router.post("/login", response_model=LoginResponse, summary="Authentification de l'utilisateur")
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(check_rate_limit)]
):
    """Authentification de l'utilisateur avec debugging"""
    
    logger.info(f"=== DEBUT LOGIN DEBUG ===")
    logger.info(f"Username reçu: '{login_data.username}'")
    logger.info(f"Password reçu: '{login_data.password[:3]}...' (longueur: {len(login_data.password)})")
    
    # Nettoyer les entrées
    username = SecurityUtils.sanitize_input(login_data.username)
    password = login_data.password
    
    logger.info(f"Username après sanitization: '{username}'")
    
    # Rechercher l'utilisateur
    user = db.query(Utilisateur).filter(
        Utilisateur.login == username
    ).first()
    
    if not user:
        logger.error(f"ERREUR: Utilisateur '{username}' non trouvé dans la base")
        # Lister tous les utilisateurs pour debug
        all_users = db.query(Utilisateur.login, Utilisateur.role).all()
        logger.info(f"Utilisateurs disponibles: {[u.login for u in all_users]}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"Utilisateur trouvé: ID={user.id}, login='{user.login}', role='{user.role}'")
    logger.info(f"Hash en base: '{user.motDePasse[:20]}...'")
    
    # Vérifier le mot de passe
    password_valid = PasswordManager.verify_password(password, user.motDePasse)
    logger.info(f"Vérification mot de passe: {password_valid}")
    
    if not password_valid:
        logger.error(f"ERREUR: Mot de passe invalide pour '{username}'")
        # Test de vérification manuelle (utile pour le debug mais peut être retiré en production)
        try:
            import bcrypt
            manual_check = bcrypt.checkpw(password.encode('utf-8'), user.motDePasse.encode('utf-8'))
            logger.info(f"Vérification manuelle bcrypt: {manual_check}")
        except ImportError:
            logger.warning("Module 'bcrypt' non disponible pour la vérification manuelle.")
        except Exception as e:
            logger.error(f"Erreur vérification manuelle: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"Authentification réussie pour '{username}'")
    
    # Obtenir les informations du directeur si applicable
    direction_id = None
    direction_nom = None
    
    logger.info(f"Rôle utilisateur: '{user.role}' (type: {type(user.role)})")
    
    if user.role.lower() == RolePermissions.DIRECTEUR: # Use constant for role comparison
        logger.info("Recherche des informations directeur...")
        directeur = db.query(Directeur).filter(
            Directeur.utilisateur_id == user.id
        ).first()
        if directeur:
            direction_id = directeur.direction_id
            # Ensure direction_rel is loaded and exists
            direction_nom = directeur.direction_rel.nom if hasattr(directeur, 'direction_rel') and directeur.direction_rel else None
            logger.info(f"Directeur trouvé: direction_id={direction_id}, nom='{direction_nom}'")
        else:
            logger.warning("Aucune information directeur trouvée pour cet utilisateur directeur.")
    
    # Créer les données du token
    token_data = {
        "sub": user.login,
        "user_id": user.id,
        "role": user.role.lower(),
        "direction_id": direction_id
    }
    
    logger.info(f"Données token: {token_data}")
    
    try:
        # Générer les tokens
        access_token = JWTManager.create_access_token(token_data)
        refresh_token = JWTManager.create_refresh_token(token_data)
        logger.info("Tokens générés avec succès")
    except Exception as e:
        logger.error(f"Erreur génération tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération des tokens"
        )
    
    # Informations utilisateur
    user_info = {
        "id": user.id,
        "login": user.login,
        "role": user.role.lower(),
        "direction_id": direction_id,
        "direction_nom": direction_nom
    }
    
    logger.info(f"Réponse finale: user_info={user_info}")
    logger.info("=== FIN LOGIN DEBUG ===")
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_info=user_info
    )

# ====================================================================================================
# ICI COMMENCE L'ENDPOINT /auth/me - Assurez-vous qu'il est inclus dans votre fichier
# ====================================================================================================

@router.get("/me", response_model=UserInfoResponse, summary="Obtenir les informations de l'utilisateur connecté")
async def get_current_user_info(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Retourne les informations détaillées de l'utilisateur actuellement authentifié,
    y compris son rôle et, si applicable, les détails de sa direction.
    """
    logger.info(f"Requête /auth/me pour l'utilisateur: {current_user.login}")
    
    direction_id = None
    direction_nom = None

    if current_user.role.lower() == RolePermissions.DIRECTEUR:
        logger.info("Tentative de récupérer les informations de direction pour le directeur.")
        directeur = db.query(Directeur).filter(
            Directeur.utilisateur_id == current_user.id
        ).first()
        if directeur:
            direction_id = directeur.direction_id
            direction_nom = directeur.direction_rel.nom if hasattr(directeur, 'direction_rel') and directeur.direction_rel else None
            logger.info(f"Informations direction trouvées: ID={direction_id}, Nom={direction_nom}")
        else:
            logger.warning(f"Profil directeur non trouvé pour l'utilisateur {current_user.login} (ID: {current_user.id}).")
    
    return UserInfoResponse(
        id=current_user.id,
        login=current_user.login,
        role=current_user.role.lower(), # Ensure consistency
        direction_id=direction_id,
        direction_nom=direction_nom,
        created_at=current_user.created_at # Ensure created_at is a datetime object
    )

# ====================================================================================================
# FIN DE L'ENDPOINT /auth/me
# ====================================================================================================

@router.post("/refresh", response_model=LoginResponse, summary="Rafraîchir le token d'accès")
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    _: Annotated[bool, Depends(check_rate_limit)]
):
    """Rafraîchir le token d'accès"""
    
    try:
        token_payload = JWTManager.verify_token(refresh_data.refresh_token, token_type="refresh")
        
        new_token_data = {
            "sub": token_payload.username,
            "user_id": token_payload.user_id,
            "role": token_payload.role,
            "direction_id": token_payload.direction_id
        }
        
        new_access_token = JWTManager.create_access_token(new_token_data)
        
        # Pour le user_info dans la réponse de refresh, si direction_nom n'est pas dans le token,
        # il faudrait le récupérer de la DB ici si nécessaire, sinon il sera null.
        user_info = {
            "id": token_payload.user_id,
            "login": token_payload.username,
            "role": token_payload.role,
            "direction_id": token_payload.direction_id,
            "direction_nom": None # Placeholder, retrieve from DB if critical
        }

        return LoginResponse(
            access_token=new_access_token,
            refresh_token=refresh_data.refresh_token,
            token_type="bearer",
            expires_in=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_info=user_info
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement du token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de rafraîchissement invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout", summary="Déconnexion de l'utilisateur")
async def logout(
    response: Response,
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
):
    """Déconnexion de l'utilisateur"""
    logger.info(f"Déconnexion de l'utilisateur: {current_user.login}")
    return {"message": "Déconnexion réussie"}

@router.post("/change-password", summary="Changer le mot de passe de l'utilisateur connecté")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Changer le mot de passe de l'utilisateur connecté"""
    
    if not PasswordManager.verify_password(
        password_data.current_password,
        current_user.motDePasse
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect"
        )
    
    is_valid, message = PasswordManager.validate_password_strength(
        password_data.new_password
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    current_user.motDePasse = PasswordManager.get_password_hash(
        password_data.new_password
    )
    
    db.commit()
    logger.info(f"Mot de passe de l'utilisateur {current_user.login} modifié avec succès.")
    
    return {"message": "Mot de passe modifié avec succès"}

@router.post("/reset-password", summary="Réinitialiser le mot de passe (implémentation partielle)")
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)]
):
    """Réinitialisation de mot de passe (implémentation partielle)"""
    user = db.query(Utilisateur).filter(Utilisateur.login == reset_data.username).first()
    if not user:
        logger.warning(f"Tentative de réinitialisation de mot de passe pour utilisateur non trouvé: {reset_data.username}")
        raise HTTPException(status_code=status.HTTP_200_OK, detail="Si l'utilisateur existe, un e-mail de réinitialisation a été envoyé.")
    
    logger.info(f"Processus de réinitialisation de mot de passe déclenché pour: {reset_data.username}")
    # Ajoutez ici la logique réelle d'envoi d'e-mail avec un token de réinitialisation
    return {"message": "Si l'utilisateur existe, un e-mail de réinitialisation a été envoyé."}

@router.get("/validate-token", response_model=TokenValidationResponse, summary="Valider un token JWT")
async def validate_token(
    token_data: Annotated[dict, Depends(get_current_user_token)]
):
    """Vérifie la validité du token JWT fourni et retourne ses informations décodées."""
    expires_at = None
    if "exp" in token_data:
        expires_at = datetime.fromtimestamp(token_data["exp"], tz=timezone.utc)

    return TokenValidationResponse(
        valid=True,
        username=token_data.get("sub"),
        role=token_data.get("role"),
        direction_id=token_data.get("direction_id"),
        expires_at=expires_at
    )

@router.get("/permissions", response_model=PermissionsResponse, summary="Obtenir les permissions de l'utilisateur connecté")
async def get_user_permissions(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
):
    """Retourne le rôle de l'utilisateur connecté et la liste des permissions associées à ce rôle."""
    user_role = current_user.role
    permissions = RolePermissions.get_user_permissions(user_role.lower()) # Ensure consistent lowercasing for role
    
    return PermissionsResponse(
        role=user_role.lower(),
        permissions=permissions
    )

# Endpoint de debug pour lister les utilisateurs (déjà présent)
@router.get("/debug/users", summary="[DEBUG] Lister tous les utilisateurs")
async def debug_users(db: Annotated[Session, Depends(get_db)]):
    """Endpoint de debug pour lister les utilisateurs"""
    users = db.query(Utilisateur.id, Utilisateur.login, Utilisateur.role).all()
    return {
        "total_users": len(users),
        "users": [{"id": u.id, "login": u.login, "role": u.role} for u in users]
    }

# Endpoint de debug pour tester le hachage (déjà présent)
@router.post("/debug/hash-check", summary="[DEBUG] Tester un mot de passe et un hachage")
async def debug_hash_check(
    request: dict,  # {"password": "...", "hash": "..."}
    db: Annotated[Session, Depends(get_db)]
):
    """Endpoint de debug pour tester le hachage"""
    password = request.get("password")
    hash_to_check = request.get("hash")
    
    if not password or not hash_to_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "password et hash requis"}
        )
    
    try:
        result1 = PasswordManager.verify_password(password, hash_to_check)
        
        import bcrypt
        result2 = bcrypt.checkpw(password.encode('utf-8'), hash_to_check.encode('utf-8'))
        
        return {
            "password": password,
            "hash": hash_to_check[:20] + "...",
            "password_manager_result": result1,
            "bcrypt_manual_result": result2,
            "match": result1 and result2
        }
    except Exception as e:
        logger.error(f"Erreur debug_hash_check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e)}
        )