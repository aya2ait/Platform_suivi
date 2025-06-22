import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, Spinner } from 'react-bootstrap';
import { MissionStatus } from '../../constants'; // Ensure path is correct

// --- IMPORTANT: Define your backend API base URL here ---
const API_BASE_URL = "http://localhost:8000";

const GEOCODING_API_BASE_URL = "https://atlas.microsoft.com";
const AZURE_MAPS_API_KEY = "2awYgCjtEMly2f94tKyNqLZdu8WLgYnZmrgJdfK64uqwLdYQO1pxJQQJ99BFACYeBjFbQNAvAAAgAZMP35dr";

const MissionForm = ({ mission, onSubmit, onCancel }) => {

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
        dateDebut: mission?.dateDebut ? new Date(mission.dateDebut).toISOString().split('T')[0] : '',
        dateFin: mission?.dateFin ? new Date(mission.dateFin).toISOString().split('T')[0] : '',
        moyenTransport: mission?.moyenTransport || '',
        statut: mission?.statut || MissionStatus.CREEE,
        vehicule_id: mission?.vehicule_id || '',
        directeur_id: mission?.directeur_id || '',
        trajet_predefini: parseTrajetPoints(mission?.trajet_predefini).length > 0
            ? parseTrajetPoints(mission?.trajet_predefini)
            : [{ cityName: '', latitude: null, longitude: null }]
    });

    const [validated, setValidated] = useState(false);
    const [loadingGeocode, setLoadingGeocode] = useState({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [availableVehicles, setAvailableVehicles] = useState([]); // State to store fetched vehicles
    const [dateError, setDateError] = useState(''); // State pour gérer les erreurs de date

    // Fetch vehicles on component mount
    useEffect(() => {
        const fetchVehicles = async () => {
            try {
                // MODIFIED: Corrected endpoint path to include "/missions" prefix
                const response = await fetch(`${API_BASE_URL}/missions/vehicules`); 
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                setAvailableVehicles(data);
            } catch (error) {
                console.error("Error fetching vehicles:", error);
                // Optionally show an alert to the user
            }
        };
        fetchVehicles();
    }, []);

    // Reset form data when mission prop changes
    useEffect(() => {
        setFormData({
            objet: mission?.objet || '',
            dateDebut: mission?.dateDebut ? new Date(mission.dateDebut).toISOString().split('T')[0] : '',
            dateFin: mission?.dateFin ? new Date(mission.dateFin).toISOString().split('T')[0] : '',
            moyenTransport: mission?.moyenTransport || '',
            statut: mission?.statut || MissionStatus.CREEE,
            vehicule_id: mission?.vehicule_id || '',
            directeur_id: mission?.directeur_id || '',
            trajet_predefini: parseTrajetPoints(mission?.trajet_predefini).length > 0
                ? parseTrajetPoints(mission?.trajet_predefini)
                : [{ cityName: '', latitude: null, longitude: null }]
        });
        setValidated(false);
        setLoadingGeocode({});
        setIsSubmitting(false);
        setDateError(''); // Reset date error
    }, [mission]);

    // Fonction pour valider les dates
    const validateDates = (dateDebut, dateFin) => {
        if (!dateDebut || !dateFin) {
            return '';
        }
        
        const debut = new Date(dateDebut);
        const fin = new Date(dateFin);
        const aujourd = new Date();
        aujourd.setHours(0, 0, 0, 0); // Reset time to start of day
        
        // Vérifier si la date de début est antérieure à aujourd'hui
        if (debut < aujourd) {
            return 'La date de début ne peut pas être antérieure à aujourd\'hui.';
        }
        
        // Vérifier si la date de fin est antérieure à la date de début
        if (fin < debut) {
            return 'La date de fin ne peut pas être antérieure à la date de début.';
        }
        
        return '';
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => {
            const newData = { ...prev, [name]: value };
            
            // Valider les dates quand l'une d'elles change
            if (name === 'dateDebut' || name === 'dateFin') {
                const error = validateDates(
                    name === 'dateDebut' ? value : newData.dateDebut,
                    name === 'dateFin' ? value : newData.dateFin
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
            // Using a custom alert/modal is preferred over native alert()
            // For now, keeping alert() as per original code, but note for future improvements
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

        // Vérifier d'abord les erreurs de date
        const currentDateError = validateDates(formData.dateDebut, formData.dateFin);
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

            let responseData = null;

            const baseMissionData = {
                objet: formData.objet,
                dateDebut: new Date(formData.dateDebut).toISOString(),
                dateFin: new Date(formData.dateFin).toISOString(),
                moyenTransport: formData.moyenTransport || null,
                statut: formData.statut,
                directeur_id: parseInt(formData.directeur_id, 10),
                // Ensure vehicule_id is null if empty string, or parsed int
                vehicule_id: formData.vehicule_id ? parseInt(formData.vehicule_id, 10) : null,
                trajet_predefini: pointsToSend.length > 0 ? pointsToSend : null,
            };

            if (mission?.id) {
                // MODIFICATION
                console.log("Données de mission à mettre à jour:", baseMissionData);

                const updateResponse = await fetch(`${API_BASE_URL}/missions/${mission.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(baseMissionData),
                });

                if (!updateResponse.ok) {
                    const errorBody = await updateResponse.json();
                    console.error("Erreur lors de la mise à jour de la mission (API Response):", errorBody);
                    throw new Error(`Échec de la mise à jour de la mission: ${updateResponse.statusText || updateResponse.status}. Détails: ${JSON.stringify(errorBody)}`);
                }
                responseData = await updateResponse.json();
                console.log("Mission mise à jour avec succès:", responseData);

            } else {
                // CRÉATION
                console.log("Données de mission à créer:", baseMissionData);

                const createResponse = await fetch(`${API_BASE_URL}/missions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(baseMissionData),
                });

                if (!createResponse.ok) {
                    const errorBody = await createResponse.json();
                    console.error("Erreur lors de la création de la mission (API Response):", errorBody);
                    throw new Error(`Échec de la création de la mission: ${createResponse.statusText || createResponse.status}. Détails: ${JSON.stringify(errorBody)}`);
                }
                responseData = await createResponse.json();
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
                        <Form.Group as={Col} controlId="formDirecteurId">
                            <Form.Label className="form-label text-dark">ID Directeur *</Form.Label>
                            <Form.Control
                                type="number"
                                name="directeur_id"
                                value={formData.directeur_id}
                                onChange={handleChange}
                                required
                                placeholder="ID du directeur"
                            />
                            <Form.Control.Feedback type="invalid">
                                Veuillez fournir l'ID du directeur.
                            </Form.Control.Feedback>
                        </Form.Group>
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
                            disabled={isSubmitting || dateError !== ''}
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