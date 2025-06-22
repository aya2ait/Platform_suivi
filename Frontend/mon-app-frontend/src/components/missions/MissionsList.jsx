import React, { useState, useEffect } from 'react';
import { Plus, Search, Filter } from 'lucide-react';
import { Container, Row, Col, Button, Form, Spinner, Alert } from 'react-bootstrap';
import ApiService from '../../api/apiService';
import MissionCard from './MissionCard';
import MissionForm from './MissionForm';
import MissionDetails from './MissionDetails';
import MissionCollaboratorAssignment from './MissionCollaboratorAssignment'; // Import the new component
import { MissionStatus } from '../../constants';

const MissionsList = () => {
    const [missions, setMissions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // State for MissionForm (create/edit mission details)
    const [showMissionForm, setShowMissionForm] = useState(false);
    const [editingMission, setEditingMission] = useState(null); // The mission object being edited

    // State for MissionDetails modal
    const [selectedMission, setSelectedMission] = useState(null); // The mission object for details view

    // State for MissionCollaboratorAssignment modal
    const [showAssignmentForm, setShowAssignmentForm] = useState(false);
    const [missionIdToAssign, setMissionIdToAssign] = useState(null); // ID of the mission to assign collaborators to
    const [collaboratorsForAssignment, setCollaboratorsForAssignment] = useState([]); // Current collaborators for that mission

    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('');

    const fetchMissions = async () => {
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

    useEffect(() => {
        const handler = setTimeout(() => {
            fetchMissions();
        }, 300);

        return () => {
            clearTimeout(handler);
        };
    }, [statusFilter, searchTerm]);

    // Handles submission from MissionForm when creating a NEW mission
    // Dans MissionsList.jsx
    const handleCreateMission = async (responseData) => {
     try {
        // ✅ responseData est déjà la mission créée par MissionForm
        setShowMissionForm(false);
        
        // Utiliser directement responseData (qui contient déjà l'ID)
        setMissionIdToAssign(responseData.id);
        setCollaboratorsForAssignment([]);
        setShowAssignmentForm(true);
        
        fetchMissions(); // Refresh la liste
     } catch (err) {
        console.error('Erreur:', err);
        alert(`Erreur: ${err.message}`);
    }
};

    // Handles submission from MissionForm when updating an EXISTING mission
    const handleUpdateMission = async (missionData) => {
        try {
            await ApiService.updateMission(editingMission.id, missionData);
            setEditingMission(null);
            setShowMissionForm(false);
            fetchMissions(); // Refresh the list after update
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

    // New handler for clicking "Assign Collaborators" button on a MissionCard
    const handleAssignCollaboratorsClick = (mission) => {
        setMissionIdToAssign(mission.id);
        // Ensure mission.affectations exists and is an array before mapping
        if (mission.affectations && Array.isArray(mission.affectations)) {
            setCollaboratorsForAssignment(
                mission.affectations.map(aff => ({
                    matricule: aff.collaborateur.matricule,
                    nom: aff.collaborateur.nom || '' // Use a default empty string if name is not present
                }))
            );
        } else {
            setCollaboratorsForAssignment([]);
        }
        setShowAssignmentForm(true);
    };

    // Callback when collaborators are saved in MissionCollaboratorAssignment
    const handleCollaboratorAssignmentSaved = () => {
        setShowAssignmentForm(false); // Close the assignment modal
        setMissionIdToAssign(null); // Clear the selected mission ID
        setCollaboratorsForAssignment([]); // Clear the collaborators state
        fetchMissions(); // Refresh the main mission list to show updated assignments
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

            {/* NEW: Mission Collaborator Assignment Modal */}
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
        </Container>
    );
};

export default MissionsList;