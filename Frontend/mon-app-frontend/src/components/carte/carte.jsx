import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapPin, Car, AlertTriangle, Navigation, Zap, Users, RefreshCw, Calendar, Clock } from 'lucide-react';
import { useAuth, axiosInstance } from '../../contexts/AuthContext'; // Importez useAuth et axiosInstance

const MoroccoInteractiveMap = () => {
    const mapRef = useRef(null);
    const leafletMapRef = useRef(null);
    const markersRef = useRef({});
    const polylinesRef = useRef({}); // Nouveau : pour stocker les objets polyline Leaflet
    const intervalRef = useRef(null); // Nouveau : pour le polling en temps réel

    const [selectedMission, setSelectedMission] = useState(null);
    const [isMapLoaded, setIsMapLoaded] = useState(false);
    const [missions, setMissions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);

    // --- Utilisation de useAuth pour l'authentification ---
    const { isAuthenticated, user, loading: authLoading, authReady, hasPermission } = useAuth();

    // Principales villes du Maroc avec leurs coordonnées
    const moroccanCities = [
        { name: "Rabat", lat: 33.9716, lng: -6.8498 },
        { name: "Casablanca", lat: 33.5731, lng: -7.5898 },
        { name: "Marrakech", lat: 31.6295, lng: -7.9811 },
        { name: "Fès", lat: 34.0181, lng: -5.0078 },
        { name: "Tanger", lat: 35.7595, lng: -5.8340 },
        { name: "Agadir", lat: 30.4278, lng: -9.5981 },
        { name: "Meknès", lat: 33.8935, lng: -5.5473 },
        { name: "Oujda", lat: 34.6814, lng: -1.9086 },
        { name: "Tétouan", lat: 35.5889, lng: -5.3626 },
        { name: "Safi", lat: 32.2994, lng: -9.2372 }
    ];

    // Fonction pour récupérer les missions depuis le backend
    // Utilisation de useCallback pour stabiliser la fonction, évitant des re-créations inutiles
    const fetchMissions = useCallback(async () => {
        // Ne pas tenter de récupérer si l'authentification n'est pas prête ou si l'utilisateur n'est pas authentifié
        // Ou si l'utilisateur n'a pas la permission 'carte:read'
        if (!authReady || !isAuthenticated || !hasPermission('carte:read')) {
            setLoading(false);
            if (!isAuthenticated) {
                setError("Authentification requise pour charger les missions.");
            } else if (!hasPermission('carte:read')) {
                setError("Vous n'avez pas la permission d'accéder à la carte des missions.");
            }
            return;
        }

        setLoading(true);
        try {
            // Utilisation de axiosInstance au lieu de fetch
            const response = await axiosInstance.get('/api/map/missions');

            // --- IMPORTANT: PARSE trajet_predefini FOR EACH MISSION ---
            const processedMissions = response.data.missions.map(mission => {
                let parsedTrajetPredefini = [];
                if (mission.trajet_predefini && typeof mission.trajet_predefini === 'string') {
                    try {
                        parsedTrajetPredefini = JSON.parse(mission.trajet_predefini);
                        // Ensure it's an array after parsing, or default to empty
                        if (!Array.isArray(parsedTrajetPredefini)) {
                            console.warn(`Parsed trajet_predefini for mission ${mission.id} is not an array. Resetting to empty.`, parsedTrajetPredefini);
                            parsedTrajetPredefini = [];
                        }
                    } catch (e) {
                        console.error(`Error parsing trajet_predefini for mission ${mission.id}:`, e);
                        parsedTrajetPredefini = []; // Reset to empty array on parsing error
                    }
                }
                // Return the mission object with the parsed (or empty) array
                return { ...mission, trajet_predefini: parsedTrajetPredefini };
            });
            // --- END IMPORTANT MODIFICATION ---

            setMissions(processedMissions || []); // Use processedMissions
            setLastUpdate(new Date());
            setError(null);
        } catch (err) {
            console.error('Erreur lors de la récupération des missions:', err);
            // Axios place l'objet de réponse dans error.response
            if (err.response && err.response.status === 403) {
                setError("Accès refusé : Vous n'avez pas la permission de voir les missions.");
            } else {
                setError(err.message);
            }
        } finally {
            setLoading(false);
        }
    }, [authReady, isAuthenticated, hasPermission]); // Dépendances de useCallback

    // Fonction pour déterminer la couleur selon le statut
    const getStatusColor = (statut) => {
        switch (statut) {
            case 'EN_COURS':
                return '#10b981'; // Vert
            case 'TERMINEE':
                return '#6b7280'; // Gris
            case 'CREEE':
                return '#f59e0b'; // Orange
            case 'ANNULEE':
                return '#ef4444'; // Rouge
            case 'SUSPENDUE':
                return '#8b5cf6'; // Violet
            default:
                return '#6b7280'; // Gris par défaut
        }
    };

    // Fonction pour obtenir le texte du statut
    const getStatusText = (statut) => {
        switch (statut) {
            case 'EN_COURS':
                return 'En cours';
            case 'TERMINEE':
                return 'Terminée';
            case 'CREEE':
                return 'Créée';
            case 'ANNULEE':
                return 'Annulée';
            case 'SUSPENDUE':
                return 'Suspendue';
            default:
                return statut;
        }
    };

    // Fonction pour déterminer si une mission a des anomalies
    const hasAnomalies = (mission) => {
        return mission.anomalies && mission.anomalies.length > 0;
    };

    // MODIFIÉ : Fonction pour obtenir la position d'une mission selon son statut
    const getMissionPosition = (mission) => {
        const { statut } = mission;
        let lat, lng;

        // Helper function to safely parse and assign coordinates
        const parseCoordinates = (point) => {
            if (point && typeof point.latitude === 'number' && typeof point.longitude === 'number') {
                // Coordinates are already numbers if successfully JSON.parsed
                return { lat: point.latitude, lng: point.longitude };
            }
            // Fallback for string coordinates (though should be handled by JSON.parse)
            if (point && typeof point.latitude === 'string' && typeof point.longitude === 'string') {
                const parsedLat = parseFloat(point.latitude);
                const parsedLng = parseFloat(point.longitude);
                if (!isNaN(parsedLat) && !isNaN(parsedLng)) {
                    return { lat: parsedLat, lng: parsedLng };
                }
            }
            return null;
        };

        if (statut === 'CREEE') {
            // Pour les missions créées : utiliser le PREMIER point du trajet prédéfini
            if (mission.trajet_predefini && mission.trajet_predefini.length > 0) {
                const position = parseCoordinates(mission.trajet_predefini[0]);
                if (position) return position;
            }
            // Si pas de trajet prédéfini valide, utiliser le PREMIER point du trajet_points
            if (mission.trajet_points && mission.trajet_points.length > 0) {
                const position = parseCoordinates(mission.trajet_points[0]);
                if (position) return position;
            }
        } else if (statut === 'EN_COURS') {
            // Pour les missions en cours : utiliser le DERNIER point du trajet_points (position actuelle)
            if (mission.trajet_points && mission.trajet_points.length > 0) {
                const position = parseCoordinates(mission.trajet_points[mission.trajet_points.length - 1]);
                if (position) return position;
            }
        } else {
            // Pour les autres statuts (TERMINEE, ANNULEE, SUSPENDUE) : utiliser le dernier point du trajet_points
            if (mission.trajet_points && mission.trajet_points.length > 0) {
                const position = parseCoordinates(mission.trajet_points[mission.trajet_points.length - 1]);
                if (position) return position;
            }
        }

        // Position par défaut si aucune position valide n'a pu être trouvée
        console.warn(`Mission ${mission.id} (${mission.objet}) had invalid or missing coordinates. Using default position.`);
        return { lat: 31.7917, lng: -7.0926 }; // Centre du Maroc
    };

    // Initialisation de Leaflet
    useEffect(() => {
        const loadLeaflet = async () => {
            // S'assurer que l'authentification est prête avant de charger la carte
            if (!authReady) return;

            if (!document.querySelector('link[href*="leaflet"]')) {
                const leafletCSS = document.createElement('link');
                leafletCSS.rel = 'stylesheet';
                leafletCSS.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';
                document.head.appendChild(leafletCSS);
            }

            if (!window.L) {
                const leafletJS = document.createElement('script');
                leafletJS.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js';
                leafletJS.onload = initializeMap;
                document.head.appendChild(leafletJS);
            } else {
                initializeMap();
            }
        };

        const initializeMap = () => {
            if (leafletMapRef.current || !mapRef.current) return;

            const map = window.L.map(mapRef.current, {
                zoomControl: true,
                scrollWheelZoom: true,
                doubleClickZoom: true,
                boxZoom: true,
                keyboard: true
            }).setView([31.7917, -7.0926], 6);

            window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 18,
                minZoom: 5
            }).addTo(map);

            // Ajout des marqueurs des villes
            moroccanCities.forEach(city => {
                const cityIcon = window.L.divIcon({
                    className: 'city-marker',
                    html: `<div style="background-color: #1f2937; color: white; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">${city.name}</div>`,
                    iconSize: [60, 20],
                    iconAnchor: [30, 10]
                });

                window.L.marker([city.lat, city.lng], { icon: cityIcon }).addTo(map);
            });

            leafletMapRef.current = map;
            setIsMapLoaded(true);
        };

        loadLeaflet();

        return () => {
            if (leafletMapRef.current) {
                leafletMapRef.current.remove();
                leafletMapRef.current = null;
            }
            // Nettoyage de l'animation CSS si elle a été ajoutée
            const styleElement = document.querySelector('#pulse-animation');
            if (styleElement) {
                styleElement.remove();
            }
        };
    }, [authReady]); // Déclenchez l'initialisation de la carte lorsque authReady change

    // --- Gestion du chargement initial des missions et du polling en temps réel ---
    useEffect(() => {
        // Cet effet gère le chargement initial des missions et la mise en place du polling.

        if (authReady && isAuthenticated && hasPermission('carte:read')) {
            // S'assurer qu'aucun intervalle précédent ne tourne
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }

            // Charger les missions immédiatement
            fetchMissions();

            // Mettre en place le polling toutes les 10 secondes
            intervalRef.current = setInterval(() => {
                fetchMissions();
            }, 10000); // 10 secondes
        } else {
            // Si pas authentifié ou pas la permission, arrêter le polling et mettre les messages d'erreur
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
            if (authReady && !isAuthenticated) {
                setLoading(false);
                setError("Veuillez vous connecter pour voir la carte des missions.");
            } else if (authReady && !hasPermission('carte:read')) {
                setLoading(false);
                setError("Vous n'avez pas la permission d'accéder à la carte des missions.");
            }
        }

        // Fonction de nettoyage pour arrêter le polling quand le composant est démonté
        // ou que les dépendances (authReady, isAuthenticated, hasPermission) changent
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
        };
    }, [authReady, isAuthenticated, hasPermission, fetchMissions]); // fetchMissions est une dépendance car c'est une fonction useCallback

    // MODIFIÉ : Mise à jour des marqueurs et tracés des missions
    useEffect(() => {
        // N'afficher les marqueurs et tracés que si la carte est chargée, l'utilisateur est authentifié et a la permission
        if (!isMapLoaded || !leafletMapRef.current || !isAuthenticated || !hasPermission('carte:read')) return;

        // Supprimer les anciens marqueurs
        Object.values(markersRef.current).forEach(marker => {
            leafletMapRef.current.removeLayer(marker);
        });
        markersRef.current = {};

        // Supprimer les anciennes polylines
        Object.values(polylinesRef.current).forEach(polyline => {
            leafletMapRef.current.removeLayer(polyline);
        });
        polylinesRef.current = {};

        // Ajouter les nouveaux marqueurs et trajets
        missions.forEach(mission => {
            const { statut } = mission;
            const hasAnomaliesFlag = hasAnomalies(mission);
            const position = getMissionPosition(mission); // Position selon le statut

            // It's crucial to check if position is valid BEFORE creating the marker
            if (isNaN(position.lat) || isNaN(position.lng)) {
                console.error(`Skipping mission ${mission.id} due to invalid coordinates: (${position.lat}, ${position.lng})`);
                return; // Skip this mission if coordinates are invalid
            }

            let color = getStatusColor(statut);
            let pulseColor = color.replace(')', ', 0.5)').replace('rgb', 'rgba');

            if (hasAnomaliesFlag) {
                color = '#ef4444'; // Rouge pour anomalies, prime sur le statut
                pulseColor = 'rgba(239, 68, 68, 0.5)';
            }

            const missionIcon = window.L.divIcon({
                className: 'mission-marker',
                html: `
                    <div style="position: relative;">
                        ${statut === 'EN_COURS' ? `
                            <div style="
                                position: absolute;
                                top: -5px;
                                left: -5px;
                                width: 30px;
                                height: 30px;
                                background-color: ${pulseColor};
                                border-radius: 50%;
                                animation: pulse 2s infinite;
                            "></div>
                        ` : ''}
                        <div style="
                            position: relative;
                            width: 20px;
                            height: 20px;
                            background-color: ${color};
                            border: 2px solid white;
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                            z-index: 10;
                        ">
                            <div style="
                                width: 8px;
                                height: 8px;
                                background-color: white;
                                border-radius: 50%;
                            "></div>
                        </div>
                        ${hasAnomaliesFlag ? `
                            <div style="
                                position: absolute;
                                top: -4px;
                                right: -4px;
                                width: 12px;
                                height: 12px;
                                background-color: #ef4444;
                                border: 1px solid white;
                                border-radius: 50%;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                z-index: 11;
                            ">
                                <div style="
                                    width: 0;
                                    height: 0;
                                    border-left: 2px solid transparent;
                                    border-right: 2px solid transparent;
                                    border-bottom: 3px solid white;
                                    margin-bottom: 1px;
                                "></div>
                            </div>
                        ` : ''}
                    </div>
                `,
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });

            const marker = window.L.marker([position.lat, position.lng], {
                icon: missionIcon
            }).addTo(leafletMapRef.current);

            // Popup avec informations de la mission (inchangé)
            const popupContent = `
                <div style="min-width: 200px; font-family: system-ui, sans-serif;">
                    <div style="border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-bottom: 8px;">
                        <h3 style="margin: 0; font-size: 14px; font-weight: 600; color: #1f2937;">
                            Mission #${mission.id}
                        </h3>
                        <p style="margin: 2px 0 0 0; font-size: 12px; color: #6b7280;">
                            ${mission.objet}
                        </p>
                    </div>

                    <div style="margin-bottom: 8px;">
                        <p style="margin: 0; font-size: 12px; color: #6b7280;">
                            <strong>Directeur:</strong> ${mission.directeur_prenom} ${mission.directeur_nom}
                        </p>
                        <p style="margin: 0; font-size: 12px; color: #6b7280;">
                            <strong>Direction:</strong> ${mission.direction_nom}
                        </p>
                    </div>

                    ${mission.vehicule_immatriculation ? `
                        <div style="margin-bottom: 8px;">
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">
                                <strong>Véhicule:</strong> ${mission.vehicule_immatriculation}<br>
                                ${mission.vehicule_marque} ${mission.vehicule_modele}
                            </p>
                        </div>
                    ` : ''}

                    ${mission.collaborateurs && mission.collaborateurs.length > 0 ? `
                        <div style="margin-bottom: 8px;">
                            <p style="margin: 0; font-size: 11px; color: #6b7280;">
                                <strong>Collaborateurs:</strong><br>
                                ${mission.collaborateurs.map(c => `${c.nom} (${c.matricule})`).join('<br>')}
                            </p>
                        </div>
                    ` : ''}

                    <div style="margin-bottom: 8px;">
                        <p style="margin: 0; font-size: 11px; color: #6b7280;">
                            <strong>Période:</strong><br>
                            ${new Date(mission.dateDebut).toLocaleDateString('fr-FR')} -
                            ${new Date(mission.dateFin).toLocaleDateString('fr-FR')}
                        </p>
                    </div>

                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <span style="
                            display: inline-block;
                            padding: 2px 8px;
                            border-radius: 12px;
                            font-size: 10px;
                            font-weight: 500;
                            color: white;
                            background-color: ${color};
                        ">
                            ${getStatusText(statut)}
                        </span>
                        ${mission.trajet_points && mission.trajet_points.length > 0 ? `
                            <span style="font-size: 10px; color: #6b7280;">
                                ${mission.trajet_points.length} points GPS
                            </span>
                        ` : ''}
                    </div>

                    ${hasAnomaliesFlag ? `
                        <div style="
                            margin-top: 8px;
                            padding: 6px;
                            background-color: #fef2f2;
                            border: 1px solid #fecaca;
                            border-radius: 4px;
                        ">
                            <p style="margin: 0; font-size: 11px; color: #dc2626;">
                                <strong>⚠️ Anomalies détectées:</strong><br>
                                ${mission.anomalies.length} anomalie(s)
                            </p>
                        </div>
                    ` : ''}
                </div>
            `;

            marker.bindPopup(popupContent, {
                maxWidth: 250,
                className: 'custom-popup'
            });

            marker.on('click', () => {
                setSelectedMission(mission);
            });

            markersRef.current[mission.id] = marker;

            // MODIFIÉ : Gestion des tracés selon le statut
          
            // MODIFIÉ : Désactiver le tracé pour les missions 'EN_COURS'
            // Les missions en cours n'affichent plus leur trajet parcouru
        });

        // Ajouter les styles CSS pour l'animation (inchangé)
        if (!document.querySelector('#pulse-animation')) {
            const style = document.createElement('style');
            style.id = 'pulse-animation';
            style.textContent = `
                @keyframes pulse {
                    0% {
                        transform: scale(0.8);
                        opacity: 1;
                    }
                    100% {
                        transform: scale(2);
                        opacity: 0;
                    }
                }
                .custom-popup .leaflet-popup-content-wrapper {
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                }
                .custom-popup .leaflet-popup-tip {
                    background: white;
                }
            `;
            document.head.appendChild(style);
        }

    }, [missions, isMapLoaded, isAuthenticated, hasPermission]); // Dépend de `missions` pour la mise à jour des marqueurs et tracés

    const centerOnMission = (mission) => {
        if (leafletMapRef.current) {
            const position = getMissionPosition(mission);
            // Only attempt to set view if coordinates are valid
            if (!isNaN(position.lat) && !isNaN(position.lng)) {
                leafletMapRef.current.setView([position.lat, position.lng], 12);
                markersRef.current[mission.id]?.openPopup();
            } else {
                console.warn(`Cannot center on mission ${mission.id}: invalid coordinates.`);
            }
        }
    };

    const refreshData = () => {
        fetchMissions();
    };

    // Statistiques
    const stats = {
        total: missions.length,
        enCours: missions.filter(m => m.statut === 'EN_COURS').length,
        terminees: missions.filter(m => m.statut === 'TERMINEE').length,
        creees: missions.filter(m => m.statut === 'CREEE').length,
        avecAnomalies: missions.filter(m => hasAnomalies(m)).length
    };

    // --- Gestion de l'état de chargement de l'authentification ---
    if (authLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-100">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p className="text-gray-700 text-lg">Chargement de l'authentification...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-100">
            {/* Header */}
            <div className="bg-blue-900 text-white p-4 shadow-lg">
                <div className="flex items-center justify-between max-w-7xl mx-auto">
                    <div className="flex items-center space-x-3">
                        <Zap className="h-8 w-8 text-yellow-400" />
                        <div>
                            <h1 className="text-2xl font-bold">ONEE - Suivi des Missions</h1>
                            <p className="text-blue-200 text-sm">Office National de l'Électricité et de l'Eau Potable</p>
                        </div>
                    </div>
                    <div className="flex items-center space-x-6 text-sm">
                        <div className="flex items-center space-x-2">
                            <Car className="h-4 w-4" />
                            <span>{stats.enCours} missions actives</span>
                        </div>
                        <div className="flex items-center space-x-2">
                            <AlertTriangle className="h-4 w-4 text-red-400" />
                            <span>{stats.avecAnomalies} anomalies</span>
                        </div>
                        <button
                            onClick={refreshData}
                            disabled={loading || !isAuthenticated || !hasPermission('carte:read')}
                            className="flex items-center space-x-2 bg-blue-800 hover:bg-blue-700 px-3 py-1 rounded-md transition-colors"
                        >
                            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                            <span>Actualiser</span>
                        </button>
                    </div>
                </div>
            </div>

            <div className="flex h-screen">
                {/* Sidebar - Liste des missions */}
                <div className="w-80 bg-white shadow-lg overflow-y-auto">
                    <div className="p-4 border-b bg-gray-50">
                        <h2 className="text-lg font-semibold text-gray-800 flex items-center">
                            <Navigation className="h-5 w-5 mr-2" />
                            Missions ({stats.total})
                        </h2>
                        {lastUpdate && (
                            <p className="text-xs text-gray-500 mt-1">
                                Dernière mise à jour: {lastUpdate.toLocaleTimeString('fr-FR')}
                            </p>
                        )}
                    </div>

                    {/* --- Affichage des messages d'erreur/chargement liés à l'authentification et permissions --- */}
                    {error && (
                        <div className="p-4 bg-red-50 border-l-4 border-red-500">
                            <div className="flex">
                                <AlertTriangle className="h-5 w-5 text-red-500" />
                                <div className="ml-3">
                                    <p className="text-sm text-red-700">
                                        Erreur de chargement: {error}
                                    </p>
                                    {(!isAuthenticated || !hasPermission('carte:read')) && (
                                        <p className="text-sm text-red-700 mt-1">
                                            Veuillez vous assurer que vous êtes connecté et que vous avez les permissions nécessaires.
                                        </p>
                                    )}
                                    <button
                                        onClick={refreshData}
                                        disabled={!isAuthenticated || !hasPermission('carte:read')}
                                        className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
                                    >
                                        Réessayer
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {loading && isAuthenticated && hasPermission('carte:read') ? (
                        <div className="p-4 text-center">
                            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2 text-blue-600" />
                            <p className="text-gray-600">Chargement des missions...</p>
                        </div>
                    ) : (!isAuthenticated || !hasPermission('carte:read')) ? (
                        <div className="p-4 text-center bg-yellow-50 border-l-4 border-yellow-500 text-yellow-700">
                            <p className="text-sm">
                                {!isAuthenticated ? "Vous devez être connecté pour voir la liste des missions." : "Vous n'avez pas la permission de voir la liste des missions."}
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-2 p-2">
                            {missions.map((mission) => (
                                <div
                                    key={mission.id}
                                    className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 ${
                                        selectedMission?.id === mission.id
                                            ? 'border-blue-500 bg-blue-50 shadow-md'
                                            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                    }`}
                                    onClick={() => centerOnMission(mission)}
                                >
                                    {/* Mission card content (remains unchanged) */}
                                    <h3 className="font-semibold text-gray-900 text-sm">{mission.objet}</h3>
                                    <p className="text-xs text-gray-600">
                                        Par {mission.directeur_prenom} {mission.directeur_nom}
                                    </p>
                                    {mission.vehicule_immatriculation && (
                                        <p className="text-xs text-gray-500 flex items-center mt-1">
                                            <Car className="h-3 w-3 mr-1" />
                                            {mission.vehicule_immatriculation}
                                        </p>
                                    )}
                                    <div className="flex items-center justify-between mt-2">
                                        <span
                                            style={{ backgroundColor: getStatusColor(mission.statut) }}
                                            className="px-2 py-0.5 rounded-full text-white text-xs font-medium"
                                        >
                                            {getStatusText(mission.statut)}
                                        </span>
                                        {hasAnomalies(mission) && (
                                            <span className="text-red-500 text-xs font-medium flex items-center">
                                                <AlertTriangle className="h-3 w-3 mr-1" />
                                                Anomalie(s)
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center text-gray-500 text-xs mt-1">
                                        <Calendar className="h-3 w-3 mr-1" />
                                        <span>
                                            {new Date(mission.dateDebut).toLocaleDateString('fr-FR')} -{' '}
                                            {new Date(mission.dateFin).toLocaleDateString('fr-FR')}
                                        </span>
                                    </div>
                                </div>
                            ))}
                            {missions.length === 0 && !loading && !error && (
                                <div className="p-4 text-center text-gray-500">
                                    Aucune mission trouvée.
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Main Content - Map */}
                <div className="flex-1">
                    <div
                        id="mapid"
                        ref={mapRef}
                        className="w-full h-full"
                        style={{ minHeight: '500px' }} // Ensure map has a minimum height
                    >
                        {!isMapLoaded && (
                            <div className="absolute inset-0 flex items-center justify-center bg-gray-200 bg-opacity-75 z-10">
                                <p className="text-gray-700 text-lg">Chargement de la carte...</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MoroccoInteractiveMap;