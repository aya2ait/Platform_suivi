# app/routers/admin_routes.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_dependencies import get_current_user
from app.models.models import Utilisateur
from app.services.admin_service import AdminService
from app.schemas.admin_schemas import (
    # Direction schemas
    DirectionCreate, DirectionUpdate, DirectionResponse, DirectionWithStats,
    DirectionListResponse, DirectionFilter,
    # Utilisateur schemas
    UtilisateurCreate, UtilisateurUpdate, UtilisateurResponse, 
    UtilisateurListResponse, UtilisateurFilter, ChangePasswordRequest,
    # Directeur schemas
    DirecteurCreate, DirecteurUpdate, DirecteurResponse, DirecteurWithDetails,
    DirecteurListResponse, DirecteurFilter, DirecteurCreateWithUser,
    # Utility schemas
    PaginationParams, ErrorResponse, SuccessResponse, BulkDeleteRequest, BulkDeleteResponse
)

router = APIRouter(prefix="/admin", tags=["admin"])

def admin_required(current_user: Utilisateur = Depends(get_current_user)):
    """Middleware pour vérifier que l'utilisateur est admin"""
    if str(current_user.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    return current_user

def directeur_permission_required(permission: str):
    """Middleware pour vérifier les permissions spécifiques aux directeurs"""
    def permission_checker(current_user: Utilisateur = Depends(get_current_user)):
        if str(current_user.role) != "admin":
            # Pour les non-admins, vérifier les permissions spécifiques
            if not hasattr(current_user, 'permissions') or permission not in current_user.permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' requise pour cette opération"
                )
        return current_user
    return permission_checker

# ====================================================================
# Routes Direction CRUD
# ====================================================================

@router.post("/directions", response_model=DirectionResponse, status_code=status.HTTP_201_CREATED)
async def create_direction(
    direction_data: DirectionCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Créer une nouvelle direction"""
    return AdminService.create_direction(db, direction_data)

@router.get("/directions/{direction_id}", response_model=DirectionWithStats)
async def get_direction(
    direction_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Récupérer une direction par ID avec statistiques"""
    direction = AdminService.get_direction_with_stats(db, direction_id)
    if not direction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Direction non trouvée"
        )
    return direction

@router.get("/directions", response_model=DirectionListResponse)
async def list_directions(
    page: int = Query(1, ge=1, description="Numéro de page"),
    size: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page"),
    nom: Optional[str] = Query(None, description="Filtrer par nom"),
    annee: Optional[int] = Query(None, description="Filtrer par année"),
    mois: Optional[str] = Query(None, description="Filtrer par mois"),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Lister les directions avec pagination et filtres"""
    skip = (page - 1) * size
    
    # Convertir mois en int si fourni
    mois_int = None
    if mois:
        try:
            mois_int = int(mois)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le mois doit être un nombre entre 1 et 12"
            )
    
    filters = DirectionFilter(nom=nom, annee=annee, mois=mois_int)
    directions, total = AdminService.get_directions(db, skip=skip, limit=size, filters=filters)
    
    # Ajouter les statistiques pour chaque direction
    directions_with_stats = []
    for direction in directions:
        stats = AdminService.get_direction_with_stats(db, int(direction.id))
        if stats:
            directions_with_stats.append(DirectionWithStats(**stats))
    
    pages = (total + size - 1) // size
    
    return DirectionListResponse(
        items=directions_with_stats,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.put("/directions/{direction_id}", response_model=DirectionResponse)
async def update_direction(
    direction_id: int,
    direction_data: DirectionUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Mettre à jour une direction"""
    direction = AdminService.update_direction(db, direction_id, direction_data)
    if not direction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Direction non trouvée"
        )
    return direction

@router.delete("/directions/{direction_id}", response_model=SuccessResponse)
async def delete_direction(
    direction_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Supprimer une direction"""
    success = AdminService.delete_direction(db, direction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Direction non trouvée"
        )
    return SuccessResponse(message="Direction supprimée avec succès")

@router.post("/directions/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_directions(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Suppression en lot des directions"""
    deleted_count, failed_ids, errors = AdminService.bulk_delete_directions(db, request.ids)
    return BulkDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids,
        errors=errors
    )

# ====================================================================
# Routes Utilisateur CRUD
# ====================================================================

@router.post("/users", response_model=UtilisateurResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UtilisateurCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Créer un nouvel utilisateur"""
    return AdminService.create_utilisateur(db, user_data)

@router.get("/users/{user_id}", response_model=UtilisateurResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Récupérer un utilisateur par ID"""
    user = AdminService.get_utilisateur(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    return user

@router.get("/users", response_model=UtilisateurListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Numéro de page"),
    size: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page"),
    login: Optional[str] = Query(None, description="Filtrer par login"),
    role: Optional[str] = Query(None, description="Filtrer par rôle"),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Lister les utilisateurs avec pagination et filtres"""
    skip = (page - 1) * size
    
    filters = UtilisateurFilter(login=login, role=role)
    users, total = AdminService.get_utilisateurs(db, skip=skip, limit=size, filters=filters)
    
    # Convertir les objets Utilisateur en UtilisateurResponse
    user_responses = []
    for user in users:
        user_responses.append(UtilisateurResponse.model_validate(user))
    
    pages = (total + size - 1) // size
    
    return UtilisateurListResponse(
        items=user_responses,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.put("/users/{user_id}", response_model=UtilisateurResponse)
async def update_user(
    user_id: int,
    user_data: UtilisateurUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Mettre à jour un utilisateur"""
    user = AdminService.update_utilisateur(db, user_id, user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    return user

@router.delete("/users/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Supprimer un utilisateur"""
    success = AdminService.delete_utilisateur(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    return SuccessResponse(message="Utilisateur supprimé avec succès")

# ====================================================================
# Routes Directeur CRUD
# ====================================================================

@router.post("/directeurs", response_model=DirecteurResponse, status_code=status.HTTP_201_CREATED)
async def create_directeur(
    directeur_data: DirecteurCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """
    Créer un nouveau directeur
    
    - **utilisateur_id**: ID de l'utilisateur existant avec rôle DIRECTEUR
    - **nom**: Nom du directeur
    - **prenom**: Prénom du directeur  
    - **direction_id**: ID de la direction associée
    
    L'utilisateur doit avoir le rôle "DIRECTEUR" et ne pas avoir déjà un profil directeur.
    """
    return AdminService.create_directeur(db, directeur_data)

@router.post("/directeurs/with-user", status_code=status.HTTP_201_CREATED)
async def create_directeur_with_user(
    directeur_data: DirecteurCreateWithUser,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """
    Créer un utilisateur et son profil directeur en une seule opération
    
    - **login**: Login du nouvel utilisateur
    - **motDePasse**: Mot de passe (min 8 caractères)
    - **nom**: Nom du directeur
    - **prenom**: Prénom du directeur
    - **direction_id**: ID de la direction associée
    
    Crée automatiquement un utilisateur avec le rôle "DIRECTEUR" et son profil directeur.
    """
    user, directeur = AdminService.create_directeur_with_user(db, directeur_data)
    return {
        "message": "Directeur créé avec succès",
        "user": UtilisateurResponse.model_validate(user),
        "directeur": DirecteurResponse.model_validate(directeur)
    }

@router.get("/directeurs", response_model=DirecteurListResponse)
async def list_directeurs(
    page: int = Query(1, ge=1, description="Numéro de page"),
    size: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page"),
    nom: Optional[str] = Query(None, description="Filtrer par nom"),
    prenom: Optional[str] = Query(None, description="Filtrer par prénom"),
    direction_id: Optional[int] = Query(None, description="Filtrer par direction"),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Lister les directeurs avec pagination et filtres"""
    skip = (page - 1) * size
    
    filters = DirecteurFilter(nom=nom, prenom=prenom, direction_id=direction_id)
    directeurs, total = AdminService.get_directeurs(db, skip=skip, limit=size, filters=filters)
    
    # Ajouter les détails pour chaque directeur
    directeurs_with_details = []
    for directeur in directeurs:
        details = AdminService.get_directeur_with_details(db, int(directeur.id))
        if details:
            directeurs_with_details.append(DirecteurWithDetails(**details))
    
    pages = (total + size - 1) // size
    
    return DirecteurListResponse(
        items=directeurs_with_details,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/directeurs/{directeur_id}", response_model=DirecteurWithDetails)
async def get_directeur(
    directeur_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Récupérer un directeur par ID avec détails"""
    directeur = AdminService.get_directeur_with_details(db, directeur_id)
    if not directeur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directeur non trouvé"
        )
    return directeur

@router.put("/directeurs/{directeur_id}", response_model=DirecteurResponse)
async def update_directeur(
    directeur_id: int,
    directeur_data: DirecteurUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Mettre à jour un directeur"""
    directeur = AdminService.update_directeur(db, directeur_id, directeur_data)
    if not directeur:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directeur non trouvé"
        )
    return directeur

@router.delete("/directeurs/{directeur_id}", response_model=SuccessResponse)
async def delete_directeur(
    directeur_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Supprimer un directeur"""
    success = AdminService.delete_directeur(db, directeur_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Directeur non trouvé"
        )
    return SuccessResponse(message="Directeur supprimé avec succès")

# ====================================================================
# Routes utilitaires
# ====================================================================

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(admin_required)
):
    """Récupérer les statistiques du tableau de bord admin"""
    return AdminService.get_dashboard_stats(db)