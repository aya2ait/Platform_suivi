# app/services/anomaly_simulation_orchestrator.py (Nouveau fichier)

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from sqlalchemy.orm import Session

# Importez vos services existants
from app.services.simulator_service import TrajectoryGeneratorService
from app.services.anomaly import AnomalyInjectionService
from app.services.anomaly_detection import AnomalyDetectionService, AnomalyScore

# Importez vos modèles et schémas nécessaires
from app.models.models import Mission, Trajet, Anomalie
from app.schemas.anomaly import TrajectPoint # Assurez-vous que c'est le bon chemin pour TrajectPoint

logger = logging.getLogger(__name__)

class AnomalySimulationOrchestrator:
    """
    Orchestre la génération, l'injection et la détection d'anomalies
    en utilisant les services existants.
    Cette classe ne modifie pas les services sous-jacents.
    """

    def __init__(self, db: Session, 
                 generator_service: TrajectoryGeneratorService,
                 injector_service: AnomalyInjectionService,
                 detector_service: AnomalyDetectionService):
        self.db = db
        self.generator_service = generator_service
        self.injector_service = injector_service
        self.detector_service = detector_service
        self.running = False # Pour contrôler la boucle de simulation

    async def run_full_simulation_cycle(self, anomaly_injection_probability: float = 0.3):
        """
        Exécute un cycle complet de simulation :
        1. Récupère les missions actives.
        2. Pour chaque mission :
           a. Génère une trajectoire "propre".
           b. Sauvegarde cette trajectoire.
           c. Décide d'injecter ou non une anomalie. Si oui, modifie la trajectoire en DB.
           d. Récupère la trajectoire (potentiellement modifiée) depuis la DB.
           e. Détecte les anomalies sur cette trajectoire.
           f. Envoie la trajectoire finale et les statuts à IoT Hub.
        """
        logger.info("Début d'un cycle complet de simulation d'anomalies.")

        # Assurez-vous que le générateur est connecté à IoT Hub pour l'envoi de messages
        if not self.generator_service.iot_client:
            if not await self.generator_service.connect_to_iot_hub():
                logger.error("Impossible de connecter le générateur à IoT Hub. Le cycle de simulation ne peut pas continuer.")
                return

        try:
            missions = await self.generator_service.get_active_missions()
            
            if not missions:
                logger.info("Aucune mission active trouvée pour ce cycle.")
                return
            
            for mission in missions:
                logger.info(f"Orchestration pour la mission {mission.id}: {mission.objet}")
                
                # Étape 1: Générer la trajectoire "propre" initiale
                raw_generated_points = self.generator_service.generate_trajectory_points(mission)
                
                # Convertir les points générés en TrajectPoint complets pour l'injection/détection
                # En s'assurant que l'ID est géré correctement (None pour les points non encore sauvegardés)
                initial_points_for_processing: List[TrajectPoint] = []
                for p in raw_generated_points:
                    # Si p.id n'existe pas, nous utilisons None. Si TrajectPoint est un BaseModel,
                    # il gérera l'absence de 'id' en utilisant sa valeur par défaut Optional[int] = None.
                    # Cependant, pour être explicite et éviter l'AttributeError si 'p' n'a pas 'id',
                    # nous pouvons utiliser getattr.
                    point_id = getattr(p, 'id', None) 
                    initial_points_for_processing.append(TrajectPoint(
                        id=point_id, # Utilise l'ID s'il existe, sinon None
                        mission_id=p.mission_id,
                        timestamp=p.timestamp,
                        latitude=p.latitude,
                        longitude=p.longitude,
                        vitesse=p.vitesse,
                        mission_start=mission.dateDebut, # Ajouté ici
                        mission_end=mission.dateFin     # Ajouté ici
                    ))

                # Sauvegarder la trajectoire propre dans la DB via le générateur
                # Le générateur original n'a pas de logique pour supprimer les anciens points
                # avant d'insérer, ce qui peut créer des doublons si la mission est re-traitée.
                # Il faudrait gérer cela dans le générateur si c'est un problème.
                if not await self.generator_service.save_trajectory_points(initial_points_for_processing):
                    logger.error(f"Échec de la sauvegarde de la trajectoire initiale pour mission {mission.id}.")
                    await self.generator_service.send_mission_status(mission, "GENERATION_FAILED")
                    continue
                await self.generator_service.send_mission_status(mission, "TRAJECTORY_GENERATED")

                # Étape 2: Potentiellement injecter des anomalies
                # L'injecteur lira et écrira directement dans la DB
                injection_result = await self.injector_service.inject_anomalies_for_mission(mission.id)
                
                if injection_result.success and injection_result.anomalies_injected:
                    logger.info(f"Anomalies injectées pour la mission {mission.id}: {', '.join(injection_result.anomalies_injected)}")
                    await self.generator_service.send_mission_status(mission, "ANOMALY_INJECTED")
                else:
                    logger.info(f"Aucune anomalie injectée pour la mission {mission.id} (ou échec de l'injection).")
                    await self.generator_service.send_mission_status(mission, "NO_ANOMALY_INJECTED")

                # Étape 3: Récupérer la trajectoire finale (potentiellement contaminée) depuis la DB
                # Puisque nous ne touchons pas aux services, nous allons devoir récupérer les points
                # et les enrichir avec mission_start/end pour le détecteur.
                db_trajets = self.db.query(Trajet).filter(Trajet.mission_id == mission.id).order_by(Trajet.timestamp).all()
                
                final_trajectory_for_detection: List[TrajectPoint] = []
                for t in db_trajets:
                    final_trajectory_for_detection.append(TrajectPoint(
                        id=t.id,
                        mission_id=t.mission_id,
                        timestamp=t.timestamp,
                        latitude=float(t.latitude),
                        longitude=float(t.longitude),
                        vitesse=float(t.vitesse),
                        mission_start=mission.dateDebut, # Enrichissement
                        mission_end=mission.dateFin     # Enrichissement
                    ))

                if not final_trajectory_for_detection:
                    logger.warning(f"Aucune trajectoire disponible pour la détection pour la mission {mission.id}")
                    await self.generator_service.send_mission_status(mission, "NO_TRAJECTORY_FOR_DETECTION")
                    continue

                # Étape 4: Détecter les anomalies sur la trajectoire finale
                detected_anomalies: List[AnomalyScore] = await self.detector_service.detect_anomalies(final_trajectory_for_detection)
                
                if detected_anomalies:
                    logger.warning(f"Anomalies DÉTECTÉES pour la mission {mission.id}:")
                    for anomaly in detected_anomalies:
                        logger.warning(f"  - Type: {anomaly.anomaly_type}, Score: {anomaly.score:.2f}, Sévérité: {anomaly.severity}")
                    await self.generator_service.send_mission_status(mission, "ANOMALY_DETECTED")
                else:
                    logger.info(f"Aucune anomalie DÉTECTÉE pour la mission {mission.id}.")
                    await self.generator_service.send_mission_status(mission, "NO_ANOMALY_DETECTED")

                # Étape 5: Envoyer la trajectoire (potentiellement contaminée) à IoT Hub
                await self.generator_service.send_to_iot_hub(final_trajectory_for_detection)
                await self.generator_service.send_mission_status(mission, "TRAJECTORY_SENT_TO_IOT_HUB")

                # Pause entre le traitement des missions
                await asyncio.sleep(2) 
            
            logger.info(f"Cycle de simulation terminé pour toutes les missions actives.")
            
        except Exception as e:
            logger.error(f"Erreur générale dans le cycle de simulation: {e}")
            
        finally:
            # Déconnexion de IoT Hub à la fin du cycle
            await self.generator_service.disconnect_from_iot_hub()

    async def start_monitoring(self, interval_seconds: int = 2000):
        """
        Démarre la boucle de monitoring qui exécute des cycles de simulation périodiquement.
        """
        self.running = True
        logger.info(f"Démarrage du monitoring de simulation (intervalle: {interval_seconds}s)")
        while self.running:
            try:
                await self.run_full_simulation_cycle()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("Tâche de monitoring de simulation annulée.")
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle de monitoring: {e}")
                await asyncio.sleep(interval_seconds) # Attendre avant de réessayer
        logger.info("Boucle de monitoring de simulation terminée.")

    def stop(self):
        """Arrête la boucle de monitoring de simulation."""
        self.running = False
        logger.info("Signal d'arrêt envoyé à l'orchestrateur de simulation.")