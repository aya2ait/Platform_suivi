import React, { useState, useEffect, useCallback } from 'react';
import moment from 'moment'; // For date formatting, install with `npm install moment` or `yarn add moment`

// Import the authentication context and axios instance
// Adjusted path: '../../contexts/AuthContext' because CollaborateurMissions.jsx is now in 'src/components/collaborateurs/'
import { useAuth, axiosInstance } from '../../contexts/AuthContext';

const CollaborateurMissions = () => {
    // Use the useAuth hook to get authentication state and methods
    const { isAuthenticated, loading: authLoading, authReady } = useAuth();

    const [profile, setProfile] = useState(null);
    const [missions, setMissions] = useState([]);
    const [totalMissions, setTotalMissions] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [missionsPerPage, setMissionsPerPage] = useState(10);
    const [totalPages, setTotalPages] = useState(1);
    const [filterStatus, setFilterStatus] = useState('');
    const [filterStartDate, setFilterStartDate] = useState('');
    const [filterEndDate, setFilterEndDate] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedMission, setSelectedMission] = useState(null);
    // Removed states for missionStats, recentMissions, periodMissions, and their related loading/error states
    const [selectedMissionAffectation, setSelectedMissionAffectation] = useState(null);

    // États de chargement et d'erreur généraux pour la liste principale des missions
    const [componentLoading, setComponentLoading] = useState(true);
    const [error, setError] = useState(null);


    // Fonction générique pour récupérer les données, avec des setters d'erreur/chargement spécifiques
    const fetchData = useCallback(async (endpoint, setStateFunction, params = {}, specificSetError = setError, specificSetLoading = setComponentLoading) => {
        specificSetLoading(true);
        specificSetError(null); // Clear previous specific error
        try {
            const response = await axiosInstance.get(endpoint, { params });
            setStateFunction(response.data);
            return response.data;
        } catch (err) {
            console.error(`Error fetching ${endpoint}:`, err.response?.data || err.message);
            // Capture the specific error message from the backend if available
            let errorMessage = 'An error occurred';
            if (err.response?.data?.detail) {
                if (Array.isArray(err.response.data.detail)) {
                    // If 'detail' is an array of validation errors, join their messages
                    errorMessage = err.response.data.detail.map(e => {
                        if (typeof e === 'object' && e !== null) {
                            // Prioritize 'msg' for Pydantic validation errors, then 'detail', then stringify
                            return e.msg || e.detail || JSON.stringify(e);
                        }
                        return String(e); // Fallback for non-object elements in detail array
                    }).join('; ');
                } else if (typeof err.response.data.detail === 'string') {
                    // If 'detail' is a simple string
                    errorMessage = err.response.data.detail;
                } else if (typeof err.response.data.detail === 'object' && err.response.data.detail !== null) {
                    // If 'detail' is an object (e.g., {detail: "message"})
                    errorMessage = err.response.data.detail.detail || JSON.stringify(err.response.data.detail);
                }
            } else if (err.message) {
                errorMessage = err.message;
            }
            // Ensure errorMessage is a string before setting it to prevent "Objects are not valid as a React child"
            specificSetError(String(errorMessage));
            return null;
        } finally {
            specificSetLoading(false);
        }
    }, []); // No dependencies needed for axiosInstance as it's configured globally

    // Fetch Profile - only if authenticated and auth context is ready
    useEffect(() => {
        if (isAuthenticated && authReady) {
            fetchData('/collaborateur/profile', setProfile);
        }
    }, [isAuthenticated, authReady, fetchData]);

    // Fetch Missions (with filters and pagination) - only if authenticated and auth context is ready
    const fetchMissions = useCallback(async () => {
        if (isAuthenticated && authReady) {
            const data = await fetchData('/collaborateur/missions', setMissions, {
                statut: filterStatus || undefined,
                date_debut: filterStartDate || undefined,
                date_fin: filterEndDate || undefined,
                page: currentPage,
                per_page: missionsPerPage,
            });
            if (data) {
                setMissions(data.missions);
                setTotalMissions(data.total);
                setTotalPages(data.total_pages);
            }
        }
    }, [isAuthenticated, authReady, fetchData, filterStatus, filterStartDate, filterEndDate, currentPage, missionsPerPage]);

    useEffect(() => {
        fetchMissions();
    }, [fetchMissions]);

    // Fetch Mission Details
    const fetchMissionDetails = async (missionId) => {
        if (isAuthenticated && authReady) {
            setSelectedMissionAffectation(null); // Clear previous affectation
            await fetchData(`/collaborateur/missions/${missionId}`, (data) => setSelectedMission(data.mission));
        }
    };

    // Fetch Mission Search Results
    const handleSearch = async () => {
        if (isAuthenticated && authReady && searchQuery.trim()) {
            const data = await fetchData('/collaborateur/missions/search', setMissions, {
                query: searchQuery,
                page: currentPage,
                per_page: missionsPerPage,
            });
            if (data) {
                setMissions(data.missions);
                setTotalMissions(data.total);
                setTotalPages(data.total_pages);
            }
        } else if (!searchQuery.trim() && isAuthenticated && authReady) {
            // If search query is cleared, re-fetch all missions
            fetchMissions();
        }
    };

    // Removed useEffect for fetching Mission Stats
    // Removed useEffect for fetching Recent Missions
    // Removed fetchMissionsByPeriod function

    // Fetch Mission Affectation Details
    const fetchMissionAffectation = async (missionId) => {
        if (isAuthenticated && authReady) {
            await fetchData(`/collaborateur/missions/${missionId}/affectation`, setSelectedMissionAffectation);
        }
    };

    const handlePageChange = (newPage) => {
        setCurrentPage(newPage);
    };

    const handleFilterSubmit = (e) => {
        e.preventDefault();
        setCurrentPage(1); // Reset to first page on new filter
        fetchMissions();
    };

    const handleClearFilters = () => {
        setFilterStatus('');
        setFilterStartDate('');
        setFilterEndDate('');
        setCurrentPage(1);
        fetchMissions();
    };

    // Handle initial loading state based on AuthContext
    if (authLoading || !authReady) {
        return <div className="p-4 text-blue-500">Authenticating...</div>;
    }

    if (!isAuthenticated) {
        return <div className="p-4 text-red-500">Please log in to view collaborator missions.</div>;
    }

    // Adjusted combined loading check
    if (componentLoading && !profile && missions.length === 0) {
        return <div className="p-4 text-blue-500">Loading data...</div>;
    }

    if (error) {
        return <div className="p-4 text-red-500">Error: {error}</div>;
    }

    return (
        <div className="p-6 bg-gray-100 min-h-screen font-inter"> {/* Added font-inter */}
            <h1 className="text-3xl font-bold text-gray-800 mb-6">Tableau de Bord Collaborateur</h1>

            {/* Profile Section */}
            <div className="bg-white p-6 rounded-lg shadow-md mb-8">
                <h2 className="text-2xl font-semibold text-gray-700 mb-4">Mon Profil</h2>
                {profile ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <p><strong>Nom:</strong> {profile.nom}</p>
                        <p><strong>Matricule:</strong> {profile.matricule}</p>
                        <p><strong>Disponible:</strong> {profile.disponible ? 'Oui' : 'Non'}</p>
                        <p><strong>Type Collaborateur:</strong> {profile.type_collaborateur}</p>
                        <p><strong>Direction:</strong> {profile.direction}</p>
                    </div>
                ) : (
                    <p>Chargement du profil...</p>
                )}
            </div>

            {/* Removed Mission Statistics Section */}
            {/* Removed Recent Missions Section */}
            {/* Removed Missions by Period Section */}

            {/* Mission List Section */}
            <div className="bg-white p-6 rounded-lg shadow-md mb-8">
                <h2 className="text-2xl font-semibold text-gray-700 mb-4">Mes Missions</h2>

                {/* Filters */}
                <form onSubmit={handleFilterSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 items-end">
                    <div>
                        <label htmlFor="statut" className="block text-sm font-medium text-gray-700 mb-1">Statut:</label>
                        <select
                            id="statut"
                            value={filterStatus}
                            onChange={(e) => setFilterStatus(e.target.value)}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="">Tous les statuts</option>
                            <option value="CREEE">Créée</option>
                            <option value="EN_COURS">En cours</option>
                            <option value="TERMINEE">Terminée</option>
                            <option value="ANNULEE">Annulée</option>
                        </select>
                    </div>
                    <div>
                        <label htmlFor="dateDebutFilter" className="block text-sm font-medium text-gray-700 mb-1">Date Début:</label>
                        <input
                            type="date"
                            id="dateDebutFilter"
                            value={filterStartDate ? moment(filterStartDate).format('YYYY-MM-DD') : ''}
                            onChange={(e) => setFilterStartDate(e.target.value ? moment(e.target.value).format('YYYY-MM-DDTHH:mm:ss') + 'Z' : '')}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label htmlFor="dateFinFilter" className="block text-sm font-medium text-gray-700 mb-1">Date Fin:</label>
                        <input
                            type="date"
                            id="dateFinFilter"
                            value={filterEndDate ? moment(filterEndDate).format('YYYY-MM-DD') : ''}
                            onChange={(e) => setFilterEndDate(e.target.value ? moment(e.target.value).format('YYYY-MM-DDTHH:mm:ss') + 'Z' : '')}
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>
                    <div className="flex gap-2">
                        <button
                            type="submit"
                            className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50"
                        >
                            Filtrer
                        </button>
                        <button
                            type="button"
                            onClick={handleClearFilters}
                            className="bg-gray-300 text-gray-800 px-4 py-2 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-opacity-50"
                        >
                            Effacer Filtres
                        </button>
                    </div>
                </form>

                {/* Search */}
                <div className="flex mb-6 gap-2">
                    <input
                        type="text"
                        placeholder="Rechercher par objet, moyen de transport..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="flex-grow border border-gray-300 rounded-md shadow-sm p-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <button
                        onClick={handleSearch}
                        className="bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-opacity-50"
                    >
                        Rechercher
                    </button>
                </div>

                {/* Missions Table */}
                {missions.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="min-w-full bg-white border border-gray-200 rounded-lg">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                                    <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Objet</th>
                                    <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Début</th>
                                    <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fin</th>
                                    <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Statut</th>
                                    <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {missions.map((mission) => (
                                    <tr key={mission.id}>
                                        <td className="py-3 px-4 whitespace-nowrap text-sm text-gray-900">{mission.id}</td>
                                        <td className="py-3 px-4 whitespace-nowrap text-sm text-gray-900">{mission.objet}</td>
                                        <td className="py-3 px-4 whitespace-nowrap text-sm text-gray-900">{moment(mission.dateDebut).format('DD/MM/YYYY')}</td>
                                        <td className="py-3 px-4 whitespace-nowrap text-sm text-gray-900">{moment(mission.dateFin).format('DD/MM/YYYY')}</td>
                                        <td className="py-3 px-4 whitespace-nowrap text-sm text-gray-900">
                                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                                                mission.statut === 'CREEE' ? 'bg-blue-100 text-blue-800' :
                                                mission.statut === 'EN_COURS' ? 'bg-yellow-100 text-yellow-800' :
                                                mission.statut === 'TERMINEE' ? 'bg-green-100 text-green-800' :
                                                'bg-red-100 text-red-800'
                                            }`}>
                                                {mission.statut}
                                            </span>
                                        </td>
                                        <td className="py-3 px-4 whitespace-nowrap text-sm font-medium">
                                            <button
                                                onClick={() => fetchMissionDetails(mission.id)}
                                                className="text-indigo-600 hover:text-indigo-900 mr-2"
                                            >
                                                Détails
                                            </button>
                                            <button
                                                onClick={() => fetchMissionAffectation(mission.id)}
                                                className="text-teal-600 hover:text-teal-900"
                                            >
                                                Affectation
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-gray-600">Aucune mission trouvée avec les critères actuels.</p>
                )}

                {/* Pagination */}
                {totalMissions > 0 && (
                    <div className="flex justify-between items-center mt-6">
                        <p className="text-sm text-gray-700">
                            Affichage de {((currentPage - 1) * missionsPerPage) + 1} à {Math.min(currentPage * missionsPerPage, totalMissions)} sur {totalMissions} missions
                        </p>
                        <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                            <button
                                onClick={() => handlePageChange(currentPage - 1)}
                                disabled={currentPage === 1}
                                className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                            >
                                Précédent
                            </button>
                            {[...Array(totalPages)].map((_, i) => (
                                <button
                                    key={i + 1}
                                    onClick={() => handlePageChange(i + 1)}
                                    className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                                        currentPage === i + 1
                                            ? 'z-10 bg-indigo-50 border-indigo-500 text-indigo-600'
                                            : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                                    }`}
                                >
                                    {i + 1}
                                </button>
                            ))}
                            <button
                                onClick={() => handlePageChange(currentPage + 1)}
                                disabled={currentPage === totalPages}
                                className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                            >
                                Suivant
                            </button>
                        </nav>
                    </div>
                )}
            </div>

            {/* Mission Detail Modal */}
            {selectedMission && (
                <div className="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center p-4 z-50">
                    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto relative">
                        <h2 className="text-2xl font-bold mb-4 text-gray-800">Détails de la Mission: {selectedMission.objet}</h2>
                        <button
                            onClick={() => setSelectedMission(null)}
                            className="absolute top-4 right-4 text-gray-500 hover:text-gray-700 text-2xl"
                        >
                            &times;
                        </button>
                        <div className="space-y-4">
                            <p><strong>ID:</strong> {selectedMission.id}</p>
                            <p><strong>Objet:</strong> {selectedMission.objet}</p>
                            <p><strong>Date Début:</strong> {moment(selectedMission.dateDebut).format('DD/MM/YYYY HH:mm')}</p>
                            <p><strong>Date Fin:</strong> {moment(selectedMission.dateFin).format('DD/MM/YYYY HH:mm')}</p>
                            <p><strong>Statut:</strong> {selectedMission.statut}</p>
                            <p><strong>Moyen de Transport:</strong> {selectedMission.moyenTransport || 'N/A'}</p>
                            <p><strong>Trajet Prédéfini:</strong> {selectedMission.trajet_predefini || 'N/A'}</p>
                            <p><strong>Créée le:</strong> {moment(selectedMission.created_at).format('DD/MM/YYYY HH:mm')}</p>
                            <p><strong>Mise à jour le:</strong> {moment(selectedMission.updated_at).format('DD/MM/YYYY HH:mm')}</p>

                            <h3 className="text-xl font-semibold mt-6 mb-2">Directeur</h3>
                            <p><strong>Nom:</strong> {selectedMission.directeur.nom} {selectedMission.directeur.prenom}</p>

                            {selectedMission.vehicule && (
                                <>
                                    <h3 className="text-xl font-semibold mt-6 mb-2">Véhicule</h3>
                                    <p><strong>Immatriculation:</strong> {selectedMission.vehicule.immatriculation}</p>
                                    <p><strong>Marque:</strong> {selectedMission.vehicule.marque}</p>
                                    <p><strong>Modèle:</strong> {selectedMission.vehicule.modele || 'N/A'}</p>
                                </>
                            )}

                            {selectedMission.affectation && (
                                <>
                                    <h3 className="text-xl font-semibold mt-6 mb-2">Affectation</h3>
                                    <p><strong>Déjeuner:</strong> {selectedMission.affectation.dejeuner}</p>
                                    <p><strong>Dîner:</strong> {selectedMission.affectation.dinner}</p>
                                    <p><strong>Accouchement:</strong> {selectedMission.affectation.accouchement}</p>
                                    <p><strong>Montant Calculé:</strong> {parseFloat(selectedMission.affectation.montantCalcule).toFixed(2)} DH</p>
                                    <p><strong>Créée le:</strong> {moment(selectedMission.affectation.created_at).format('DD/MM/YYYY HH:mm')}</p>
                                </>
                            )}

                            <h3 className="text-xl font-semibold mt-6 mb-2">Trajets ({selectedMission.trajets.length})</h3>
                            {selectedMission.trajets.length > 0 ? (
                                <ul className="list-disc pl-5 space-y-1">
                                    {selectedMission.trajets.map(trajet => (
                                        <li key={trajet.id}>
                                            {moment(trajet.timestamp).format('DD/MM/YYYY HH:mm:ss')} - Lat: {trajet.latitude}, Lng: {trajet.longitude}, Vitesse: {parseFloat(trajet.vitesse).toFixed(2)} km/h
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p>Aucun trajet enregistré.</p>
                            )}

                            <h3 className="text-xl font-semibold mt-6 mb-2">Anomalies ({selectedMission.anomalies.length})</h3>
                            {selectedMission.anomalies.length > 0 ? (
                                <ul className="list-disc pl-5 space-y-1">
                                    {selectedMission.anomalies.map(anomaly => (
                                        <li key={anomaly.id}>
                                            <strong>{anomaly.type}</strong>: {anomaly.description || 'N/A'} (Détectée le: {moment(anomaly.dateDetection).format('DD/MM/YYYY HH:mm')})
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p>Aucune anomalie détectée.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Affectation Detail Modal */}
            {selectedMissionAffectation && (
                <div className="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center p-4 z-50">
                    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-xl relative">
                        <h2 className="text-2xl font-bold mb-4 text-gray-800">Détails de l'Affectation</h2>
                        <button
                            onClick={() => setSelectedMissionAffectation(null)}
                            className="absolute top-4 right-4 text-gray-500 hover:text-gray-700 text-2xl"
                        >
                            &times;
                        </button>
                        <div className="space-y-4">
                            <p><strong>ID Affectation:</strong> {selectedMissionAffectation.id}</p>
                            <p><strong>Déjeuner:</strong> {selectedMissionAffectation.dejeuner}</p>
                            <p><strong>Dîner:</strong> {selectedMissionAffectation.dinner}</p>
                            <p><strong>Accouchement:</strong> {selectedMissionAffectation.accouchement}</p>
                            <p><strong>Montant Calculé:</strong> {parseFloat(selectedMissionAffectation.montantCalcule).toFixed(2)} DH</p>
                            <p><strong>Créée le:</strong> {moment(selectedMissionAffectation.created_at).format('DD/MM/YYYY HH:mm')}</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CollaborateurMissions;
