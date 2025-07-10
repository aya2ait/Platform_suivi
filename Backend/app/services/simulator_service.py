import asyncio
import json
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from math import radians, cos, sin, asin, sqrt, atan2, degrees

from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import IOT_HUB_CONNECTION_STRING, MOROCCO_BOUNDS, MAJOR_CITIES
from app.schemas.simulator_schema import TrajectPoint, Mission

logger = logging.getLogger(__name__)

class TrajectoryGeneratorService:
    """Générateur de trajectoires aléatoires pour les missions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.iot_client = None
        
        self.MOROCCO_BOUNDS = MOROCCO_BOUNDS
        self.MAJOR_CITIES = MAJOR_CITIES
    
    def parse_date(self, date_str) -> datetime:
        """Parser une date depuis différents formats possibles"""
        if isinstance(date_str, datetime):
            return date_str
        
        if isinstance(date_str, str):
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%SZ'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            logger.warning(f"Impossible de parser la date: {date_str}. Utilisation de la date actuelle.")
            return datetime.now()
        
        logger.warning(f"Type de date non reconnu: {type(date_str)}. Utilisation de la date actuelle.")
        return datetime.now()
    
    async def connect_to_iot_hub(self):
        """Établir la connexion avec Azure IoT Hub"""
        try:
            self.iot_client = IoTHubDeviceClient.create_from_connection_string(
                IOT_HUB_CONNECTION_STRING
            )
            await self.iot_client.connect()
            logger.info("Connexion établie avec Azure IoT Hub")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la connexion à IoT Hub: {e}")
            return False
    
    async def disconnect_from_iot_hub(self):
        """Fermer la connexion avec Azure IoT Hub"""
        if self.iot_client:
            try:
                await self.iot_client.disconnect()
                logger.info("Déconnexion d'Azure IoT Hub")
            except Exception as e:
                logger.error(f"Erreur lors de la déconnexion: {e}")
    
    async def get_active_missions(self) -> List[Mission]:
        """Récupérer les missions en cours depuis la base de données"""
        try:
            query = text("""
                SELECT id, objet, statut, "dateDebut", "dateFin", 
                       trajet_predefini, vehicule_id
                FROM mission
                WHERE statut = 'EN_COURS' 
            """)
            
            result = self.db.execute(query)
            missions = []
            
            for row in result:
                date_debut = self.parse_date(row.dateDebut)
                date_fin = self.parse_date(row.dateFin)
                
                if date_fin <= date_debut:
                    date_debut = datetime.now()
                    date_fin = date_debut + timedelta(hours=2)
                    logger.warning(f"Dates invalides pour mission {row.id}. Utilisation de dates par défaut.")
                
                mission = Mission(
                    id=row.id,
                    objet=row.objet,
                    statut=row.statut,
                    dateDebut=date_debut,
                    dateFin=date_fin,
                    trajet_predefini=row.trajet_predefini,
                    vehicule_id=row.vehicule_id
                )
                missions.append(mission)
            
            logger.info(f"Trouvé {len(missions)} missions actives")
            return missions
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des missions: {e}")
            return []
    
    def parse_predefined_route(self, route_json: str) -> List[Tuple[float, float]]:
        """Parser le trajet prédéfini depuis le JSON"""
        try:
            if not route_json:
                return []
            
            route_data = json.loads(route_json)
            return [(point['latitude'], point['longitude']) for point in route_data]
        except Exception as e:
            logger.warning(f"Erreur lors du parsing du trajet prédéfini: {e}")
            return []
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer la distance entre deux points GPS (formule de Haversine)"""
        R = 6371  # Rayon de la Terre en km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        return R * c
    
    def calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculer le cap entre deux points GPS"""
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        
        y = sin(dlon) * cos(lat2)
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        
        bearing = atan2(y, x)
        return (degrees(bearing) + 360) % 360
    
    def generate_realistic_speed(self, previous_speed: float, terrain_type: str = "urban") -> float:
        """Générer une vitesse réaliste basée sur le terrain"""
        base_speeds = {
            "urban": (20, 50),     # Ville: 20-50 km/h
            "highway": (60, 120),  # Autoroute: 60-120 km/h
            "rural": (40, 80),     # Campagne: 40-80 km/h
            "mountain": (15, 40)   # Montagne: 15-40 km/h
        }
        
        min_speed, max_speed = base_speeds.get(terrain_type, (20, 50))
        
        speed_variation = random.uniform(-10, 10)
        new_speed = previous_speed + speed_variation
        
        new_speed = max(min_speed, min(max_speed, new_speed))
        
        if random.random() < 0.1:  # 10% de chance d'arrêt
            new_speed = random.uniform(0, 5)
        
        return round(new_speed, 1)
    
    def generate_route_waypoints(self, start_point: Tuple[float, float], 
                                  end_point: Tuple[float, float], 
                                  num_points: int = 10) -> List[Tuple[float, float]]:
        """Générer des points intermédiaires entre deux points"""
        waypoints = []
        
        for i in range(num_points):
            ratio = i / (num_points - 1)
            
            lat = start_point[0] + (end_point[0] - start_point[0]) * ratio
            lon = start_point[1] + (end_point[1] - start_point[1]) * ratio
            
            lat_variation = random.uniform(-0.01, 0.01)
            lon_variation = random.uniform(-0.01, 0.01)
            
            lat += lat_variation
            lon += lon_variation
            
            lat = max(self.MOROCCO_BOUNDS['min_lat'], 
                      min(self.MOROCCO_BOUNDS['max_lat'], lat))
            lon = max(self.MOROCCO_BOUNDS['min_lon'], 
                      min(self.MOROCCO_BOUNDS['max_lon'], lon))
            
            waypoints.append((lat, lon))
        
        return waypoints
    
    def generate_trajectory_points(self, mission: Mission) -> List[TrajectPoint]:
        """Générer des points de trajet pour une mission"""
        points = []
        
        predefined_route = self.parse_predefined_route(mission.trajet_predefini)
        
        if predefined_route:
            start_point = predefined_route[0]
            end_point = predefined_route[-1] if len(predefined_route) > 1 else start_point
            waypoints = predefined_route
        else:
            cities = list(self.MAJOR_CITIES.values())
            start_point = random.choice(cities)
            end_point = random.choice([city for city in cities if city != start_point])
            waypoints = self.generate_route_waypoints(start_point, end_point, 8)
        
        mission_duration = (mission.dateFin - mission.dateDebut).total_seconds()
        
        if mission_duration <= 0:
            mission_duration = 7200  # 2 heures par default
            logger.warning(f"Durée de mission invalide pour mission {mission.id}. Utilisation de 2h par défaut.")
        
        num_points = random.randint(20, 50)  # Entre 20 et 50 points
        time_interval = mission_duration / num_points
        
        current_time = mission.dateDebut
        current_speed = random.uniform(30, 60)  # Vitesse initiale
        
        for i in range(num_points):
            progress = i / num_points
            waypoint_index = min(int(progress * len(waypoints)), len(waypoints) - 1)
            base_lat, base_lon = waypoints[waypoint_index]
            
            lat_variation = random.uniform(-0.005, 0.005)
            lon_variation = random.uniform(-0.005, 0.005)
            
            lat = base_lat + lat_variation
            lon = base_lon + lon_variation
            
            terrain_type = "urban" if any(
                self.calculate_distance(lat, lon, city[0], city[1]) < 20 
                for city in self.MAJOR_CITIES.values()
            ) else "rural"
            
            current_speed = self.generate_realistic_speed(current_speed, terrain_type)
            
            point = TrajectPoint(
                latitude=lat,
                longitude=lon,
                timestamp=current_time,
                vitesse=current_speed,
                mission_id=mission.id
            )
            points.append(point)
            
            current_time += timedelta(seconds=time_interval)
        
        logger.info(f"Généré {len(points)} points pour la mission {mission.id}")
        return points
    
    async def save_trajectory_points(self, points: List[TrajectPoint]) -> bool:
        """Sauvegarder les points de trajet en base de données"""
        try:
            for point in points:
                query = text("""
                    INSERT INTO trajet (mission_id, timestamp, latitude, longitude, vitesse)
                    VALUES (:mission_id, :timestamp, :latitude, :longitude, :vitesse)
                """)
                
                self.db.execute(query, {
                    "mission_id": point.mission_id,
                    "timestamp": point.timestamp,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "vitesse": point.vitesse
                })
            
            self.db.commit()
            logger.info(f"Sauvegardé {len(points)} points de trajet")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False
    
    async def send_to_iot_hub(self, points: List[TrajectPoint]):
        """Envoyer les points de trajet vers Azure IoT Hub"""
        if not self.iot_client:
            logger.warning("Client IoT Hub non connecté")
            return
        
        try:
            for point in points:
                telemetry_data = {
                    "deviceId": "mydvice",
                    "mission_id": point.mission_id,
                    "timestamp": point.timestamp.isoformat(),
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "vitesse": point.vitesse,
                    "type": "trajectory_point",
                    "messageType": "telemetry"
                }
                
                message = Message(json.dumps(telemetry_data))
                
                message.custom_properties["mission_id"] = str(point.mission_id)
                message.custom_properties["data_type"] = "trajectory"
                message.custom_properties["timestamp"] = point.timestamp.isoformat()
                
                message.content_type = "application/json"
                message.content_encoding = "utf-8"
                
                await self.iot_client.send_message(message)
                
                await asyncio.sleep(0.1)
            
            logger.info(f"Envoyé {len(points)} points vers Azure IoT Hub")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi vers IoT Hub: {e}")
    
    async def send_mission_status(self, mission: Mission, status: str):
        """Envoyer le statut de la mission vers IoT Hub"""
        if not self.iot_client:
            return
        
        try:
            status_data = {
                "deviceId": "mydvice",
                "mission_id": mission.id,
                "mission_objet": mission.objet,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "vehicule_id": mission.vehicule_id,
                "type": "mission_status",
                "messageType": "status"
            }
            
            message = Message(json.dumps(status_data))
            message.custom_properties["mission_id"] = str(mission.id)
            message.custom_properties["data_type"] = "status"
            message.custom_properties["status"] = status
            message.content_type = "application/json"
            message.content_encoding = "utf-8"
            
            await self.iot_client.send_message(message)
            logger.info(f"Statut mission {mission.id} envoyé: {status}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du statut: {e}")
    
    async def generate_and_process_trajectories(self):
        """Processus principal pour générer et traiter les trajectoires"""
        logger.info("Début de la génération des trajectoires")
        
        if not await self.connect_to_iot_hub():
            logger.error("Impossible de se connecter à IoT Hub")
            return
        
        try:
            missions = await self.get_active_missions()
            
            if not missions:
                logger.info("Aucune mission active trouvée")
                return
            
            all_points = []
            
            for mission in missions:
                logger.info(f"Génération de trajet pour mission {mission.id}: {mission.objet}")
                
                await self.send_mission_status(mission, "PROCESSING")
                
                points = self.generate_trajectory_points(mission)
                all_points.extend(points)
                
                if await self.save_trajectory_points(points):
                    await self.send_to_iot_hub(points)
                    await self.send_mission_status(mission, "TRAJECTORY_SENT")
                else:
                    await self.send_mission_status(mission, "ERROR")
                
                await asyncio.sleep(2)
            
            logger.info(f"Traitement terminé. Total: {len(all_points)} points générés")
            
        finally:
            await self.disconnect_from_iot_hub()

class TrajectoryMonitorService:
    """Moniteur pour générer des points en temps réel"""
    
    def __init__(self, generator_service: TrajectoryGeneratorService):
        self.generator_service = generator_service
        self.running = False
    
    async def start_real_time_generation(self, interval_seconds: int = 60):
        """Démarrer la génération en temps réel"""
        self.running = True
        logger.info(f"Démarrage du monitoring en temps réel (intervalle: {interval_seconds}s)")
        
        while self.running:
            try:
                await self.generator_service.generate_and_process_trajectories()
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Erreur dans le monitoring: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def send_heartbeat(self):
        """Envoyer un signal de vie périodique"""
        if not self.generator_service.iot_client:
            return
        
        try:
            heartbeat_data = {
                "deviceId": "mydvice",
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat(),
                "status": "alive",
                "messageType": "heartbeat"
            }
            
            message = Message(json.dumps(heartbeat_data))
            message.custom_properties["data_type"] = "heartbeat"
            message.content_type = "application/json"
            
            await self.generator_service.iot_client.send_message(message)
            logger.info("Heartbeat envoyé")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du heartbeat: {e}")
    
    def stop(self):
        """Arrêter la génération"""
        self.running = False
        logger.info("Arrêt du monitoring")