// src/components/missions/MissionDetails.jsx

import React, { useState, useEffect } from 'react';
import { Modal, Button, Spinner, Badge } from 'react-bootstrap'; // Import Modal, Button, Spinner, Badge
import { Users } from 'lucide-react';
import ApiService from '../../api/apiService';
import { StatusColors, MissionStatus } from '../../constants'; // Import StatusColors and MissionStatus

const MissionDetails = ({ mission, onClose }) => {
  const [collaborators, setCollaborators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchCollaborators = async () => {
      if (!mission?.id) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await ApiService.getMissionCollaborators(mission.id);
        setCollaborators(data);
      } catch (err) {
        console.error('Erreur lors du chargement des collaborateurs:', err);
        setError('Impossible de charger les collaborateurs.');
      } finally {
        setLoading(false);
      }
    };

    fetchCollaborators();
  }, [mission?.id]); // Re-fetch when mission ID changes

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      console.error("Invalid date string for formatting:", dateString, e);
      return 'Invalid Date';
    }
  };

  // Helper to map status to Bootstrap variant for Badge
  const getStatusVariant = (status) => {
    switch (status) {
      case MissionStatus.CREEE:
        return 'primary';
      case MissionStatus.EN_COURS:
        return 'warning';
      case MissionStatus.TERMINEE:
        return 'success';
      case MissionStatus.ANNULEE:
        return 'danger';
      default:
        return 'secondary';
    }
  };

  // MissionDetails is now rendered conditionally inside MissionsList.jsx
  // So, if !mission, it won't be rendered. No need for the 'if (!mission) return null;' check here.

  return (
    <Modal show={true} onHide={onClose} centered size="lg"> {/* show=true makes it visible, onHide for closing */}
      <Modal.Header closeButton> {/* closeButton adds the X icon */}
        <Modal.Title className="h5 fw-semibold text-dark">Détails de la Mission</Modal.Title>
      </Modal.Header>
      <Modal.Body className="p-4"> {/* Equivalent to p-6 but Bootstrap usually uses less aggressive padding */}
        <div className="mb-4"> {/* space-y-6 is converted to mb-4 */}
          <h4 className="text-uppercase text-secondary fs-6 fw-medium mb-2"> {/* text-sm, font-medium, text-gray-500, uppercase, tracking-wide */}
            Informations générales
          </h4>
          <div className="bg-light p-3 rounded space-y-3"> {/* bg-gray-50 p-4 rounded-lg space-y-3 */}
            <div>
              <span className="fw-medium text-dark">Objet:</span> {/* font-medium text-gray-700 */}
              <p className="text-dark mt-1 mb-0">{mission.objet}</p> {/* text-gray-900 mt-1 */}
            </div>
            <div className="row g-3"> {/* grid grid-cols-2 gap-4 converted to Bootstrap Grid */}
              <div className="col-md-6"> {/* Equivalent to first column */}
                <span className="fw-medium text-dark">Date de début:</span>
                <p className="text-dark mb-0">{formatDate(mission.dateDebut)}</p>
              </div>
              <div className="col-md-6"> {/* Equivalent to second column */}
                <span className="fw-medium text-dark">Date de fin:</span>
                <p className="text-dark mb-0">{formatDate(mission.dateFin)}</p>
              </div>
            </div>
            <div className="row g-3">
              <div className="col-md-6">
                <span className="fw-medium text-dark">Statut:</span>
                <Badge bg={getStatusVariant(mission.statut)} className="d-block mt-1"> {/* d-block makes it block level, mt-1 for margin-top */}
                  {mission.statut || 'N/A'}
                </Badge>
              </div>
              {mission.moyenTransport && (
                <div className="col-md-6">
                  <span className="fw-medium text-dark">Transport:</span>
                  <p className="text-dark mb-0">{mission.moyenTransport}</p>
                </div>
              )}
            </div>
            <div>
              <span className="fw-medium text-dark">ID Directeur:</span>
              <p className="text-dark mt-1 mb-0">{mission.directeur_id}</p>
            </div>
            {mission.vehicule_id && (
              <div>
                <span className="fw-medium text-dark">ID Véhicule:</span>
                <p className="text-dark mt-1 mb-0">{mission.vehicule_id}</p>
              </div>
            )}
          </div>
        </div>

        <div>
          <h4 className="text-uppercase text-secondary fs-6 fw-medium mb-2">
            Collaborateurs affectés
          </h4>
          <div className="bg-light p-3 rounded">
            {loading ? (
              <div className="d-flex justify-content-center align-items-center py-3"> {/* Centering spinner */}
                <Spinner animation="border" size="sm" role="status">
                  <span className="visually-hidden">Chargement...</span>
                </Spinner>
                <p className="ms-2 text-muted mb-0">Chargement des collaborateurs...</p>
              </div>
            ) : error ? (
              <p className="text-danger">{error}</p>
            ) : collaborators.length > 0 ? (
              <div className="space-y-2"> {/* Keep space-y-2 or convert to mb-2 on children */}
                {collaborators.map((affectation) => (
                  <div key={affectation.collaborateur_id} className="d-flex align-items-center gap-2 small">
                    <Users className="w-4 h-4 text-muted" /> {/* text-gray-400 becomes text-muted */}
                    <span>ID Collaborateur: {affectation.collaborateur_id}</span>
                    {affectation.montantCalcule !== undefined && (
                      <span className="text-muted"> {/* text-gray-500 becomes text-muted */}
                        (Montant: {affectation.montantCalcule}€)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted">Aucun collaborateur affecté</p>
            )}
          </div>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="light" className="w-100" onClick={onClose}> {/* w-100 for full width */}
          Fermer
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default MissionDetails;