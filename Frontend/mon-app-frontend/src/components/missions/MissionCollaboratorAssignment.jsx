import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, Spinner, Badge } from 'react-bootstrap';
import { useAuth } from '../../contexts/AuthContext'; // Ajout de l'import
import ApiService from '../../api/apiService';

const MissionCollaboratorAssignment = ({ missionId, currentCollaborators = [], onSave, onCancel }) => {
    const { authReady } = useAuth(); // Utilisation du contexte d'authentification
    const [collaborateurs, setCollaborateurs] = useState(currentCollaborators);
    const [newCollaborateurMatricule, setNewCollaborateurMatricule] = useState('');
    const [loadingCollaborateur, setLoadingCollaborateur] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        setCollaborateurs(currentCollaborators);
    }, [currentCollaborators]);

    const addCollaborateur = async () => {
        const matricule = newCollaborateurMatricule.trim();
        if (!matricule) {
            alert("Veuillez saisir un matricule.");
            return;
        }

        if (collaborateurs.some(collab => collab.matricule === matricule)) {
            alert("Ce collaborateur est déjà dans la liste.");
            return;
        }

        setLoadingCollaborateur(true);
        try {
            // Option 1: Valider le matricule via l'API (recommandé)
            try {
                const allCollaborators = await ApiService.getAllCollaborators();
                const foundCollaborator = allCollaborators.find(c => c.matricule === matricule);
                
                if (!foundCollaborator) {
                    alert("Matricule non trouvé dans la base de données.");
                    setLoadingCollaborateur(false);
                    return;
                }

                const nouveauCollaborateur = {
                    matricule: matricule,
                    nom: foundCollaborator.nom || `Collaborateur ${matricule}`,
                };

                setCollaborateurs(prev => [...prev, nouveauCollaborateur]);
                setNewCollaborateurMatricule('');
            } catch (validationError) {
                console.error("Erreur lors de la validation du matricule:", validationError);
                // Fallback: ajouter sans validation si l'API n'est pas disponible
                const nouveauCollaborateur = {
                    matricule: matricule,
                    nom: `Collaborateur ${matricule}`, // Placeholder name
                };

                setCollaborateurs(prev => [...prev, nouveauCollaborateur]);
                setNewCollaborateurMatricule('');
            }

        } catch (error) {
            console.error("Erreur lors de l'ajout du collaborateur:", error);
            alert("Erreur lors de l'ajout du collaborateur. Vérifiez le matricule et la connexion.");
        } finally {
            setLoadingCollaborateur(false);
        }
    };

    const removeCollaborateur = (matricule) => {
        setCollaborateurs(prev => prev.filter(collab => collab.matricule !== matricule));
    };

    const handleSaveAssignments = async () => {
        if (!missionId) {
            alert("Impossible d'affecter des collaborateurs: ID de mission manquant.");
            return;
        }

        if (!authReady) {
            alert("Authentification en cours, veuillez patienter.");
            return;
        }

        setIsSaving(true);
        try {
            const assignmentData = collaborateurs.map(c => ({ matricule: c.matricule }));

            console.log("Affectation des collaborateurs à la mission:", missionId, assignmentData);

            const affectationResult = await ApiService.assignCollaborators(missionId, assignmentData);

            console.log("Collaborateurs affectés avec succès:", affectationResult);
            onSave(affectationResult); // Passer le résultat au composant parent
        } catch (error) {
            console.error("Erreur lors de l'affectation des collaborateurs:", error);
            alert(`Erreur lors de l'affectation des collaborateurs: ${error.message || "Échec de l'affectation."}`);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Modal show={true} onHide={onCancel} centered>
            <Modal.Header closeButton>
                <Modal.Title className="h5 fw-semibold text-dark">
                    Affecter des collaborateurs à la Mission {missionId}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="p-4">
                <Form.Group className="mb-3">
                    <Form.Label className="form-label text-dark">Matricule du collaborateur</Form.Label>
                    <Row className="align-items-center g-2">
                        <Col xs={12} md={8}>
                            <Form.Control
                                type="text"
                                value={newCollaborateurMatricule}
                                onChange={(e) => setNewCollaborateurMatricule(e.target.value)}
                                placeholder="Matricule du collaborateur"
                                onKeyPress={(e) => {
                                    if (e.key === 'Enter') {
                                        e.preventDefault();
                                        addCollaborateur();
                                    }
                                }}
                            />
                        </Col>
                        <Col xs="auto">
                            <Button
                                variant="success"
                                onClick={addCollaborateur}
                                disabled={loadingCollaborateur || !newCollaborateurMatricule.trim() || !authReady}
                            >
                                {loadingCollaborateur ?
                                    <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> :
                                    'Ajouter'
                                }
                            </Button>
                        </Col>
                    </Row>
                </Form.Group>

                {collaborateurs.length > 0 && (
                    <div className="mt-2">
                        <small className="text-muted">Collaborateurs affectés :</small>
                        <div className="mt-1">
                            {collaborateurs.map((collab, idx) => (
                                <Badge
                                    key={idx}
                                    bg="primary"
                                    className="me-2 mb-1 d-inline-flex align-items-center"
                                >
                                    {collab.matricule} {collab.nom ? `(${collab.nom})` : ''}
                                    <Button
                                        variant="link"
                                        size="sm"
                                        className="text-white p-0 ms-1"
                                        style={{ fontSize: '12px', lineHeight: 1 }}
                                        onClick={() => removeCollaborateur(collab.matricule)}
                                    >
                                        ×
                                    </Button>
                                </Badge>
                            ))}
                        </div>
                    </div>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button 
                    variant="primary" 
                    onClick={handleSaveAssignments} 
                    disabled={isSaving || !authReady}
                >
                    {isSaving ? 
                        <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> : 
                        'Enregistrer les affectations'
                    }
                </Button>
                <Button variant="secondary" onClick={onCancel} disabled={isSaving}>
                    Annuler
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default MissionCollaboratorAssignment;