import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, Table, Alert, Spinner, Badge } from 'react-bootstrap';

const API_BASE_URL = "http://localhost:8000"; // Make sure this matches your backend URL

const CollaboratorManagement = ({ missionId, show, onHide, onUpdate }) => {
    const [collaborators, setCollaborators] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    
    // État pour le formulaire d'ajout/modification
    const [newCollaborator, setNewCollaborator] = useState({
        matricule: '',
        action: 'add',
        dejeuner: 0,
        dinner: 0,
        accouchement: 0
    });

    // Charger les collaborateurs de la mission
    const loadCollaborators = async () => {
        if (!missionId) return;
        
        setLoading(true);
        setError('');
        
        try {
            const response = await fetch(`${API_BASE_URL}/missions/${missionId}/collaborators`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail 
                                     ? errorData.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ')
                                     : `Erreur HTTP: ${response.status}`;
                throw new Error(errorMessage);
            }
            const data = await response.json();
            console.log("Données des collaborateurs reçues:", data);
            
            // Mapper les données du backend vers le format attendu par le frontend
            const mappedData = data.map((collab) => ({
                ...collab,
                // Mapper les propriétés du backend vers celles attendues par le frontend
                collaborateur_matricule: collab.collaborateur_matricule || `ID-${collab.collaborateur_id}`,
                collaborateur_nom: collab.collaborateur_nom || 'Nom non disponible',
                montant_calcule: collab.montantCalcule || 0
            }));
            
            setCollaborators(mappedData);
        } catch (err) {
            console.error('Erreur lors du chargement des collaborateurs:', err);
            setError(`Impossible de charger les collaborateurs de la mission: ${err.message || ''}`);
        } finally {
            setLoading(false);
        }
    };

    // Charger les collaborateurs quand le composant se monte ou que missionId change
    useEffect(() => {
        if (show && missionId) {
            loadCollaborators();
            // Reset form when modal opens or missionId changes
            setNewCollaborator({
                matricule: '',
                action: 'add',
                dejeuner: 0,
                dinner: 0,
                accouchement: 0
            });
        }
    }, [show, missionId]);

    // Gérer les changements dans le formulaire
    const handleInputChange = (e) => {
        const { name, value, type } = e.target;
        setNewCollaborator(prev => ({
            ...prev,
            [name]: type === 'number' ? parseInt(value) || 0 : value
        }));
    };

    // Ajouter/Modifier un collaborateur
    const handleAddOrUpdateCollaborator = async (e) => {
        e.preventDefault();
        
        if (!newCollaborator.matricule.trim()) {
            setError('Le matricule est requis.');
            return;
        }

        setSubmitting(true);
        setError('');
        setSuccess('');

        try {
            // Construire le payload en fonction de l'action
            let collaboratorData = {
                matricule: newCollaborator.matricule,
                action: newCollaborator.action
            };

            // Ajouter les champs numériques seulement pour 'add' et 'update'
            if (newCollaborator.action === 'add' || newCollaborator.action === 'update') {
                collaboratorData = {
                    ...collaboratorData,
                    dejeuner: newCollaborator.dejeuner,
                    dinner: newCollaborator.dinner,
                    accouchement: newCollaborator.accouchement
                };
            }

            const payload = {
                collaborateurs: [collaboratorData]
            };

            console.log('Payload envoyé:', JSON.stringify(payload, null, 2));

            const response = await fetch(`${API_BASE_URL}/missions/${missionId}/manage-collaborators`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail 
                                     ? errorData.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ')
                                     : `Erreur HTTP: ${response.status}`;
                throw new Error(errorMessage);
            }
            
            if (newCollaborator.action === 'add') {
                setSuccess(`Collaborateur ${newCollaborator.matricule} ajouté avec succès.`);
            } else {
                setSuccess(`Collaborateur ${newCollaborator.matricule} mis à jour avec succès.`);
            }

            // Réinitialiser le formulaire
            setNewCollaborator({
                matricule: '',
                action: 'add',
                dejeuner: 0,
                dinner: 0,
                accouchement: 0
            });

            // Recharger la liste
            await loadCollaborators();
            
            // Notifier le parent si nécessaire
            if (onUpdate) {
                onUpdate();
            }

        } catch (err) {
            console.error('Erreur lors de la gestion du collaborateur:', err);
            setError(err.message || 'Une erreur est survenue.');
        } finally {
            setSubmitting(false);
        }
    };

    // Supprimer un collaborateur
    const handleRemoveCollaborator = async (matricule) => {
        if (!window.confirm(`Êtes-vous sûr de vouloir retirer le collaborateur ${matricule} de cette mission ?`)) {
            return;
        }

        setSubmitting(true);
        setError('');
        setSuccess('');

        try {
            const payload = {
                collaborateurs: [{
                    matricule: matricule,
                    action: 'remove'
                }]
            };

            console.log('Payload de suppression:', JSON.stringify(payload, null, 2));

            const response = await fetch(`${API_BASE_URL}/missions/${missionId}/manage-collaborators`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail 
                                     ? errorData.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ')
                                     : `Erreur HTTP: ${response.status}`;
                throw new Error(errorMessage);
            }

            setSuccess(`Collaborateur ${matricule} retiré avec succès.`);
            
            // Recharger la liste
            await loadCollaborators();
            
            // Notifier le parent si nécessaire
            if (onUpdate) {
                onUpdate();
            }

        } catch (err) {
            console.error('Erreur lors de la suppression du collaborateur:', err);
            setError(err.message || 'Une erreur est survenue.');
        } finally {
            setSubmitting(false);
        }
    };

    // Modifier un collaborateur existant (remplir le formulaire)
    const handleEditCollaborator = (collaborator) => {
        setNewCollaborator({
            matricule: collaborator.collaborateur_matricule || '', 
            action: 'update',
            dejeuner: collaborator.dejeuner || 0,
            dinner: collaborator.dinner || 0,
            accouchement: collaborator.accouchement || 0
        });
    };

    return (
        <Modal show={show} onHide={onHide} size="lg" centered>
            <Modal.Header closeButton>
                <Modal.Title>Gestion des Collaborateurs - Mission #{missionId}</Modal.Title>
            </Modal.Header>
            
            <Modal.Body style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                {error && (
                    <Alert variant="danger" dismissible onClose={() => setError('')}>
                        {error}
                    </Alert>
                )}
                
                {success && (
                    <Alert variant="success" dismissible onClose={() => setSuccess('')}>
                        {success}
                    </Alert>
                )}

                {/* Formulaire d'ajout/modification */}
                <div className="border rounded p-3 mb-4 bg-light">
                    <h6 className="fw-bold mb-3">
                        {newCollaborator.action === 'add' ? 'Ajouter un collaborateur' : 'Modifier le collaborateur'}
                    </h6>
                    
                    <Form onSubmit={handleAddOrUpdateCollaborator}>
                        <Row className="g-3">
                            <Col md={6}>
                                <Form.Group>
                                    <Form.Label>Matricule *</Form.Label>
                                    <Form.Control
                                        type="text"
                                        name="matricule"
                                        value={newCollaborator.matricule}
                                        onChange={handleInputChange}
                                        placeholder="Ex: EMP001"
                                        required
                                        disabled={newCollaborator.action === 'update'}
                                    />
                                </Form.Group>
                            </Col>
                            
                            <Col md={6}>
                                <Form.Group>
                                    <Form.Label>Action</Form.Label>
                                    <Form.Select
                                        name="action"
                                        value={newCollaborator.action}
                                        onChange={handleInputChange}
                                    >
                                        <option value="add">Ajouter</option>
                                        <option value="update">Modifier</option>
                                    </Form.Select>
                                </Form.Group>
                            </Col>
                        </Row>

                        <Row className="g-3 mt-2">
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>Déjeuners</Form.Label>
                                    <Form.Control
                                        type="number"
                                        name="dejeuner"
                                        value={newCollaborator.dejeuner}
                                        onChange={handleInputChange}
                                        min="0"
                                    />
                                </Form.Group>
                            </Col>
                            
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>Dîners</Form.Label>
                                    <Form.Control
                                        type="number"
                                        name="dinner"
                                        value={newCollaborator.dinner}
                                        onChange={handleInputChange}
                                        min="0"
                                    />
                                </Form.Group>
                            </Col>
                            
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>Hébergements</Form.Label>
                                    <Form.Control
                                        type="number"
                                        name="accouchement"
                                        value={newCollaborator.accouchement}
                                        onChange={handleInputChange}
                                        min="0"
                                    />
                                </Form.Group>
                            </Col>
                        </Row>

                        <div className="d-flex gap-2 mt-3">
                            <Button 
                                type="submit" 
                                variant={newCollaborator.action === 'add' ? 'primary' : 'warning'}
                                disabled={submitting}
                            >
                                {submitting ? (
                                    <Spinner as="span" animation="border" size="sm" className="me-2" />
                                ) : null}
                                {newCollaborator.action === 'add' ? 'Ajouter' : 'Modifier'}
                            </Button>
                            
                            {newCollaborator.action === 'update' && (
                                <Button 
                                    type="button" 
                                    variant="secondary"
                                    onClick={() => setNewCollaborator({
                                        matricule: '',
                                        action: 'add',
                                        dejeuner: 0,
                                        dinner: 0,
                                        accouchement: 0
                                    })}
                                >
                                    Annuler
                                </Button>
                            )}
                        </div>
                    </Form>
                </div>

                {/* Liste des collaborateurs */}
                <div>
                    <h6 className="fw-bold mb-3">Collaborateurs affectés</h6>
                    
                    {loading ? (
                        <div className="text-center py-4">
                            <Spinner animation="border" role="status">
                                <span className="visually-hidden">Chargement...</span>
                            </Spinner>
                        </div>
                    ) : collaborators.length === 0 ? (
                        <Alert variant="info">
                            Aucun collaborateur n'est actuellement affecté à cette mission.
                        </Alert>
                    ) : (
                        <Table striped bordered hover responsive>
                            <thead className="table-dark">
                                <tr>
                                    <th>Matricule</th>
                                    <th>Nom</th>
                                    <th>Déjeuners</th>
                                    <th>Dîners</th>
                                    <th>Hébergements</th>
                                    <th>Montant</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {collaborators.map((collab) => (
                                    <tr key={collab.id}>
                                        <td>
                                            <Badge bg="secondary">
                                                {collab.collaborateur_matricule || 'N/A'}
                                            </Badge>
                                        </td>
                                        <td>{collab.collaborateur_nom || 'N/A'}</td>
                                        <td className="text-center">{collab.dejeuner || 0}</td>
                                        <td className="text-center">{collab.dinner || 0}</td>
                                        <td className="text-center">{collab.accouchement || 0}</td>
                                        <td className="text-end">
                                            {collab.montant_calcule ? 
                                                `${collab.montant_calcule.toFixed(2)} €` : 
                                                '0.00 €'
                                            }
                                        </td>
                                        <td>
                                            <div className="d-flex gap-1">
                                                <Button
                                                    size="sm"
                                                    variant="outline-warning"
                                                    onClick={() => handleEditCollaborator(collab)}
                                                    disabled={submitting}
                                                >
                                                    Modifier
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline-danger"
                                                    onClick={() => handleRemoveCollaborator(collab.collaborateur_matricule)}
                                                    disabled={submitting}
                                                >
                                                    Retirer
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}
                </div>
            </Modal.Body>
            
            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>
                    Fermer
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default CollaboratorManagement;