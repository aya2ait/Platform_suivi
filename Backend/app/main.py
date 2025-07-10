import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Assurez-vous que le chemin d'importation correspond à votre structure de projet
from app.api.endpoints import missions
from app.api.endpoints import admin_routes
from app.api.endpoints import map_routes
from app.api.endpoints import auth
from app.api.endpoints import collaborateur_routes
from app.api.endpoints import anomaly_routes

# Importez la fonction setup_security_middlewares depuis votre module de sécurité
from app.core.security_middleware import setup_security_middlewares
# Importez Base et engine pour la création des tables si nécessaire
from app.core.database import Base, engine, get_db # Assurez-vous que ces imports sont corrects

# Importation des services du simulateur
from app.services.simulator_service import TrajectoryGeneratorService, TrajectoryMonitorService

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales pour les services du simulateur et la tâche d'arrière-plan
generator_service: Optional[TrajectoryGeneratorService] = None
monitor_service: Optional[TrajectoryMonitorService] = None
simulator_task: Optional[asyncio.Task] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gère les événements de démarrage et d'arrêt de l'application FastAPI.
    Initialise les services du simulateur et lance la génération de trajectoires en arrière-plan.
    """
    global generator_service, monitor_service, simulator_task

    # Crée les tables de la base de données au démarrage de l'application
    Base.metadata.create_all(bind=engine)
    logger.info("Tables de la base de données vérifiées/créées.")

    # Initialisation des services du simulateur
    # Nous utilisons next(get_db()) pour obtenir une session.
    db_session = next(get_db())
    generator_service = TrajectoryGeneratorService(db_session)
    monitor_service = TrajectoryMonitorService(generator_service)

    # Lancer la génération de trajectoires en temps réel comme tâche d'arrière-plan.
    # Vous pouvez choisir de lancer generate_and_process_trajectories une seule fois
    # ou start_real_time_generation pour un monitoring continu.
    # Pour cet exemple, nous lançons le monitoring en temps réel avec un intervalle de 30 secondes.
    if await generator_service.connect_to_iot_hub():
        simulator_task = asyncio.create_task(monitor_service.start_real_time_generation(interval_seconds=2000))
        logger.info("Tâche de génération de trajectoires démarrée en arrière-plan.")
    else:
        logger.error("Impossible de connecter le client IoT Hub. La génération de trajectoires ne démarrera pas.")

    yield # L'application FastAPI démarre et est prête à recevoir des requêtes

    # Événements d'arrêt : exécutés lorsque l'application s'arrête
    logger.info("Arrêt de l'application FastAPI...")
    if simulator_task and not simulator_task.done():
        monitor_service.stop() # Signaler au moniteur d'arrêter sa boucle
        simulator_task.cancel() # Annuler la tâche asyncio
        try:
            await simulator_task # Attendre que la tâche se termine (ou soit annulée)
        except asyncio.CancelledError:
            logger.info("Tâche de génération de trajectoires annulée.")
    
    # Déconnecter le client IoT Hub si il a été initialisé
    if generator_service:
        await generator_service.disconnect_from_iot_hub()
    
    # Fermer la session de base de données si elle a été ouverte
    if db_session:
        db_session.close()

    logger.info("Services du simulateur arrêtés et déconnectés.")


# Créez l'application FastAPI avec le gestionnaire de durée de vie
app = FastAPI(
    title="ONEE Suivi Deplacements API",
    description="API pour la gestion des missions et des déplacements des collaborateurs ONEE.",
    version="1.0.0",
    lifespan=lifespan # Utiliser le gestionnaire de durée de vie pour gérer le démarrage/l'arrêt
)

# Configuration CORS (Cross-Origin Resource Sharing)
# Ce middleware doit généralement être défini avant vos middlewares de sécurité
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Ajoutez toutes les origines de votre frontend
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes HTTP
    allow_headers=["*"],  # Autorise tous les en-têtes
)

# Configuration des middlewares de sécurité personnalisés
app = setup_security_middlewares(app)

# Inclusion de vos routeurs d'API
app.include_router(missions.router, tags=["Missions"])
app.include_router(auth.router) # Routeur d'authentification
app.include_router(admin_routes.router) # Routeur d'administration
app.include_router(map_routes.router) # Routeur de carte´
app.include_router(collaborateur_routes.router)
app.include_router(anomaly_routes.router)
@app.get("/")
async def root():
    """Endpoint racine de l'API."""
    return {"message": "Welcome to ONEE Suivi Deplacements API!"}