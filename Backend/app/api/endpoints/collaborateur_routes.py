# app/api/v1/collaborateur_routes.py
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import math

from app.core.database import get_db
from app.core.auth_dependencies import get_current_active_user
from app.core.collaborateur_auth import (
    get_current_collaborateur,
    can_read_own_missions,
    check_collaborateur_mission_access
)
from app.models.models import Utilisateur, Collaborateur
from app.services.collaborateur_service import CollaborateurService
from app.schemas.collaborateur_schemas import (
    MissionListResponse,
    MissionDetailResponse,
    MissionFilterRequest,
    MissionSearchRequest,
    MissionStatsResponse,
    CollaborateurProfileResponse,
    MissionCollaborateurResponse
)

router = APIRouter(prefix="/collaborateur", tags=["Collaborateur Missions"])

@router.get("/profile", response_model=CollaborateurProfileResponse)
async def get_my_profile(
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)]
):
    """Obtenir le profil du collaborateur connecté"""
    service = CollaborateurService(db)
    profile = service.get_collaborateur_profile(collaborateur.id)
    return profile

@router.get("/missions", response_model=MissionListResponse)
async def get_my_missions(
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)],
    statut: str = Query(None, description="Filtrer par statut de mission"),
    date_debut: datetime = Query(None, description="Date de début pour le filtre"),
    date_fin: datetime = Query(None, description="Date de fin pour le filtre"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page")
):
    """Obtenir la liste des missions du collaborateur connecté"""
    service = CollaborateurService(db)
    
    # Créer les filtres
    filters = MissionFilterRequest(
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        page=page,
        per_page=per_page
    )
    
    missions, total = service.get_collaborateur_missions(collaborateur.id, filters)
    
    # Calculer le nombre total de pages
    total_pages = math.ceil(total / per_page)
    
    return MissionListResponse(
        missions=missions,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.get("/missions/{mission_id}", response_model=MissionDetailResponse)
async def get_my_mission(
    mission_id: int,
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)]
):
    """Obtenir les détails d'une mission spécifique"""
    service = CollaborateurService(db)
    
    # Vérifier l'accès à la mission
    await check_collaborateur_mission_access(mission_id, current_user, db)
    
    mission = service.get_mission_by_id(mission_id, collaborateur.id)
    
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission non trouvée"
        )
    
    return MissionDetailResponse(mission=mission)

@router.get("/missions/search", response_model=MissionListResponse)
async def search_my_missions(
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)],
    query: str = Query(..., min_length=1, description="Terme de recherche"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(10, ge=1, le=100, description="Nombre d'éléments par page")
):
    """Rechercher dans les missions du collaborateur"""
    service = CollaborateurService(db)
    
    search_request = MissionSearchRequest(
        query=query,
        page=page,
        per_page=per_page
    )
    
    missions, total = service.search_collaborateur_missions(collaborateur.id, search_request)
    
    # Calculer le nombre total de pages
    total_pages = math.ceil(total / per_page)
    
    return MissionListResponse(
        missions=missions,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.get("/missions/stats", response_model=MissionStatsResponse)
async def get_my_mission_stats(
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)]
):
    """Obtenir les statistiques des missions du collaborateur"""
    service = CollaborateurService(db)
    return service.get_collaborateur_mission_stats(collaborateur.id)

@router.get("/missions/recent", response_model=List[MissionCollaborateurResponse])
async def get_my_recent_missions(
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(5, ge=1, le=20, description="Nombre de missions récentes")
):
    """Obtenir les missions récentes du collaborateur"""
    service = CollaborateurService(db)
    return service.get_collaborateur_recent_missions(collaborateur.id, limit)

@router.get("/missions/period", response_model=List[MissionCollaborateurResponse])
async def get_missions_by_period(
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)],
    start_date: datetime = Query(..., description="Date de début de la période"),
    end_date: datetime = Query(..., description="Date de fin de la période")
):
    """Obtenir les missions du collaborateur sur une période donnée"""
    service = CollaborateurService(db)
    
    # Valider les dates
    if start_date >= end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de début doit être antérieure à la date de fin"
        )
    
    # Limiter la période à un maximum (ex: 1 an)
    max_period = timedelta(days=365)
    if end_date - start_date > max_period:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La période ne peut pas dépasser 1 an"
        )
    
    return service.get_collaborateur_missions_by_period(
        collaborateur.id, 
        start_date, 
        end_date
    )

@router.get("/missions/{mission_id}/affectation")
async def get_mission_affectation(
    mission_id: int,
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)],
    collaborateur: Annotated[Collaborateur, Depends(get_current_collaborateur)],
    db: Annotated[Session, Depends(get_db)]
):
    """Obtenir les détails d'affectation pour une mission"""
    service = CollaborateurService(db)
    
    # Vérifier l'accès à la mission
    await check_collaborateur_mission_access(mission_id, current_user, db)
    
    affectation = service.get_mission_affectation(mission_id, collaborateur.id)
    
    if not affectation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Affectation non trouvée pour cette mission"
        )
    
    return affectation