import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Assurez-vous que le chemin d'importation correspond à votre structure de projet
from app.api.endpoints import missions
from app.api.endpoints import admin_routes
from app.api.endpoints import map_routes
from app.api.endpoints import auth
from app.api.endpoints import collaborateur_routes
from app.api.endpoints import anomaly_routes
from app.api.endpoints import anomaly

# Importez la fonction setup_security_middlewares depuis votre module de sécurité
from app.core.security_middleware import setup_security_middlewares
# Importez Base et engine pour la création des tables si nécessaire
from app.core.database import Base, engine, get_db # Assurez-vous que ces imports sont corrects

# Importation des services du simulateur et des services d'anomalies
from app.services.simulator_service import TrajectoryGeneratorService # Votre service original
from app.services.anomaly import AnomalyInjectionService # Votre service original
from app.services.anomaly_detection import AnomalyDetectionService # Votre service original
from app.services.anomaly_simulation_orchestrator import AnomalySimulationOrchestrator # Le nouvel orchestrateur

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales pour les services et la tâche d'arrière-plan de l'orchestrateur
generator_service: Optional[TrajectoryGeneratorService] = None
anomaly_injector_service: Optional[AnomalyInjectionService] = None
anomaly_detection_service: Optional[AnomalyDetectionService] = None
simulation_orchestrator: Optional[AnomalySimulationOrchestrator] = None
orchestrator_task: Optional[asyncio.Task] = None # Renommé pour plus de clarté

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gère les événements de démarrage et d'arrêt de l'application FastAPI.
    Initialise les services et lance l'orchestrateur de simulation en arrière-plan.
    """
    global generator_service, anomaly_injector_service, anomaly_detection_service, simulation_orchestrator, orchestrator_task

    # Crée les tables de la base de données au démarrage de l'application
    Base.metadata.create_all(bind=engine)
    logger.info("Tables de la base de données vérifiées/créées.")

    # Initialisation des sessions de base de données pour les services
    # Chaque service devrait idéalement avoir sa propre session gérée par FastAPI Depends,
    # mais pour l'initialisation globale dans lifespan, nous en créons une.
    # Assurez-vous que get_db() fournit une session qui peut être utilisée de cette manière.
    db_session_for_services = next(get_db()) 
    
    # Initialisation de VOS services (inchangés)
    generator_service = TrajectoryGeneratorService(db_session_for_services)
    anomaly_injector_service = AnomalyInjectionService(db_session_for_services)
    anomaly_detection_service = AnomalyDetectionService(db_session_for_services)
    
    # Initialisation du NOUVEL orchestrateur avec VOS services
    simulation_orchestrator = AnomalySimulationOrchestrator(
        db=db_session_for_services, # L'orchestrateur a besoin d'une session DB pour les requêtes directes
        generator_service=generator_service,
        injector_service=anomaly_injector_service,
        detector_service=anomaly_detection_service
    )

    # Entraîner les modèles de détection d'anomalies au démarrage (recommandé)
    logger.info("Démarrage de l'entraînement des modèles de détection d'anomalies...")
    await anomaly_detection_service.train_models()
    logger.info("Entraînement des modèles de détection d'anomalies terminé.")

    # Lancer la tâche de l'orchestrateur en arrière-plan
    # L'orchestrateur gère lui-même la connexion/déconnexion IoT Hub par le générateur.
    orchestrator_task = asyncio.create_task(simulation_orchestrator.start_monitoring(interval_seconds=2000))
    logger.info("Tâche de l'orchestrateur de simulation démarrée en arrière-plan.")
    
    yield # L'application FastAPI démarre et est prête à recevoir des requêtes

    # Événements d'arrêt : exécutés lorsque l'application s'arrête
    logger.info("Arrêt de l'application FastAPI...")
    if orchestrator_task and not orchestrator_task.done():
        simulation_orchestrator.stop() # Signaler à l'orchestrateur d'arrêter sa boucle
        orchestrator_task.cancel() # Annuler la tâche asyncio
        try:
            await orchestrator_task # Attendre que la tâche se termine (ou soit annulée)
        except asyncio.CancelledError:
            logger.info("Tâche de l'orchestrateur de simulation annulée.")
    
    # Fermer la session de base de données utilisée par les services dans lifespan
    if db_session_for_services:
        db_session_for_services.close()
        logger.info("Session de base de données fermée.")

    logger.info("Services et orchestrateur arrêtés et déconnectés.")


# Créez l'application FastAPI avec le gestionnaire de durée de vie
app = FastAPI(
    title="ONEE Suivi Deplacements API",
    description="API pour la gestion des missions et des déplacements des collaborateurs ONEE.",
    version="1.0.0",
    lifespan=lifespan # Utiliser le gestionnaire de durée de vie pour gérer le démarrage/l'arrêt
)

# Configuration CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration des middlewares de sécurité personnalisés
app = setup_security_middlewares(app)

# Inclusion de vos routeurs d'API
app.include_router(missions.router, tags=["Missions"])
app.include_router(auth.router)
app.include_router(admin_routes.router)
app.include_router(map_routes.router)
app.include_router(collaborateur_routes.router)
app.include_router(anomaly.router)

@app.get("/")
async def root():
    """Endpoint racine de l'API."""
    return {"message": "Welcome to ONEE Suivi Deplacements API!"}

@app.post("/simulate/run", summary="Déclencher manuellement une exécution de la simulation des trajectoires")
async def run_simulation_manually():
    """
    Déclenche une exécution unique du processus de génération, d'injection et de détection
    des trajectoires pour les missions actives via l'orchestrateur.
    """
    global simulation_orchestrator

    if not simulation_orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="L'orchestrateur de simulation n'est pas initialisé. Veuillez redémarrer l'application."
        )
    
    # Exécuter la logique de génération/injection/détection via l'orchestrateur
    # Nous lançons cela comme une tâche séparée pour ne pas bloquer la requête HTTP.
    asyncio.create_task(simulation_orchestrator.run_full_simulation_cycle())
    logger.info("Déclenchement manuel d'un cycle de simulation des trajectoires.")
    
    return {"message": "Un cycle de simulation des trajectoires a été déclenché en arrière-plan. Vérifiez les logs pour les détails."}

@app.get("/simulate/status", summary="Obtenir le statut de la tâche de simulation en arrière-plan")
async def get_simulation_status():
    """
    Renvoie le statut actuel de la tâche de l'orchestrateur de simulation en arrière-plan.
    """
    global orchestrator_task
    
    status_info = {
        "is_running": False,
        "details": "La tâche de l'orchestrateur n'est pas démarrée ou a terminé."
    }

    if orchestrator_task:
        status_info["is_running"] = not orchestrator_task.done()
        if orchestrator_task.done():
            if orchestrator_task.exception():
                status_info["details"] = f"La tâche de l'orchestrateur a échoué: {orchestrator_task.exception()}"
            else:
                status_info["details"] = "La tâche de l'orchestrateur a terminé avec succès."
        else:
            status_info["details"] = "La tâche de l'orchestrateur est en cours d'exécution."
    
    return status_info