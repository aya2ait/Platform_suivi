// src/components/missions/MissionCard.jsx

import React from 'react';
import { Card, Badge, Button } from 'react-bootstrap';
import { Calendar, Car, Users, Edit, Trash2, Eye, UserPlus } from 'lucide-react'; // Import UserPlus icon
import { StatusColors, MissionStatus } from '../../constants';

// Add onManageCollaborators to the props
const MissionCard = ({ mission, onEdit, onDelete, onViewDetails, onManageCollaborators }) => {
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

    return (
        <Card className="shadow-sm border border-light-subtle hover-shadow-lg transition-shadow">
            <Card.Body className="p-4">
                <div className="d-flex align-items-start justify-content-between">
                    <div className="flex-grow-1">
                        <div className="d-flex align-items-center gap-2 mb-2">
                            <h3 className="h5 mb-0 text-dark text-truncate">
                                {mission.objet}
                            </h3>
                            <Badge pill bg={getStatusVariant(mission.statut)} className="ms-2">
                                {mission.statut || 'N/A'}
                            </Badge>
                        </div>
                        <div className="small text-muted mb-0">
                            <div className="d-flex align-items-center gap-2 mb-1">
                                <Calendar className="w-4 h-4" />
                                <span>
                                    Du: {formatDate(mission.dateDebut)} - Au: {formatDate(mission.dateFin)}
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
                                {/* Display director's name if available, otherwise just ID */}
                                <span>Directeur: {mission.directeur ? `${mission.directeur.nom} ${mission.directeur.prenom}` : `ID ${mission.directeur_id}`}</span>
                            </div>
                            {mission.affectations && mission.affectations.length > 0 && (
                                <div className="d-flex align-items-center gap-2 mt-1"> {/* Added margin top for spacing */}
                                    <Users className="w-4 h-4" />
                                    <span>Collaborateurs: {mission.affectations.length}</span>
                                </div>
                            )}
                             {mission.vehicule && (
                                <div className="d-flex align-items-center gap-2 mt-1">
                                    <Car className="w-4 h-4" />
                                    <span>Véhicule: {mission.vehicule.modele} ({mission.vehicule.immatriculation})</span>
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="d-flex flex-column gap-2 ms-4"> {/* Changed to flex-column for vertical buttons */}
                        <Button
                            variant="outline-secondary"
                            size="sm"
                            className="p-1 icon-button"
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
                        {/* New button for managing collaborators */}
                        <Button
                            variant="outline-info" // Using 'info' for a distinct color for collaborator management
                            size="sm"
                            className="p-1 icon-button"
                            onClick={() => onManageCollaborators(mission.id)} // Pass mission.id to the handler
                            title="Gérer les collaborateurs"
                        >
                            <UserPlus className="w-4 h-4" /> {/* UserPlus icon for adding/managing users */}
                        </Button>
                        <Button
                            variant="outline-danger"
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