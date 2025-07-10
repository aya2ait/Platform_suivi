import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, Spinner } from 'react-bootstrap';
import { MissionStatus } from '../../constants'; // Ensure path is correct
import ApiService from '../../api/apiService';

// --- IMPORTANT: Define your backend API base URL here ---
//const API_BASE_URL = "http://localhost:8000";

const GEOCODING_API_BASE_URL = "https://atlas.microsoft.com";
const AZURE_MAPS_API_KEY = "2awYgCjtEMly2f94tKyNqLZdu8WLgYnZmrgJdfK64uqwLdYQO1pxJQQJ99BFACYeBjFbQNAvAAAgAZMP35dr";

// --- NOUVEAU: Hook de remplacement pour obtenir le rôle de l'utilisateur ---
// EN PRODUCTION, VOUS DEVEZ REMPLACER CELA PAR VOTRE PROPRE LOGIQUE
// (par exemple, un contexte d'authentification qui stocke le rôle de l'utilisateur).
const useUserRole = () => {
    // Ceci est un exemple. En réalité, vous obtiendriez le rôle depuis votre état global d'authentification.
    // Par exemple, depuis un contexte React (AuthContext) ou Redux/Zustand.
    // Pour les tests, vous pouvez le changer manuellement: "directeur" ou "administrateur"
    const [role, setRole] = useState(null); // 'directeur' | 'administrateur' | null

    useEffect(() => {
        // Simule un appel API ou une récupération depuis le stockage local/contexte
        const fetchUserRole = async () => {
            // Exemple: Récupérer le rôle depuis localStorage ou une API
            const storedUser = localStorage.getItem('currentUser'); // Supposons que vous stockiez l'utilisateur ici
            if (storedUser) {
                const user = JSON.parse(storedUser);
                setRole(user.role); // Assurez-vous que l'objet utilisateur a une propriété 'role'
            } else {
                // Pour le développement/test, définissez un rôle par défaut si aucun utilisateur n'est trouvé
                // Ou laissez-le null si l'utilisateur doit se connecter d'abord
                setRole('directeur'); // Exemple par défaut pour le développement
            }
        };
        fetchUserRole();
    }, []);

    return role;
};
// --- FIN NOUVEAU HOOK ---


const MissionForm = ({ mission, onSubmit, onCancel }) => {
    const userRole = useUserRole(); // Récupérer le rôle de l'utilisateur
    
    const parseTrajetPoints = (trajetJsonStr) => {
        try {
            if (trajetJsonStr && typeof trajetJsonStr === 'string') {
                const parsed = JSON.parse(trajetJsonStr);
                return parsed.filter(point =>
                    typeof point === 'object' && point !== null &&
                    typeof point.latitude === 'number' && typeof point.longitude === 'number'
                ).map(point => ({
                    cityName: point.cityName || '',
                    latitude: point.latitude,
                    longitude: point.longitude,
                }));
            }
        } catch (e) {
            console.error("Erreur de parsing JSON pour trajet_predefini des points:", e);
        }
        return [];
    };

    const [formData, setFormData] = useState({
        objet: mission?.objet || '',
        dateDebut: mission?.dateDebut ? new Date(mission.dateDebut.replace('T00:00:00.000Z', '')).toLocaleDateString('en-CA') : '',
        dateFin: mission?.dateFin ? new Date(mission.dateFin.replace('T00:00:00.000Z', '')).toLocaleDateString('en-CA') : '',
        moyenTransport: mission?.moyenTransport || '',
        statut: mission?.statut || MissionStatus.CREEE,
        vehicule_id: mission?.vehicule_id || '',
        // --- MODIFICATION ICI: directeur_id géré différemment ---
        // directeur_id sera inclus seulement si l'utilisateur est administrateur et si une valeur est fournie
        // Lors de la modification, si la mission a un directeur_id, on l'initialise.
        directeur_id: mission?.directeur_id || '', 
        // --- FIN MODIFICATION ---
        trajet_predefini: parseTrajetPoints(mission?.trajet_predefini).length > 0
            ? parseTrajetPoints(mission?.trajet_predefini)
            : [{ cityName: '', latitude: null, longitude: null }]
    });

    const [validated, setValidated] = useState(false);
    const [loadingGeocode, setLoadingGeocode] = useState({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [availableVehicles, setAvailableVehicles] = useState([]); 
    const [dateError, setDateError] = useState(''); 

    // Fetch vehicles on component mount
    useEffect(() => {
        const fetchVehicles = async () => {
           try {
             const data = await ApiService.request('/missions/vehicules');
             setAvailableVehicles(data);
           } catch (error) {
              console.error("Error fetching vehicles:", error);
           }
        };
        fetchVehicles();
    }, []);

    // Reset form data when mission prop changes
    useEffect(() => {
        setFormData({
            objet: mission?.objet || '',
            dateDebut: mission?.dateDebut ? new Date(mission.dateDebut.replace('T00:00:00.000Z', '')).toLocaleDateString('en-CA') : '',
            dateFin: mission?.dateFin ? new Date(mission.dateFin.replace('T00:00:00.000Z', '')).toLocaleDateString('en-CA') : '',
            moyenTransport: mission?.moyenTransport || '',
            statut: mission?.statut || MissionStatus.CREEE,
            vehicule_id: mission?.vehicule_id || '',
            // --- MODIFICATION ICI (bis) pour le reset du formulaire ---
            directeur_id: mission?.directeur_id || '', 
            // --- FIN MODIFICATION ---
            trajet_predefini: parseTrajetPoints(mission?.trajet_predefini).length > 0
                ? parseTrajetPoints(mission?.trajet_predefini)
                : [{ cityName: '', latitude: null, longitude: null }]
        });
        setValidated(false);
        setLoadingGeocode({});
        setIsSubmitting(false);
        setDateError(''); 
    }, [mission]);

    // Fonction pour valider les dates - MODIFIÉE pour distinguer création/modification
    const validateDates = (dateDebut, dateFin, isEditing = false) => {
        if (!dateDebut || !dateFin) {
            return '';
        }
        
        const debut = new Date(dateDebut);
        const fin = new Date(dateFin);
        const aujourd = new Date();
        aujourd.setHours(0, 0, 0, 0); 
        
        if (!isEditing && debut < aujourd) {
            return 'La date de début ne peut pas être antérieure à aujourd\'hui.';
        }
        
        if (fin < debut) {
            return 'La date de fin ne peut pas être antérieure à la date de début.';
        }
        
        return '';
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => {
            const newData = { ...prev, [name]: value };
            
            if (name === 'dateDebut' || name === 'dateFin') {
                const error = validateDates(
                    name === 'dateDebut' ? value : newData.dateDebut,
                    name === 'dateFin' ? value : newData.dateFin,
                    !!mission?.id 
                );
                setDateError(error);
            }
            
            return newData;
        });
    };

    const handleCityNameChange = (index, value) => {
        const newTrajet = [...formData.trajet_predefini];
        newTrajet[index] = { ...newTrajet[index], cityName: value };
        setFormData(prev => ({ ...prev, trajet_predefini: newTrajet }));
    };

    const addTrajetPoint = () => {
        setFormData(prev => ({
            ...prev,
            trajet_predefini: [...prev.trajet_predefini, { cityName: '', latitude: null, longitude: null }]
        }));
    };

    const removeTrajetPoint = (index) => {
        const newTrajet = formData.trajet_predefini.filter((_, i) => i !== index);
        setFormData(prev => ({ ...prev, trajet_predefini: newTrajet }));
    };

    const geocodeAddress = async (index, address) => {
        if (!address || address.trim() === '') {
            alert("Veuillez entrer un nom de ville ou une adresse.");
            return;
        }

        setLoadingGeocode(prev => ({ ...prev, [index]: true }));

        try {
            const url = `${GEOCODING_API_BASE_URL}/search/address/json?subscription-key=${AZURE_MAPS_API_KEY}&api-version=1.0&query=${encodeURIComponent(address)}`;

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status} - ${response.statusText}`);
            }
            const data = await response.json();

            if (data && data.results && data.results.length > 0) {
                const firstResult = data.results[0].position;
                const newTrajet = [...formData.trajet_predefini];
                newTrajet[index] = {
                    ...newTrajet[index],
                    latitude: firstResult.lat,
                    longitude: firstResult.lon,
                };
                setFormData(prev => ({ ...prev, trajet_predefini: newTrajet }));
            } else {
                alert(`Aucune coordonnée trouvée pour "${address}". Veuillez être plus précis.`);
                const newTrajet = [...formData.trajet_predefini];
                newTrajet[index] = {
                    ...newTrajet[index],
                    latitude: null,
                    longitude: null,
                };
                setFormData(prev => ({ ...prev, trajet_predefini: newTrajet }));
            }
        } catch (error) {
            console.error("Erreur lors du géocodage:", error);
            alert(`Échec du géocodage pour "${address}". Vérifiez la console pour plus de détails.`);
            const newTrajet = [...formData.trajet_predefini];
            newTrajet[index] = {
                ...newTrajet[index],
                latitude: null,
                longitude: null,
            };
            setFormData(prev => ({ ...prev, trajet_predefini: newTrajet }));
        } finally {
            setLoadingGeocode(prev => ({ ...prev, [index]: false }));
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        const form = e.currentTarget;

        const currentDateError = validateDates(
            formData.dateDebut, 
            formData.dateFin, 
            !!mission?.id 
        );
        if (currentDateError) {
            setDateError(currentDateError);
            setValidated(true);
            e.stopPropagation();
            return;
        }

        const hasInvalidCoordinates = formData.trajet_predefini.some(point =>
            point.cityName.trim() !== '' && (
                point.latitude === null ||
                point.longitude === null ||
                isNaN(point.latitude) ||
                isNaN(point.longitude)
            )
        );

        if (hasInvalidCoordinates) {
            alert("Veuillez géocoder toutes les étapes du trajet ou laisser les champs de ville vides si non nécessaires.");
            setValidated(true);
            e.stopPropagation();
            return;
        }

        if (form.checkValidity() === false) {
            e.stopPropagation();
            setValidated(true);
            return;
        }

        setIsSubmitting(true);

        try {
            const pointsToSend = formData.trajet_predefini
                .filter(point =>
                    point.latitude !== null &&
                    point.longitude !== null &&
                    !isNaN(point.latitude) &&
                    !isNaN(point.longitude)
                )
                .map(point => ({
                    latitude: point.latitude,
                    longitude: point.longitude,
                }));

            // --- MODIFICATION: Préparer les données à envoyer en fonction du rôle ---
            let missionDataToSend = {
                objet: formData.objet,
                dateDebut: new Date(formData.dateDebut).toISOString(),
                dateFin: new Date(formData.dateFin).toISOString(),
                moyenTransport: formData.moyenTransport || null,
                statut: formData.statut,
                vehicule_id: formData.vehicule_id ? parseInt(formData.vehicule_id, 10) : null,
                trajet_predefini: pointsToSend.length > 0 ? pointsToSend : null,
            };

            // Ajouter directeur_id seulement si l'utilisateur est administrateur
            if (userRole === "administrateur") {
                if (formData.directeur_id) { // S'assurer qu'un ID est effectivement fourni
                    missionDataToSend.directeur_id = parseInt(formData.directeur_id, 10);
                } else {
                    // Pour un admin, si c'est une création et qu'aucun directeur_id n'est fourni, c'est une erreur.
                    // Pour une mise à jour, si c'est vide, cela pourrait signifier 'retirer le directeur' si votre backend le supporte.
                    // Ici, je suppose qu'un admin doit toujours en fournir un pour la création.
                    if (!mission?.id) { // Si c'est une création
                        throw new Error("L'ID du directeur est requis pour les administrateurs lors de la création.");
                    }
                     // Pour la mise à jour, si l'admin vide le champ, on envoie null ou l'ID actuel.
                     // On enverra null si le champ est vide et n'est pas requis par la backend
                     // Sinon, il ne faut pas l'inclure dans le payload pour ne pas le modifier implicitement
                }
            } else if (userRole === "directeur") {
                // Pour un directeur, le backend récupère l'ID du directeur connecté.
                // Donc, on ne l'inclut PAS dans le payload.
                // Si `formData.directeur_id` était initialisé pour l'affichage, il ne faut pas l'envoyer.
                // (Pas besoin de `delete missionDataToSend.directeur_id` car on construit le payload explicitement.)
            }
            // --- FIN MODIFICATION ---


            let responseData = null;

            if (mission?.id) {
                // MODIFICATION
                console.log("Données de mission à mettre à jour:", missionDataToSend);
                responseData = await ApiService.updateMission(mission.id, missionDataToSend);
                console.log("Mission mise à jour avec succès:", responseData);
            } else {
                // CRÉATION
                console.log("Données de mission à créer:", missionDataToSend);
                responseData = await ApiService.createMission(missionDataToSend);
                console.log("Mission créée avec succès:", responseData);
            }

            onSubmit(responseData);

        } catch (error) {
            console.error("Erreur lors de la soumission de la mission:", error);
            alert(`Erreur lors de la soumission de la mission: ${error.message || "Échec de la création/mise à jour de la mission."}`);
        } finally {
            setIsSubmitting(false);
        }
    };


    return (
        <Modal show={true} onHide={onCancel} centered size="lg">
            <Modal.Header closeButton>
                <Modal.Title className="h5 fw-semibold text-dark">
                    {mission ? 'Modifier la Mission' : 'Nouvelle Mission'}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="p-4" style={{ maxHeight: '80vh', overflowY: 'auto' }}>
                <Form noValidate validated={validated} onSubmit={handleSubmit}>
                    {/* Mission Object */}
                    <Form.Group className="mb-3" controlId="formObjet">
                        <Form.Label className="form-label text-dark">Objet de la mission *</Form.Label>
                        <Form.Control
                            as="textarea"
                            name="objet"
                            value={formData.objet}
                            onChange={handleChange}
                            required
                            rows={3}
                            placeholder="Décrivez l'objet de la mission..."
                        />
                        <Form.Control.Feedback type="invalid">
                            Veuillez fournir un objet pour la mission.
                        </Form.Control.Feedback>
                    </Form.Group>

                    {/* Dates */}
                    <Row className="mb-3 g-3">
                        <Form.Group as={Col} controlId="formDateDebut">
                            <Form.Label className="form-label text-dark">Date de début *</Form.Label>
                            <Form.Control
                                type="date"
                                name="dateDebut"
                                value={formData.dateDebut}
                                onChange={handleChange}
                                required
                                isInvalid={dateError !== ''}
                            />
                            <Form.Control.Feedback type="invalid">
                                {dateError || 'Veuillez sélectionner une date de début.'}
                            </Form.Control.Feedback>
                        </Form.Group>
                        <Form.Group as={Col} controlId="formDateFin">
                            <Form.Label className="form-label text-dark">Date de fin *</Form.Label>
                            <Form.Control
                                type="date"
                                name="dateFin"
                                value={formData.dateFin}
                                onChange={handleChange}
                                required
                                isInvalid={dateError !== ''}
                            />
                            <Form.Control.Feedback type="invalid">
                                {dateError || 'Veuillez sélectionner une date de fin.'}
                            </Form.Control.Feedback>
                        </Form.Group>
                    </Row>
                    
                    {/* Affichage de l'erreur de date si présente */}
                    {dateError && (
                        <div className="alert alert-danger mb-3" role="alert">
                            {dateError}
                        </div>
                    )}

                    {/* Transport Type */}
                    <Form.Group className="mb-3" controlId="formMoyenTransport">
                        <Form.Label className="form-label text-dark">Moyen de transport</Form.Label>
                        <Form.Select
                            name="moyenTransport"
                            value={formData.moyenTransport}
                            onChange={handleChange}
                        >
                            <option value="">Sélectionner...</option>
                            <option value="Voiture de service">Voiture de service</option>
                            <option value="Transport en commun">Transport en commun</option>
                            <option value="Avion">Avion</option>
                            <option value="Train">Train</option>
                        </Form.Select>
                    </Form.Group>

                    {/* Trajet prédéfini */}
                    <Form.Group className="mb-3" controlId="formTrajetPredefiniGeocode">
                        <Form.Label className="form-label text-dark">Trajet prédéfini (saisissez les villes)</Form.Label>
                        {formData.trajet_predefini.map((point, idx) => (
                            <Row key={idx} className="mb-2 align-items-center g-2">
                                <Col xs={12} md={6}>
                                    <Form.Control
                                        type="text"
                                        value={point.cityName}
                                        onChange={(e) => handleCityNameChange(idx, e.target.value)}
                                        placeholder={`Étape ${idx + 1} (Ex: Tanger, Paris)`}
                                    />
                                    {point.latitude !== null && point.longitude !== null && (
                                        <Form.Text className="text-success small">
                                            Lat: {point.latitude?.toFixed(5)}, Lon: {point.longitude?.toFixed(5)}
                                        </Form.Text>
                                    )}
                                    {point.cityName.trim() !== '' && (point.latitude === null || point.longitude === null) && validated && (
                                        <Form.Control.Feedback type="invalid" className="d-block">
                                            Veuillez géocoder cette étape.
                                        </Form.Control.Feedback>
                                    )}
                                </Col>
                                <Col xs="auto">
                                    <Button
                                        variant="info"
                                        onClick={() => geocodeAddress(idx, point.cityName)}
                                        disabled={loadingGeocode[idx] || point.cityName.trim() === ''}
                                    >
                                        {loadingGeocode[idx] ?
                                            <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> :
                                            'Géocoder'
                                        }
                                    </Button>
                                </Col>
                                <Col xs="auto">
                                    <Button variant="danger" onClick={() => removeTrajetPoint(idx)}>
                                        Supprimer
                                    </Button>
                                </Col>
                            </Row>
                        ))}
                        <Button variant="secondary" onClick={addTrajetPoint}>
                            Ajouter une étape
                        </Button>
                    </Form.Group>

                    {/* Director ID and Vehicle ID */}
                    <Row className="mb-3 g-3">
                        {/* --- MODIFICATION: Affichage conditionnel du champ directeur_id --- */}
                        {userRole === "administrateur" && (
                            <Form.Group as={Col} controlId="formDirecteurId">
                                <Form.Label className="form-label text-dark">ID Directeur *</Form.Label>
                                <Form.Control
                                    type="number"
                                    name="directeur_id"
                                    value={formData.directeur_id}
                                    onChange={handleChange}
                                    required={userRole === "administrateur" && !mission?.id} // Requis seulement pour les admins en création
                                    placeholder="ID du directeur"
                                />
                                <Form.Control.Feedback type="invalid">
                                    Veuillez fournir l'ID du directeur.
                                </Form.Control.Feedback>
                            </Form.Group>
                        )}
                        {/* --- FIN MODIFICATION --- */}

                        <Form.Group as={Col} controlId="formVehiculeId">
                            <Form.Label className="form-label text-dark">Véhicule</Form.Label>
                            <Form.Select
                                name="vehicule_id"
                                value={formData.vehicule_id}
                                onChange={handleChange}
                            >
                                <option value="">Sélectionner un véhicule (Optionnel)</option>
                                {availableVehicles.map(vehicle => (
                                    <option key={vehicle.id} value={vehicle.id}>{vehicle.modele} ({vehicle.immatriculation})</option>
                                ))}
                            </Form.Select>
                        </Form.Group>
                    </Row>

                    {/* Status */}
                    <Form.Group className="mb-4" controlId="formStatut">
                        <Form.Label className="form-label text-dark">Statut</Form.Label>
                        <Form.Select
                            name="statut"
                            value={formData.statut}
                            onChange={handleChange}
                        >
                            {Object.values(MissionStatus).map(status => (
                                <option key={status} value={status}>{status.replace('_', ' ')}</option>
                            ))}
                        </Form.Select>
                    </Form.Group>

                    {/* Action Buttons */}
                    <div className="d-flex gap-3">
                        <Button 
                            variant="primary" 
                            type="submit" 
                            className="flex-fill" 
                            disabled={isSubmitting || dateError !== '' || userRole === null}
                        >
                            {isSubmitting ? <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> : (mission ? 'Modifier' : 'Créer')}
                        </Button>
                        <Button variant="secondary" type="button" onClick={onCancel} className="flex-fill" disabled={isSubmitting}>
                            Annuler
                        </Button>
                    </div>
                </Form>
            </Modal.Body>
        </Modal>
    );
};

export default MissionForm;