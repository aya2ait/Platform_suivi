# routers/anomaly_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.core.database import get_db
from app.schemas.anomaly_schema import (
    AnomalyRequest, AnomalyResponse, AnomalyConfig, 
    AnomalyType, SimulationConfig
)
from app.services.anomaly_generator_service import AnomalyGeneratorService
from app.models.models import Mission as MissionModel

router = APIRouter(prefix="/anomalies", tags=["anomalies"])
logger = logging.getLogger(__name__)

def get_anomaly_service(db: Session = Depends(get_db)) -> AnomalyGeneratorService:
    """Créer une instance du service d'anomalies"""
    return AnomalyGeneratorService(db)

@router.post("/generate", response_model=Dict[str, Any])
async def generate_anomalies(
    request: AnomalyRequest,
    db: Session = Depends(get_db),
    anomaly_service: AnomalyGeneratorService = Depends(get_anomaly_service)
):
    """
    Générer des anomalies pour une mission spécifique
    """
    try:
        # Vérifier que la mission existe
        mission = anomaly_service.get_mission_by_id(request.mission_id)
        if not mission:
            raise HTTPException(
                status_code=404, 
                detail=f"Mission {request.mission_id} non trouvée"
            )
        
        # Générer les points de trajectoire
        trajectory_points = anomaly_service.generate_trajectory_points(mission)
        
        if not trajectory_points:
            raise HTTPException(
                status_code=400, 
                detail="Impossible de générer des points de trajectoire"
            )
        
        # Appliquer les anomalies
        anomaly_configs = request.anomaly_types
        if request.force_generate:
            # Forcer la génération en mettant la probabilité à 1
            for config in anomaly_configs:
                config.probability = 1.0
        
        modified_points, detected_anomalies = await anomaly_service.apply_anomalies_to_trajectory(
            mission, trajectory_points, anomaly_configs
        )
        
        # Sauvegarder les anomalies
        if detected_anomalies:
            success = await anomaly_service.save_anomalies(detected_anomalies)
            if not success:
                logger.warning("Erreur lors de la sauvegarde des anomalies")
        
        return {
            "success": True,
            "mission_id": request.mission_id,
            "original_points_count": len(trajectory_points),
            "modified_points_count": len(modified_points),
            "anomalies_generated": len(detected_anomalies),
            "anomalies": [
                {
                    "type": anomaly.type.value,
                    "description": anomaly.description,
                    "timestamp": anomaly.timestamp.isoformat(),
                    "severity": anomaly.severity,
                    "details": anomaly.details
                }
                for anomaly in detected_anomalies
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'anomalies: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors de la génération d'anomalies"
        )

@router.get("/mission/{mission_id}", response_model=List[AnomalyResponse])
async def get_mission_anomalies(
    mission_id: int,
    anomaly_service: AnomalyGeneratorService = Depends(get_anomaly_service)
):
    """
    Récupérer toutes les anomalies d'une mission
    """
    try:
        # Vérifier que la mission existe
        mission = anomaly_service.get_mission_by_id(mission_id)
        if not mission:
            raise HTTPException(
                status_code=404, 
                detail=f"Mission {mission_id} non trouvée"
            )
        
        anomalies = await anomaly_service.get_mission_anomalies(mission_id)
        return anomalies
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des anomalies: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors de la récupération des anomalies"
        )

@router.get("/types", response_model=List[str])
async def get_anomaly_types():
    """
    Récupérer tous les types d'anomalies disponibles
    """
    return [anomaly_type.value for anomaly_type in AnomalyType]

@router.get("/statistics", response_model=Dict[str, Any])
async def get_anomaly_statistics(
    start_date: Optional[str] = Query(None, description="Date de début (ISO format)"),
    end_date: Optional[str] = Query(None, description="Date de fin (ISO format)"),
    anomaly_service: AnomalyGeneratorService = Depends(get_anomaly_service)
):
    """
    Obtenir des statistiques sur les anomalies
    """
    try:
        # Valider les dates si fournies
        if start_date:
            try:
                datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail="Format de date de début invalide. Utilisez le format ISO."
                )
        
        if end_date:
            try:
                datetime.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail="Format de date de fin invalide. Utilisez le format ISO."
                )
        
        stats = await anomaly_service.get_anomaly_statistics(start_date, end_date)
        
        if "error" in stats:
            raise HTTPException(
                status_code=500, 
                detail=f"Erreur lors du calcul des statistiques: {stats['error']}"
            )
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors du calcul des statistiques"
        )

@router.post("/simulate", response_model=Dict[str, Any])
async def simulate_mission_with_anomalies(
    mission_id: int,
    config: SimulationConfig = None,
    db: Session = Depends(get_db),
    anomaly_service: AnomalyGeneratorService = Depends(get_anomaly_service)
):
    """
    Simuler une mission complète avec anomalies
    """
    try:
        # Vérifier que la mission existe
        mission = anomaly_service.get_mission_by_id(mission_id)
        if not mission:
            raise HTTPException(
                status_code=404, 
                detail=f"Mission {mission_id} non trouvée"
            )
        
        # Utiliser la configuration par défaut si non fournie
        if not config:
            config = SimulationConfig()
        
        # Générer les points de trajectoire
        trajectory_points = anomaly_service.generate_trajectory_points(mission)
        
        if not trajectory_points:
            raise HTTPException(
                status_code=400, 
                detail="Impossible de générer des points de trajectoire"
            )
        
        detected_anomalies = []
        modified_points = trajectory_points
        
        # Appliquer les anomalies si activées
        if config.enable_anomalies:
            # Utiliser les anomalies par défaut ou celles de la configuration
            anomaly_configs = config.default_anomalies
            if not anomaly_configs:
                anomaly_configs = anomaly_service.DEFAULT_ANOMALY_CONFIG
            
            # Ajuster la fréquence
            for anomaly_config in anomaly_configs:
                anomaly_config.probability *= config.anomaly_frequency
            
            modified_points, detected_anomalies = await anomaly_service.apply_anomalies_to_trajectory(
                mission, trajectory_points, anomaly_configs
            )
            
            # Sauvegarder les anomalies
            if detected_anomalies:
                await anomaly_service.save_anomalies(detected_anomalies)
        
        return {
            "success": True,
            "mission_id": mission_id,
            "mission_info": {
                "id": mission.id,
                "start_date": mission.dateDebut.isoformat(),
                "end_date": mission.dateFin.isoformat(),
                "vehicle_id": mission.vehicule_id,
                "driver_id": mission.conducteur_id
            },
            "trajectory_info": {
                "original_points": len(trajectory_points),
                "modified_points": len(modified_points),
                "duration_hours": (mission.dateFin - mission.dateDebut).total_seconds() / 3600
            },
            "anomalies_info": {
                "enabled": config.enable_anomalies,
                "frequency": config.anomaly_frequency,
                "detected_count": len(detected_anomalies),
                "types_detected": [anomaly.type.value for anomaly in detected_anomalies]
            },
            "anomalies": [
                {
                    "type": anomaly.type.value,
                    "description": anomaly.description,
                    "timestamp": anomaly.timestamp.isoformat(),
                    "location": {
                        "latitude": anomaly.latitude,
                        "longitude": anomaly.longitude
                    },
                    "severity": anomaly.severity,
                    "details": anomaly.details
                }
                for anomaly in detected_anomalies
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la simulation: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors de la simulation"
        )

@router.get("/config/default", response_model=Dict[str, Any])
async def get_default_anomaly_config(
    anomaly_service: AnomalyGeneratorService = Depends(get_anomaly_service)
):
    """
    Récupérer la configuration par défaut des anomalies
    """
    try:
        default_config = anomaly_service.DEFAULT_ANOMALY_CONFIG
        
        return {
            "anomaly_types": [
                {
                    "type": config.type.value,
                    "probability": config.probability,
                    "severity": config.severity,
                    "parameters": config.parameters
                }
                for config in default_config
            ],
            "total_types": len(default_config),
            "average_probability": sum(config.probability for config in default_config) / len(default_config)
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la configuration: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors de la récupération de la configuration"
        )

@router.delete("/mission/{mission_id}", response_model=Dict[str, Any])
async def delete_mission_anomalies(
    mission_id: int,
    db: Session = Depends(get_db)
):
    """
    Supprimer toutes les anomalies d'une mission
    """
    try:
        from app.models.models import Anomalie as AnomalieModel
        
        # Vérifier que la mission existe
        mission = db.query(MissionModel).filter(MissionModel.id == mission_id).first()
        if not mission:
            raise HTTPException(
                status_code=404, 
                detail=f"Mission {mission_id} non trouvée"
            )
        
        # Supprimer les anomalies
        deleted_count = db.query(AnomalieModel).filter(
            AnomalieModel.mission_id == mission_id
        ).delete()
        
        db.commit()
        
        return {
            "success": True,
            "mission_id": mission_id,
            "deleted_anomalies": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la suppression des anomalies: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors de la suppression des anomalies"
        )

@router.post("/batch-generate", response_model=Dict[str, Any])
async def batch_generate_anomalies(
    mission_ids: List[int],
    anomaly_configs: List[AnomalyConfig],
    force_generate: bool = False,
    db: Session = Depends(get_db),
    anomaly_service: AnomalyGeneratorService = Depends(get_anomaly_service)
):
    """
    Générer des anomalies pour plusieurs missions en lot
    """
    try:
        results = []
        total_anomalies = 0
        
        for mission_id in mission_ids:
            try:
                # Vérifier que la mission existe
                mission = anomaly_service.get_mission_by_id(mission_id)
                if not mission:
                    results.append({
                        "mission_id": mission_id,
                        "success": False,
                        "error": "Mission non trouvée"
                    })
                    continue
                
                # Générer les points de trajectoire
                trajectory_points = anomaly_service.generate_trajectory_points(mission)
                
                if not trajectory_points:
                    results.append({
                        "mission_id": mission_id,
                        "success": False,
                        "error": "Impossible de générer des points de trajectoire"
                    })
                    continue
                
                # Appliquer les anomalies
                configs_to_use = anomaly_configs.copy()
                if force_generate:
                    for config in configs_to_use:
                        config.probability = 1.0
                
                modified_points, detected_anomalies = await anomaly_service.apply_anomalies_to_trajectory(
                    mission, trajectory_points, configs_to_use
                )
                
                # Sauvegarder les anomalies
                if detected_anomalies:
                    await anomaly_service.save_anomalies(detected_anomalies)
                
                total_anomalies += len(detected_anomalies)
                
                results.append({
                    "mission_id": mission_id,
                    "success": True,
                    "anomalies_generated": len(detected_anomalies),
                    "anomaly_types": [anomaly.type.value for anomaly in detected_anomalies]
                })
                
            except Exception as e:
                logger.error(f"Erreur pour mission {mission_id}: {e}")
                results.append({
                    "mission_id": mission_id,
                    "success": False,
                    "error": str(e)
                })
        
        successful_missions = [r for r in results if r["success"]]
        
        return {
            "success": True,
            "total_missions": len(mission_ids),
            "successful_missions": len(successful_missions),
            "failed_missions": len(mission_ids) - len(successful_missions),
            "total_anomalies_generated": total_anomalies,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération en lot: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur interne lors de la génération en lot"
        )