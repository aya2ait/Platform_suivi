# app/routes/map_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Annotated
from datetime import datetime

from app.core.database import get_db
from app.core.auth_dependencies import (
    get_current_active_user, can_read_mission,
    check_mission_access
)
from app.models.models import Utilisateur
from app.services.map_service import MapService
from app.schemas.map_schemas import (
    MissionMapResponse, MissionMapFilter, TrajetResponse,
    MissionAnalytics, MapConfiguration, LiveTrackingUpdate
)

router = APIRouter(prefix="/api/map", tags=["Cartographie"])

@router.get(
    "/missions",
    response_model=MissionMapResponse,
    summary="Récupérer les missions pour l'affichage sur carte",
    description="""
    Récupère les missions avec leurs trajets pour l'affichage sur une carte interactive.
    Supporte de nombreux filtres pour personnaliser l'affichage.
    """
)
async def get_missions_map(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Utilisateur, Depends(can_read_mission)],
    
    # Filtres de base
    statut: Optional[List[str]] = Query(
        default=None, 
        description="Filtrer par statut (CREEE, EN_COURS, TERMINEE, ANNULEE)"
    ),
    direction_id: Optional[int] = Query(
        default=None, 
        description="ID de la direction"
    ),
    
    # Filtres temporels
    date_debut: Optional[datetime] = Query(
        default=None,
        description="Date de début minimum (format ISO: 2024-01-01T00:00:00)"
    ),
    date_fin: Optional[datetime] = Query(
        default=None,
        description="Date de fin maximum (format ISO: 2024-12-31T23:59:59)"
    ),
    
    # Filtres spécifiques
    avec_anomalies: Optional[bool] = Query(
        default=None,
        description="Afficher uniquement les missions avec anomalies"
    ),
    moyen_transport: Optional[str] = Query(
        default=None,
        description="Filtrer par moyen de transport"
    ),
    vehicule_id: Optional[int] = Query(
        default=None,
        description="ID du véhicule"
    ),
    
    # Paramètres d'affichage
    limit: int = Query(
        default=100,
        le=500,
        description="Nombre maximum de missions à retourner"
    )
):
    """Récupérer les missions avec filtres pour l'affichage cartographique"""
    
    # Construction des filtres
    filters = MissionMapFilter(
        statut=statut,
        direction_id=direction_id,
        date_debut=date_debut,
        date_fin=date_fin,
        avec_anomalies=avec_anomalies,
        moyen_transport=moyen_transport,
        vehicule_id=vehicule_id
    )
    
    # Utilisation du service
    map_service = MapService(db)
    
    try:
        result = map_service.get_missions_for_map(
            filters=filters,
            user_role=current_user.role,
            user_id=current_user.id,
            limit=limit
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des missions: {str(e)}"
        )

@router.get(
    "/missions/{mission_id}/trajet",
    response_model=TrajetResponse,
    summary="Récupérer le trajet complet d'une mission",
    description="Récupère tous les points GPS d'une mission avec statistiques"
)
async def get_mission_trajet(
    mission_id: Annotated[int, Path(description="ID de la mission")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Utilisateur, Depends(can_read_mission)]
):
    """Récupérer le trajet complet d'une mission"""
    
    # Vérifier l'accès à la mission
    await check_mission_access(mission_id, current_user, db)
    
    map_service = MapService(db)
    
    try:
        trajet = map_service.get_mission_trajet(mission_id)
        return trajet
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération du trajet: {str(e)}"
        )

@router.get(
    "/missions/{mission_id}/analytics",
    response_model=MissionAnalytics,
    summary="Analytics détaillées d'une mission",
    description="Récupère les analytics complètes d'une mission (statistiques, anomalies, écarts)"
)
async def get_mission_analytics(
    mission_id: Annotated[int, Path(description="ID de la mission")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Utilisateur, Depends(can_read_mission)]
):
    """Récupérer les analytics détaillées d'une mission"""
    
    # Vérifier l'accès à la mission
    await check_mission_access(mission_id, current_user, db)
    
    map_service = MapService(db)
    
    try:
        analytics = map_service.get_mission_analytics(mission_id)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des analytics: {str(e)}"
        )
    

@router.get(
    "/missions/live",
    response_model=List[LiveTrackingUpdate],
    summary="Suivi en temps réel des missions actives",
    description="Récupère les dernières positions des missions en cours"
)
async def get_live_tracking(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Utilisateur, Depends(can_read_mission)],
    mission_ids: Optional[List[int]] = Query(
        default=None,
        description="IDs spécifiques des missions à suivre. Si vide, toutes les missions actives"
    )
):
    """Suivi en temps réel des missions actives"""
    
    map_service = MapService(db)
    
    try:
        if not mission_ids:
            # CORRECTION: Récupérer toutes les missions en cours pour l'utilisateur
            from app.models.models import Mission, Directeur
            
            query = db.query(Mission).filter(Mission.statut == "EN_COURS")
            
            # Filtrer par rôle utilisateur - CORRECTION de la logique
            if current_user.role == "DIRECTEUR":
                directeur = db.query(Directeur).filter(
                    Directeur.utilisateur_id == current_user.id
                ).first()
                if directeur:
                    # Filtrer SEULEMENT les missions de ce directeur
                    query = query.filter(Mission.directeur_id == directeur.id)
                else:
                    # Si pas de profil directeur, aucune mission
                    return []
            
            missions = query.all()
            mission_ids = [m.id for m in missions]
        else:
            # Si des IDs spécifiques sont fournis, vérifier l'accès
            if current_user.role == "DIRECTEUR":
                directeur = db.query(Directeur).filter(
                    Directeur.utilisateur_id == current_user.id
                ).first()
                if directeur:
                    # Filtrer les mission_ids pour ne garder que celles du directeur
                    allowed_missions = db.query(Mission.id).filter(
                        Mission.directeur_id == directeur.id,
                        Mission.id.in_(mission_ids)
                    ).all()
                    mission_ids = [m.id for m in allowed_missions]
                else:
                    mission_ids = []
        
        updates = map_service.get_live_mission_updates(mission_ids)
        
        return [
            LiveTrackingUpdate(
                mission_id=update['mission_id'],
                timestamp=update['timestamp'],
                latitude=update['latitude'],
                longitude=update['longitude'],
                vitesse=update['vitesse'],
                statut=update['statut']
            )
            for update in updates
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du suivi en temps réel: {str(e)}"
        )



@router.get(
    "/configuration",
    response_model=MapConfiguration,
    summary="Configuration de la carte",
    description="Récupère la configuration par défaut de la carte (centre, zoom, couleurs)"
)
async def get_map_configuration(
    current_user: Annotated[Utilisateur, Depends(get_current_active_user)]
):
    """Récupérer la configuration de la carte"""
    
    return MapConfiguration(
        centre_latitude=31.7917,  # Centre du Maroc
        centre_longitude=-7.0926,
        zoom_initial=6,
        couches_disponibles=["satellite", "terrain", "roadmap", "hybrid"],
        couleurs_statut={
            "CREEE": "#FFA500",      # Orange
            "EN_COURS": "#0000FF",   # Bleu
            "TERMINEE": "#008000",   # Vert
            "ANNULEE": "#FF0000",    # Rouge
            "SUSPENDUE": "#800080"   # Violet
        }
    )

@router.get(
    "/missions/{mission_id}/export-kml",
    summary="Exporter le trajet en format KML",
    description="Exporte le trajet d'une mission au format KML pour Google Earth"
)
async def export_mission_kml(
    mission_id: Annotated[int, Path(description="ID de la mission")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Utilisateur, Depends(can_read_mission)]
):
    """Exporter le trajet d'une mission au format KML"""
    
    # Vérifier l'accès à la mission
    await check_mission_access(mission_id, current_user, db)
    
    from fastapi.responses import Response
    
    map_service = MapService(db)
    
    try:
        trajet = map_service.get_mission_trajet(mission_id)
        
        # Récupérer les informations de la mission
        from app.models.models import Mission
        mission = db.query(Mission).filter(Mission.id == mission_id).first()
        
        if not mission:
            raise HTTPException(status_code=404, detail="Mission non trouvée")
        
        # Générer le KML
        kml_content = _generate_kml(mission, trajet)
        
        return Response(
            content=kml_content,
            media_type="application/vnd.google-earth.kml+xml",
            headers={
                "Content-Disposition": f"attachment; filename=mission_{mission_id}_trajet.kml"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'export KML: {str(e)}"
        )

@router.get(
    "/stats/heatmap",
    summary="Données pour heatmap des trajets",
    description="Récupère les données de densité de passage pour créer une heatmap"
)
async def get_heatmap_data(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Utilisateur, Depends(can_read_mission)],
    date_debut: Optional[datetime] = Query(
        default=None,
        description="Date de début pour la période d'analyse"
    ),
    date_fin: Optional[datetime] = Query(
        default=None,
        description="Date de fin pour la période d'analyse"
    ),
    precision: float = Query(
        default=0.01,
        description="Précision de la grille (en degrés)"
    )
):
    """Récupérer les données pour créer une heatmap des trajets"""
    
    from app.models.models import Trajet, Mission, Directeur
    from collections import defaultdict
    
    try:
        # Construction de la requête
        query = db.query(Trajet).join(Mission)
        
        # Filtrer par rôle utilisateur
        if current_user.role == "DIRECTEUR":
            directeur = db.query(Directeur).filter(
                Directeur.utilisateur_id == current_user.id
            ).first()
            if directeur:
                query = query.filter(Mission.directeur_id == directeur.id)
        
        # Filtres temporels
        if date_debut:
            query = query.filter(Mission.dateDebut >= date_debut)
        if date_fin:
            query = query.filter(Mission.dateFin <= date_fin)
        
        trajets = query.all()
        
        # Créer la grille de densité
        density_grid = defaultdict(int)
        
        for trajet in trajets:
            # Arrondir les coordonnées selon la précision
            lat_rounded = round(float(trajet.latitude) / precision) * precision
            lon_rounded = round(float(trajet.longitude) / precision) * precision
            
            grid_key = f"{lat_rounded},{lon_rounded}"
            density_grid[grid_key] += 1
        
        # Convertir en format compatible avec les bibliothèques de heatmap
        heatmap_data = []
        for grid_key, count in density_grid.items():
            lat, lon = map(float, grid_key.split(','))
            heatmap_data.append({
                "lat": lat,
                "lng": lon,
                "count": count
            })
        
        return {
            "data": heatmap_data,
            "total_points": len(trajets),
            "periode": {
                "debut": date_debut,
                "fin": date_fin
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération de la heatmap: {str(e)}"
        )

def _generate_kml(mission, trajet: TrajetResponse) -> str:
    """Générer le contenu KML pour une mission"""
    
    kml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>Mission {mission_id} - {objet}</name>
    <description>Trajet de la mission du {date_debut} au {date_fin}</description>
    
    <Style id="missionPath">
        <LineStyle>
            <color>ff0000ff</color>
            <width>3</width>
        </LineStyle>
    </Style>
    
    <Style id="startPoint">
        <IconStyle>
            <color>ff00ff00</color>
            <Icon>
                <href>http://maps.google.com/mapfiles/kml/shapes/arrow.png</href>
            </Icon>
        </IconStyle>
    </Style>
    
    <Style id="endPoint">
        <IconStyle>
            <color>ff0000ff</color>
            <Icon>
                <href>http://maps.google.com/mapfiles/kml/shapes/flag.png</href>
            </Icon>
        </IconStyle>
    </Style>'''.format(
        mission_id=mission.id,
        objet=mission.objet[:50],
        date_debut=mission.dateDebut.strftime("%d/%m/%Y %H:%M"),
        date_fin=mission.dateFin.strftime("%d/%m/%Y %H:%M")
    )
    
    # Points de départ et d'arrivée
    points_markup = ""
    if trajet.points:
        start_point = trajet.points[0]
        end_point = trajet.points[-1]
        
        points_markup = f'''
    <Placemark>
        <name>Départ</name>
        <description>Début de la mission à {start_point.timestamp.strftime("%H:%M")}</description>
        <styleUrl>#startPoint</styleUrl>
        <Point>
            <coordinates>{start_point.longitude},{start_point.latitude},0</coordinates>
        </Point>
    </Placemark>
    
    <Placemark>
        <name>Arrivée</name>
        <description>Fin de la mission à {end_point.timestamp.strftime("%H:%M")}</description>
        <styleUrl>#endPoint</styleUrl>
        <Point>
            <coordinates>{end_point.longitude},{end_point.latitude},0</coordinates>
        </Point>
    </Placemark>'''
    
    # Trajet complet
    coordinates = " ".join([
        f"{point.longitude},{point.latitude},0"
        for point in trajet.points
    ])
    
    path_markup = f'''
    <Placemark>
        <name>Trajet complet</name>
        <description>
            Distance totale: {trajet.distance_totale} km
            Durée: {trajet.duree_totale} minutes
            Vitesse moyenne: {trajet.vitesse_moyenne} km/h
        </description>
        <styleUrl>#missionPath</styleUrl>
        <LineString>
            <tessellate>1</tessellate>
            <coordinates>
                {coordinates}
            </coordinates>
        </LineString>
    </Placemark>'''
    
    kml_footer = '''
</Document>
</kml>'''
    
    return kml_header + points_markup + path_markup + kml_footer