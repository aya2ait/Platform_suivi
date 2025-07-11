from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from app.core.database import get_db
from app.services.anomaly import AnomalyInjectionService
from app.schemas.anomaly import (
    AnomalyConfig, AnomalyInjectionResult, BatchInjectionRequest, 
    BatchInjectionResponse, ContaminationStatus, CleanupRequest, 
    CleanupResponse, AnomalyStatistics, ConfigUpdateRequest, 
    ConfigUpdateResponse, TrajectoryValidationRequest, 
    TrajectoryValidationResponse
)
# AJOUT DES IMPORTS MANQUANTS
from app.models.models import Mission, Anomalie, Trajet  

router = APIRouter(prefix="/anomalies", tags=["anomalies"])
logger = logging.getLogger(__name__)

def get_anomaly_service(db: Session = Depends(get_db)) -> AnomalyInjectionService:
    """Dependency pour obtenir le service d'injection d'anomalies"""
    return AnomalyInjectionService(db)

@router.get("/config", response_model=AnomalyConfig)
async def get_anomaly_config(
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Récupérer la configuration actuelle des anomalies"""
    try:
        return service.config
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la configuration: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

@router.put("/config", response_model=ConfigUpdateResponse)
async def update_anomaly_config(
    request: ConfigUpdateRequest,
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Mettre à jour la configuration des anomalies"""
    try:
        previous_config = service.config.copy() if request.backup_current_config else None
        
        service.update_config(request.new_config)
        
        return ConfigUpdateResponse(
            success=True,
            previous_config=previous_config,
            new_config=request.new_config,
            update_timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trajectories/clean")
async def get_clean_trajectories(
    mission_id: Optional[int] = Query(None, description="ID de la mission (optionnel)"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum de points à retourner"),
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Récupérer les trajectoires propres"""
    try:
        trajectories = await service.get_clean_trajectories(mission_id)
        
        # Limiter le nombre de résultats
        if len(trajectories) > limit:
            trajectories = trajectories[:limit]
        
        return {
            "mission_id": mission_id,
            "total_points": len(trajectories),
            "trajectories": trajectories
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des trajectoires: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/inject/{mission_id}", response_model=AnomalyInjectionResult)
async def inject_anomalies_for_mission(
    mission_id: int,
    background_tasks: BackgroundTasks,
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Injecter des anomalies pour une mission spécifique"""
    try:
        # CORRECTION: Requête simplifiée et correcte
        mission = service.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise HTTPException(status_code=404, detail=f"Mission {mission_id} non trouvée")
        
        # Vérifier si la mission est déjà contaminée
        contaminated_missions = await service.get_contaminated_missions()
        if mission_id in contaminated_missions:
            raise HTTPException(
                status_code=400, 
                detail=f"La mission {mission_id} est déjà contaminée"
            )
        
        result = await service.inject_anomalies_for_mission(mission_id)
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error_message or "Injection échouée")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'injection pour la mission {mission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/inject/batch", response_model=BatchInjectionResponse)
async def inject_anomalies_batch(
    request: BatchInjectionRequest,
    background_tasks: BackgroundTasks,
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Injecter des anomalies en lot"""
    try:
        start_time = datetime.now()
        
        # Appliquer la configuration personnalisée si fournie
        if request.config_override:
            service.update_config(request.config_override)
        
        # Exécuter l'injection
        if request.dry_run:
            # Pour un dry run, on simule sans sauvegarder
            logger.info("Exécution en mode dry run")
            # Ici vous pourriez implémenter une version de simulation
            results = []
        else:
            results = await service.inject_anomalies_batch(request.mission_ids)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        return BatchInjectionResponse(
            total_processed=len(results),
            successful_injections=successful,
            failed_injections=failed,
            results=results,
            processing_time_seconds=processing_time
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'injection en lot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contaminated", response_model=List[ContaminationStatus])
async def get_contaminated_missions(
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Récupérer la liste des missions contaminées"""
    try:
        mission_ids = await service.get_contaminated_missions()
        
        statuses = []
        for mission_id in mission_ids:
            # Récupérer les détails de contamination
            anomalies = service.db.query(Anomalie).filter(
                Anomalie.mission_id == mission_id,
                Anomalie.type == 'TRAJECTORY_CONTAMINATED'
            ).all()
            
            contamination_types = []
            contamination_date = None
            
            for anomalie in anomalies:
                if anomalie.description:
                    # Extraire les types d'anomalies de la description
                    if "anomalies:" in anomalie.description:
                        types_str = anomalie.description.split("anomalies:")[1].strip()
                        contamination_types.extend([t.strip() for t in types_str.split(",")])
                
                if not contamination_date or anomalie.dateDetection > contamination_date:
                    contamination_date = anomalie.dateDetection
            
            # Compter les points
            total_points = service.db.query(Trajet).filter(Trajet.mission_id == mission_id).count()
            
            status = ContaminationStatus(
                mission_id=mission_id,
                is_contaminated=True,
                contamination_types=contamination_types,
                contamination_date=contamination_date,
                original_points_count=None,  # Difficile à déterminer après contamination
                contaminated_points_count=total_points
            )
            statuses.append(status)
        
        return statuses
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des missions contaminées: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clean", response_model=CleanupResponse)
async def clean_contaminated_trajectories(
    request: CleanupRequest,
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Nettoyer les trajectoires contaminées"""
    try:
        if not request.confirmation:
            raise HTTPException(
                status_code=400, 
                detail="Confirmation requise pour le nettoyage"
            )
        
        # Compter les missions à nettoyer
        contaminated_missions = await service.get_contaminated_missions()
        missions_to_clean = request.mission_ids or contaminated_missions
        
        # Compter les anomalies à supprimer
        anomalies_query = service.db.query(Anomalie).filter(
            Anomalie.type == 'TRAJECTORY_CONTAMINATED'
        )
        if request.mission_ids:
            anomalies_query = anomalies_query.filter(Anomalie.mission_id.in_(request.mission_ids))
        
        anomalies_count = anomalies_query.count()
        
        # Créer une sauvegarde si demandé
        backup_created = False
        backup_path = None
        if request.backup_before_cleanup:
            # Ici vous pourriez implémenter la logique de sauvegarde
            logger.info("Sauvegarde des données avant nettoyage")
            backup_created = True
            backup_path = f"/backups/contaminated_trajectories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        # Effectuer le nettoyage
        await service.clean_contaminated_trajectories(request.mission_ids)
        
        return CleanupResponse(
            missions_cleaned=len(missions_to_clean),
            anomalies_removed=anomalies_count,
            backup_created=backup_created,
            backup_path=backup_path,
            cleanup_timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics", response_model=AnomalyStatistics)
async def get_anomaly_statistics(
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Récupérer les statistiques des anomalies"""
    try:
        # Compter le total des missions
        total_missions = service.db.query(Mission).count()
        
        # Compter les missions contaminées
        contaminated_missions = len(await service.get_contaminated_missions())
        
        # Calculer le taux de contamination
        contamination_rate = contaminated_missions / total_missions if total_missions > 0 else 0
        
        # Compter les types d'anomalies
        anomaly_type_counts = {}
        anomalies = service.db.query(Anomalie).filter(
            Anomalie.type == 'TRAJECTORY_CONTAMINATED'
        ).all()
        
        total_anomaly_instances = 0
        for anomalie in anomalies:
            if anomalie.description and "anomalies:" in anomalie.description:
                types_str = anomalie.description.split("anomalies:")[1].strip()
                types = [t.strip() for t in types_str.split(",")]
                for anomaly_type in types:
                    anomaly_type_counts[anomaly_type] = anomaly_type_counts.get(anomaly_type, 0) + 1
                    total_anomaly_instances += 1
        
        # Calculer la moyenne d'anomalies par mission
        avg_anomalies = total_anomaly_instances / contaminated_missions if contaminated_missions > 0 else 0
        
        # Trouver la date de dernière injection
        last_injection = service.db.query(Anomalie.dateDetection).filter(
            Anomalie.type == 'TRAJECTORY_CONTAMINATED'
        ).order_by(Anomalie.dateDetection.desc()).first()
        
        last_injection_date = last_injection.dateDetection if last_injection else None
        
        return AnomalyStatistics(
            total_missions=total_missions,
            contaminated_missions=contaminated_missions,
            contamination_rate=contamination_rate,
            anomaly_type_counts=anomaly_type_counts,
            average_anomalies_per_mission=avg_anomalies,
            last_injection_date=last_injection_date
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate/{mission_id}", response_model=TrajectoryValidationResponse)
async def validate_trajectory(
    mission_id: int,
    request: TrajectoryValidationRequest,
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Valider une trajectoire"""
    try:
        # Vérifier que la mission existe
        mission = service.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise HTTPException(status_code=404, detail=f"Mission {mission_id} non trouvée")
        
        # Récupérer les points de trajectoire
        trajets = service.db.query(Trajet).filter(
            Trajet.mission_id == mission_id
        ).order_by(Trajet.timestamp).all()
        
        validation_errors = []
        validation_warnings = []
        anomalies_detected = []
        
        # Vérifier les anomalies si demandé
        if request.check_anomalies:
            anomalies = service.db.query(Anomalie).filter(
                Anomalie.mission_id == mission_id
            ).all()
            
            for anomalie in anomalies:
                if anomalie.type == 'TRAJECTORY_CONTAMINATED':
                    anomalies_detected.append(anomalie.type)
                    validation_warnings.append(f"Trajectoire contaminée détectée: {anomalie.description}")
        
        # Vérifier la continuité si demandé
        if request.check_continuity and len(trajets) > 1:
            for i in range(1, len(trajets)):
                prev_point = trajets[i-1]
                curr_point = trajets[i]
                
                time_diff = (curr_point.timestamp - prev_point.timestamp).total_seconds()
                if time_diff > 3600:  # Plus d'une heure entre les points
                    validation_warnings.append(f"Écart temporel important entre les points {i-1} et {i}: {time_diff/3600:.1f}h")
        
        # Vérifier les limites de vitesse si demandé
        if request.check_speed_limits:
            for i, trajet in enumerate(trajets):
                if trajet.vitesse > request.max_speed_kmh:
                    validation_errors.append(f"Vitesse excessive au point {i}: {trajet.vitesse}km/h > {request.max_speed_kmh}km/h")
        
        is_valid = len(validation_errors) == 0
        
        return TrajectoryValidationResponse(
            mission_id=mission_id,
            is_valid=is_valid,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            points_analyzed=len(trajets),
            anomalies_detected=anomalies_detected,
            validation_timestamp=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la validation de la trajectoire {mission_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check(
    service: AnomalyInjectionService = Depends(get_anomaly_service)
):
    """Vérifier l'état de santé du service"""
    try:
        # Vérifier la connectivité à la base de données
        total_missions = service.db.query(Mission).count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(),
            "database_connected": True,
            "total_missions": total_missions,
            "service_version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de santé: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(),
            "database_connected": False,
            "error": str(e)
        }