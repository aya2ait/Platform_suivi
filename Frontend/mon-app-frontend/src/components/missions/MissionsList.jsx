import React, { useState, useEffect } from 'react';
import { Plus, Search, Filter } from 'lucide-react';
import { Container, Row, Col, Button, Form, Spinner, Alert } from 'react-bootstrap';
import ApiService from '../../api/apiService';
import MissionCard from './MissionCard';
import MissionForm from './MissionForm';
import MissionDetails from './MissionDetails';
import MissionCollaboratorAssignment from './MissionCollaboratorAssignment';
import CollaboratorManagement from './CollaboratorManagement';
import { MissionStatus } from '../../constants';
import { useAuth } from '../../contexts/AuthContext';

const MissionsList = () => {
    const { user, hasPermission, axiosInstance, authReady, isAuthenticated } = useAuth(); // Add authReady
    const [missions, setMissions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // États pour MissionForm (création/édition de mission)
    const [showMissionForm, setShowMissionForm] = useState(false);
    const [editingMission, setEditingMission] = useState(null);

    // États pour MissionDetails (affichage des détails de mission)
    const [selectedMission, setSelectedMission] = useState(null);

    // États pour MissionCollaboratorAssignment
    const [showAssignmentForm, setShowAssignmentForm] = useState(false);
    const [missionIdToAssign, setMissionIdToAssign] = useState(null);
    const [collaboratorsForAssignment, setCollaboratorsForAssignment] = useState([]);

    // États pour CollaboratorManagement
    const [showCollaboratorManagementModal, setShowCollaboratorManagementModal] = useState(false);
    const [missionIdForManagement, setMissionIdForManagement] = useState(null);

    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('');

    const fetchMissions = async () => {
        // Don't make API calls if auth is not ready or user is not authenticated
        if (!authReady || !isAuthenticated) {
            console.log('Skipping API call - auth not ready or not authenticated');
            return;
        }

        try {
            setLoading(true);
            const params = {};
            if (statusFilter) params.statut = statusFilter;
            if (searchTerm) params.search = searchTerm;

            const data = await ApiService.getMissions(params);
            setMissions(data);
            setError(null);
        } catch (err) {
            setError('Erreur lors du chargement des missions.');
            console.error('Erreur:', err);
        } finally {
            setLoading(false);
        }
    };

    // Updated useEffect to depend on authReady and isAuthenticated
    useEffect(() => {
        // Only proceed if auth is ready and user is authenticated
        if (!authReady) {
            console.log('Auth not ready yet, waiting...');
            return;
        }

        if (!isAuthenticated) {
            console.log('User not authenticated');
            setLoading(false);
            return;
        }

        const handler = setTimeout(() => {
            fetchMissions();
        }, 300);

        return () => {
            clearTimeout(handler);
        };
    }, [statusFilter, searchTerm, authReady, isAuthenticated]); // Add authReady and isAuthenticated as dependencies

    // Show loading while auth is not ready
    if (!authReady) {
        return (
            <div className="d-flex justify-content-center align-items-center h-64">
                <Spinner animation="border" role="status" variant="primary">
                    <span className="visually-hidden">Initialisation...</span>
                </Spinner>
            </div>
        );
    }

    // If auth is ready but user is not authenticated, show appropriate message
    if (!isAuthenticated) {
        return (
            <Alert variant="warning" className="text-center py-4">
                Vous devez être connecté pour accéder aux missions.
            </Alert>
        );
    }

    const handleCreateMission = async (responseData) => {
        try {
            setShowMissionForm(false);
            fetchMissions();
        } catch (err) {
            console.error('Erreur:', err);
            alert(`Erreur: ${err.message}`);
        }
    };

    const handleUpdateMission = async (missionData) => {
        try {
            await ApiService.updateMission(editingMission.id, missionData);
            setEditingMission(null);
            setShowMissionForm(false);
            fetchMissions();
        } catch (err) {
            console.error('Erreur lors de la modification:', err);
            alert(`Erreur lors de la modification de la mission: ${err.message || 'Veuillez vérifier les données.'}`);
        }
    };

    const handleDeleteMission = async (missionId) => {
        if (window.confirm('Êtes-vous sûr de vouloir supprimer cette mission ?')) {
            try {
                await ApiService.deleteMission(missionId);
                fetchMissions();
            } catch (err) {
                console.error('Erreur lors de la suppression:', err);
                alert(`Erreur lors de la suppression de la mission: ${err.message || 'Veuillez réessayer.'}`);
            }
        }
    };

    const handleAssignCollaboratorsClick = (mission) => {
        setMissionIdToAssign(mission.id);
        if (mission.affectations && Array.isArray(mission.affectations)) {
            setCollaboratorsForAssignment(
                mission.affectations.map(aff => ({
                    matricule: aff.collaborateur.matricule,
                    nom: aff.collaborateur.nom || ''
                }))
            );
        } else {
            setCollaboratorsForAssignment([]);
        }
        setShowAssignmentForm(true);
    };

    const handleCollaboratorAssignmentSaved = () => {
        setShowAssignmentForm(false);
        setMissionIdToAssign(null);
        setCollaboratorsForAssignment([]);
        fetchMissions();
    };

    const openCollaboratorManagement = (missionId) => {
        setMissionIdForManagement(missionId);
        setShowCollaboratorManagementModal(true);
    };

    const closeCollaboratorManagement = () => {
        setShowCollaboratorManagementModal(false);
        setMissionIdForManagement(null);
        fetchMissions();
    };

    if (loading) {
        return (
            <div className="d-flex justify-content-center align-items-center h-64">
                <Spinner animation="border" role="status" variant="primary">
                    <span className="visually-hidden">Chargement...</span>
                </Spinner>
            </div>
        );
    }

    if (error) {
        return (
            <Alert variant="danger" className="text-center py-4">
                {error}
                <div className="mt-3">
                    <Button variant="primary" onClick={fetchMissions}>
                        Réessayer
                    </Button>
                </div>
            </Alert>
        );
    }

    return (
        <Container fluid className="py-4">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h2 className="h4 fw-bold text-dark mb-1">Missions</h2>
                    <p className="text-muted mb-0">Gérez les missions de déplacement</p>
                </div>
                <Button
                    variant="primary"
                    onClick={() => { setShowMissionForm(true); setEditingMission(null); }}
                    className="d-flex align-items-center gap-2"
                >
                    <Plus className="icon-sm" />
                    Nouvelle Mission
                </Button>
            </div>

            {/* Filters */}
            <div className="d-flex flex-column flex-md-row gap-3 mb-4">
                <div className="position-relative flex-grow-1">
                    <Search className="position-absolute start-0 translate-middle-y text-muted" style={{ top: '50%', left: '1rem' }} size={16} />
                    <Form.Control
                        type="text"
                        placeholder="Rechercher une mission par objet..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="ps-5"
                    />
                </div>
                <div className="d-flex align-items-center gap-2">
                    <Filter className="text-muted" size={16} />
                    <Form.Select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="">Tous les statuts</option>
                        {Object.values(MissionStatus).map(status => (
                            <option key={status} value={status}>{status.replace('_', ' ')}</option>
                        ))}
                    </Form.Select>
                </div>
            </div>

            {/* Mission Cards */}
            <Row xs={1} sm={1} md={2} lg={3} className="g-4">
                {missions.length > 0 ? (
                    missions.map((mission) => (
                        <Col key={mission.id}>
                            <MissionCard
                                mission={mission}
                                onEdit={(missionToEdit) => {
                                    setEditingMission(missionToEdit);
                                    setShowMissionForm(true);
                                }}
                                onDelete={handleDeleteMission}
                                onViewDetails={setSelectedMission}
                                onAssignCollaborators={handleAssignCollaboratorsClick} 
                                onManageCollaborators={() => openCollaboratorManagement(mission.id)} 
                            />
                        </Col>
                    ))
                ) : (
                    <Col className="text-center py-5 text-muted">
                        {searchTerm || statusFilter ? 'Aucune mission trouvée avec ces critères.' : 'Aucune mission créée pour le moment.'}
                    </Col>
                )}
            </Row>

            {/* Modals */}
            {showMissionForm && (
                <MissionForm
                    mission={editingMission}
                    onSubmit={editingMission ? handleUpdateMission : handleCreateMission}
                    onCancel={() => {
                        setShowMissionForm(false);
                        setEditingMission(null);
                    }}
                />
            )}

            {selectedMission && (
                <MissionDetails
                    mission={selectedMission}
                    onClose={() => setSelectedMission(null)}
                />
            )}

            {showAssignmentForm && missionIdToAssign && (
                <MissionCollaboratorAssignment
                    missionId={missionIdToAssign}
                    currentCollaborators={collaboratorsForAssignment}
                    onSave={handleCollaboratorAssignmentSaved}
                    onCancel={() => {
                        setShowAssignmentForm(false);
                        setMissionIdToAssign(null);
                        setCollaboratorsForAssignment([]);
                    }}
                />
            )}

            {showCollaboratorManagementModal && missionIdForManagement && (
                <CollaboratorManagement
                    missionId={missionIdForManagement}
                    show={showCollaboratorManagementModal}
                    onHide={closeCollaboratorManagement}
                    onUpdate={fetchMissions}
                />
            )}
        </Container>
    );
};

export default MissionsList;