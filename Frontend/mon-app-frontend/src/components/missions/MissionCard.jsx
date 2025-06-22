// src/components/missions/MissionCard.jsx

import React from 'react';
import { Card, Badge, Button } from 'react-bootstrap'; // Import Card, Badge, Button from react-bootstrap
import { Calendar, Car, Users, Edit, Trash2, Eye } from 'lucide-react'; // Keep Lucide icons
import { StatusColors, MissionStatus } from '../../constants'; // Import constants

const MissionCard = ({ mission, onEdit, onDelete, onViewDetails }) => {
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (e) {
      console.error("Invalid date string for formatting:", dateString, e);
      return 'Invalid Date';
    }
  };

  // Helper to map status to Bootstrap variant
  const getStatusVariant = (status) => {
    switch (status) {
      case MissionStatus.CREEE:
        return 'primary'; // Or 'info' for a light blue
      case MissionStatus.EN_COURS:
        return 'warning';
      case MissionStatus.TERMINEE:
        return 'success';
      case MissionStatus.ANNULEE:
        return 'danger';
      default:
        return 'secondary'; // Default gray for unknown status
    }
  };

  return (
    <Card className="shadow-sm border border-light-subtle hover-shadow-lg transition-shadow">
      <Card.Body className="p-4"> {/* p-4 is equivalent to p-6 but Bootstrap usually uses less aggressive padding */}
        <div className="d-flex align-items-start justify-content-between">
          <div className="flex-grow-1"> {/* flex-grow-1 is equivalent to flex-1 */}
            <div className="d-flex align-items-center gap-2 mb-2">
              <h3 className="h5 mb-0 text-dark text-truncate"> {/* h5 for text-lg, text-dark for text-gray-900, mb-0 to remove default margin */}
                {mission.objet}
              </h3>
              <Badge pill bg={getStatusVariant(mission.statut)} className="ms-2"> {/* ms-2 for ml-2 */}
                {mission.statut || 'N/A'}
              </Badge>
            </div>
            <div className="small text-muted mb-0"> {/* small for text-sm, text-muted for text-gray-600, mb-0 to reset margin */}
              <div className="d-flex align-items-center gap-2 mb-1"> {/* mb-1 for slight vertical spacing */}
                <Calendar className="w-4 h-4" /> {/* Lucide icons remain the same */}
                <span>
                  {formatDate(mission.dateDebut)} - {formatDate(mission.dateFin)}
                </span>
              </div>
              {mission.moyenTransport && (
                <div className="d-flex align-items-center gap-2 mb-1">
                  <Car className="w-4 h-4" />
                  <span>{mission.moyenTransport}</span>
                </div>
              )}
              <div className="d-flex align-items-center gap-2">
                <Users className="w-4 h-4" />
                <span>ID Directeur: {mission.directeur_id}</span>
              </div>
            </div>
          </div>
          <div className="d-flex gap-2 ms-4"> {/* ms-4 for ml-4 */}
            <Button
              variant="outline-secondary" // A light button style
              size="sm" // Smaller button
              className="p-1 icon-button" // Custom class for icon only button styling
              onClick={() => onViewDetails(mission)}
              title="Voir les détails"
            >
              <Eye className="w-4 h-4" />
            </Button>
            <Button
              variant="outline-secondary"
              size="sm"
              className="p-1 icon-button"
              onClick={() => onEdit(mission)}
              title="Modifier la mission"
            >
              <Edit className="w-4 h-4" />
            </Button>
            <Button
              variant="outline-danger" // Red for delete action
              size="sm"
              className="p-1 icon-button"
              onClick={() => onDelete(mission.id)}
              title="Supprimer la mission"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </Card.Body>
    </Card>
  );
};

export default MissionCard;