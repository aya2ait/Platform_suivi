// src/pages/DirecteursPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { axiosInstance, useAuth } from '../contexts/AuthContext';

const DirecteursPage = () => {
    const { hasPermission } = useAuth();
    const [directeurs, setDirecteurs] = useState([]);
    const [directions, setDirections] = useState([]);
    const [utilisateurs, setUtilisateurs] = useState([]); // Pour la liste des utilisateurs existants
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(1);
    const [size, setSize] = useState(10);
    const [totalItems, setTotalItems] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [filters, setFilters] = useState({ nom: '', prenom: '', direction_id: '' });
    const [showForm, setShowForm] = useState(false);
    const [editingDirecteur, setEditingDirecteur] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [createNewUser, setCreateNewUser] = useState(true); // Toggle pour créer un nouvel utilisateur ou utiliser un existant

    const [formData, setFormData] = useState({
        nom: '',
        prenom: '',
        direction_id: '',
        // Pour utiliser un utilisateur existant
        utilisateur_id: '',
        // Pour créer un nouvel utilisateur
        login: '',
        motDePasse: ''
    });

    // Charger la liste des directions
    const loadDirectionsList = useCallback(async () => {
        try {
            if (!hasPermission('direction:read')) {
                console.warn("Permission manquante pour charger la liste des directions (direction:read)");
                return;
            }
            const response = await axiosInstance.get('/admin/directions?skip=0&limit=1000');
            setDirections(response.data.items);
        } catch (err) {
            console.error("Erreur lors du chargement des directions pour le select:", err.response?.data || err.message);
        }
    }, [hasPermission]);

    // Charger la liste des utilisateurs existants
    const loadUtilisateursList = useCallback(async () => {
        try {
            if (!hasPermission('user:read')) {
                console.warn("Permission manquante pour charger la liste des utilisateurs (user:read)");
                return;
            }
            const response = await axiosInstance.get('/admin/users?skip=0&limit=1000');
            setUtilisateurs(response.data.items || response.data);
        } catch (err) {
            console.error("Erreur lors du chargement des utilisateurs:", err.response?.data || err.message);
        }
    }, [hasPermission]);

    const loadDirecteurs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            if (!hasPermission('directeur:read')) {
                throw new Error("Vous n'avez pas la permission de consulter les directeurs.");
            }

            const params = new URLSearchParams({
                skip: ((page - 1) * size).toString(),
                limit: size.toString(),
            });

            if (filters.nom) params.append('nom', filters.nom);
            if (filters.prenom) params.append('prenom', filters.prenom);
            if (filters.direction_id) params.append('direction_id', filters.direction_id);

            const response = await axiosInstance.get(`/admin/directeurs?${params.toString()}`);
            const data = response.data;
            setDirecteurs(data.items);
            setTotalItems(data.total);
            setTotalPages(data.pages);
        } catch (err) {
            console.error("Erreur lors du chargement des directeurs:", err.response?.data || err.message);
            setError(err.response?.data?.detail || err.message || 'Erreur lors du chargement des directeurs');
        } finally {
            setLoading(false);
        }
    }, [page, size, filters, hasPermission]);

    useEffect(() => {
        loadDirecteurs();
        loadDirectionsList();
        loadUtilisateursList();
    }, [loadDirecteurs, loadDirectionsList, loadUtilisateursList]);

    const handleFilterChange = (e) => {
        const { name, value } = e.target;
        setFilters(prevFilters => ({ ...prevFilters, [name]: value }));
    };

    const applyFilters = () => {
        setPage(1);
    };

    const handleFormChange = (e) => {
        const { name, value } = e.target;
        setFormData(prevData => ({ ...prevData, [name]: value }));
    };

    const handleFormSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSubmitting(true);
        try {
            let dataToSend = {};
            let endpoint = '';

            if (editingDirecteur) {
                // Mode modification
                if (!hasPermission('directeur:update')) {
                    throw new Error('Vous n\'avez pas la permission de modifier un directeur.');
                }
                dataToSend = {
                    nom: formData.nom,
                    prenom: formData.prenom,
                    direction_id: formData.direction_id ? parseInt(formData.direction_id) : null
                };
                endpoint = `/admin/directeurs/${editingDirecteur.id}`;
                await axiosInstance.put(endpoint, dataToSend);
                alert('Directeur mis à jour avec succès !');
            } else {
                // Mode création
                if (!hasPermission('directeur:create')) {
                    throw new Error('Vous n\'avez pas la permission de créer un directeur.');
                }

                if (createNewUser) {
                    // Créer un directeur avec un nouvel utilisateur
                    dataToSend = {
                        login: formData.login,
                        motDePasse: formData.motDePasse,
                        nom: formData.nom,
                        prenom: formData.prenom,
                        direction_id: formData.direction_id ? parseInt(formData.direction_id) : null
                    };
                    endpoint = '/admin/directeurs/with-user';
                } else {
                    // Créer un directeur avec un utilisateur existant
                    dataToSend = {
                        utilisateur_id: parseInt(formData.utilisateur_id),
                        nom: formData.nom,
                        prenom: formData.prenom,
                        direction_id: formData.direction_id ? parseInt(formData.direction_id) : null
                    };
                    endpoint = '/admin/directeurs';
                }

                await axiosInstance.post(endpoint, dataToSend);
                alert('Directeur créé avec succès !');
            }

            setShowForm(false);
            setEditingDirecteur(null);
            resetForm();
            loadDirecteurs();
        } catch (err) {
            console.error("Erreur soumission formulaire:", err.response?.data || err.message);
            setError(err.response?.data?.detail || err.message || 'Erreur lors de la soumission du formulaire.');
        } finally {
            setSubmitting(false);
        }
    };

    const resetForm = () => {
        setFormData({
            nom: '',
            prenom: '',
            direction_id: '',
            utilisateur_id: '',
            login: '',
            motDePasse: ''
        });
        setCreateNewUser(true);
    };

    const handleEditClick = (directeur) => {
        if (!hasPermission('directeur:update')) {
            alert('Vous n\'avez pas la permission de modifier un directeur.');
            return;
        }
        setEditingDirecteur(directeur);
        setFormData({
            nom: directeur.nom,
            prenom: directeur.prenom,
            direction_id: directeur.direction_id || '',
            utilisateur_id: '',
            login: '',
            motDePasse: ''
        });
        setShowForm(true);
    };

    const handleDelete = async (id) => {
        if (!hasPermission('directeur:delete')) {
            alert('Vous n\'avez pas la permission de supprimer un directeur.');
            return;
        }
        if (window.confirm('Êtes-vous sûr de vouloir supprimer ce directeur ?')) {
            setLoading(true);
            setError(null);
            try {
                await axiosInstance.delete(`/admin/directeurs/${id}`);
                alert('Directeur supprimé avec succès !');
                loadDirecteurs();
            } catch (err) {
                console.error("Erreur suppression directeur:", err.response?.data || err.message);
                setError(err.response?.data?.detail || err.message || 'Erreur lors de la suppression.');
            } finally {
                setLoading(false);
            }
        }
    };

    const handleCloseForm = () => {
        setShowForm(false);
        setEditingDirecteur(null);
        resetForm();
        setError(null);
    };

    if (error && error.includes("Vous n'avez pas la permission de consulter les directeurs.")) {
        return (
            <div className="text-center text-red-700 bg-red-100 border border-red-400 p-4 rounded-md mt-10 mx-auto max-w-lg">
                Vous n'êtes pas autorisé à consulter cette page.
            </div>
        );
    }

    return (
        <div className="container mx-auto p-6 bg-white shadow-lg rounded-lg">
            <h1 className="text-4xl font-bold text-gray-800 mb-8 text-center">Gestion des Directeurs</h1>

            {/* Error Display */}
            {error && (
                <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">
                    <strong>Erreur :</strong> {error}
                    <button 
                        onClick={() => setError(null)}
                        className="float-right text-red-800 hover:text-red-900"
                    >
                        ×
                    </button>
                </div>
            )}

            {/* Filtres */}
            <div className="mb-8 p-6 bg-gray-50 rounded-lg shadow-sm">
                <h2 className="text-2xl font-semibold text-gray-700 mb-4">Filtres de recherche</h2>
                <div className="flex flex-wrap items-center gap-4">
                    <input
                        type="text"
                        name="nom"
                        placeholder="Filtrer par nom"
                        value={filters.nom}
                        onChange={handleFilterChange}
                        className="p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 flex-grow"
                    />
                    <input
                        type="text"
                        name="prenom"
                        placeholder="Filtrer par prénom"
                        value={filters.prenom}
                        onChange={handleFilterChange}
                        className="p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 flex-grow"
                    />
                    <select
                        name="direction_id"
                        value={filters.direction_id}
                        onChange={handleFilterChange}
                        className="p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 w-40"
                    >
                        <option value="">Toutes les directions</option>
                        {directions.map(dir => (
                            <option key={dir.id} value={dir.id}>{dir.nom}</option>
                        ))}
                    </select>
                    <button 
                        onClick={applyFilters} 
                        disabled={loading}
                        className="bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-150 ease-in-out shadow-md disabled:opacity-50"
                    >
                        {loading ? 'Chargement...' : 'Appliquer'}
                    </button>
                </div>
            </div>

            {/* Formulaire */}
            <div className="mb-8 p-6 bg-gray-50 rounded-lg shadow-sm">
                {hasPermission('directeur:create') || hasPermission('directeur:update') ? (
                    <button
                        onClick={() => {
                            setShowForm(!showForm);
                            setEditingDirecteur(null);
                            resetForm();
                        }}
                        className="bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 transition duration-150 ease-in-out shadow-md"
                    >
                        {showForm ? 'Masquer le formulaire' : 'Ajouter / Modifier un directeur'}
                    </button>
                ) : (
                    <p className="text-gray-600">Vous n'avez pas les permissions pour ajouter ou modifier des directeurs.</p>
                )}

                {showForm && (
                    <div className="mt-6 p-6 border border-gray-200 rounded-lg bg-white shadow-md">
                        <h2 className="text-2xl font-semibold text-gray-700 mb-4">
                            {editingDirecteur ? 'Modifier le Directeur' : 'Ajouter un Nouveau Directeur'}
                        </h2>
                        
                        {/* Toggle pour créer un nouvel utilisateur ou utiliser un existant (seulement en mode création) */}
                        {!editingDirecteur && (
                            <div className="mb-4">
                                <label className="flex items-center space-x-2">
                                    <input
                                        type="radio"
                                        name="userType"
                                        checked={createNewUser}
                                        onChange={() => setCreateNewUser(true)}
                                        className="text-blue-600"
                                    />
                                    <span>Créer un nouvel utilisateur</span>
                                </label>
                                <label className="flex items-center space-x-2 mt-2">
                                    <input
                                        type="radio"
                                        name="userType"
                                        checked={!createNewUser}
                                        onChange={() => setCreateNewUser(false)}
                                        className="text-blue-600"
                                    />
                                    <span>Utiliser un utilisateur existant</span>
                                </label>
                            </div>
                        )}

                        <form onSubmit={handleFormSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label htmlFor="nom" className="block text-sm font-medium text-gray-700 mb-1">Nom:</label>
                                <input 
                                    type="text" 
                                    name="nom" 
                                    id="nom" 
                                    value={formData.nom} 
                                    onChange={handleFormChange} 
                                    required 
                                    disabled={submitting}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50" 
                                />
                            </div>
                            <div>
                                <label htmlFor="prenom" className="block text-sm font-medium text-gray-700 mb-1">Prénom:</label>
                                <input 
                                    type="text" 
                                    name="prenom" 
                                    id="prenom" 
                                    value={formData.prenom} 
                                    onChange={handleFormChange} 
                                    required 
                                    disabled={submitting}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50" 
                                />
                            </div>
                           
                            <div>
                                <label htmlFor="direction_id" className="block text-sm font-medium text-gray-700 mb-1">Direction:</label>
                                <select 
                                    name="direction_id" 
                                    id="direction_id" 
                                    value={formData.direction_id} 
                                    onChange={handleFormChange} 
                                    required 
                                    disabled={submitting}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                                >
                                    <option value="">Sélectionner une direction</option>
                                    {directions.map(dir => (
                                        <option key={dir.id} value={dir.id}>{dir.nom}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Champs spécifiques selon le mode */}
                            {!editingDirecteur && (
                                <>
                                    {createNewUser ? (
                                        // Champs pour créer un nouvel utilisateur
                                        <>
                                            <div>
                                                <label htmlFor="login" className="block text-sm font-medium text-gray-700 mb-1">Login:</label>
                                                <input 
                                                    type="text" 
                                                    name="login" 
                                                    id="login" 
                                                    value={formData.login} 
                                                    onChange={handleFormChange} 
                                                    required 
                                                    disabled={submitting}
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50" 
                                                />
                                            </div>
                                            <div>
                                                <label htmlFor="motDePasse" className="block text-sm font-medium text-gray-700 mb-1">Mot de passe:</label>
                                                <input 
                                                    type="password" 
                                                    name="motDePasse" 
                                                    id="motDePasse" 
                                                    value={formData.motDePasse} 
                                                    onChange={handleFormChange} 
                                                    required 
                                                    disabled={submitting}
                                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50" 
                                                />
                                            </div>
                                        </>
                                    ) : (
                                        // Champ pour sélectionner un utilisateur existant
                                        <div>
                                            <label htmlFor="utilisateur_id" className="block text-sm font-medium text-gray-700 mb-1">Utilisateur existant:</label>
                                            <select 
                                                name="utilisateur_id" 
                                                id="utilisateur_id" 
                                                value={formData.utilisateur_id} 
                                                onChange={handleFormChange} 
                                                required 
                                                disabled={submitting}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                                            >
                                                <option value="">Sélectionner un utilisateur</option>
                                                {utilisateurs.map(user => (
                                                    <option key={user.id} value={user.id}>
                                                        {user.login} ({user.nom} {user.prenom})
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    )}
                                </>
                            )}

                            <div className="col-span-1 md:col-span-2 flex justify-end space-x-3 mt-4">
                                <button 
                                    type="submit" 
                                    disabled={submitting}
                                    className="bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition duration-150 ease-in-out shadow-md disabled:opacity-50"
                                >
                                    {submitting ? 'Enregistrement...' : (editingDirecteur ? 'Mettre à jour' : 'Créer')}
                                </button>
                                <button 
                                    type="button" 
                                    onClick={handleCloseForm} 
                                    disabled={submitting}
                                    className="bg-gray-500 text-white py-2 px-4 rounded-md hover:bg-gray-600 transition duration-150 ease-in-out shadow-md disabled:opacity-50"
                                >
                                    Annuler
                                </button>
                            </div>
                        </form>
                    </div>
                )}
            </div>

            {/* Liste des directeurs */}
            <div className="mb-8 p-6 bg-gray-50 rounded-lg shadow-sm">
                <h2 className="text-2xl font-semibold text-gray-700 mb-4">Liste des Directeurs</h2>
                {loading ? (
                    <div className="text-center py-8">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                        <p className="text-gray-600">Chargement des directeurs...</p>
                    </div>
                ) : directeurs.length === 0 ? (
                    <p className="text-gray-600 text-center py-8">Aucun directeur trouvé.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-full bg-white rounded-lg shadow-md">
                            <thead className="bg-gray-200">
                                <tr>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">ID</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Nom</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Prénom</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Direction</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Login Utilisateur</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Rôle</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Nb Missions</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Date création</th>
                                    <th className="py-3 px-4 text-left text-sm font-semibold text-gray-700">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {directeurs.map((directeur) => (
                                    <tr key={directeur.id} className="border-t border-gray-200 hover:bg-gray-50 transition duration-150 ease-in-out">
                                        <td className="py-3 px-4">{directeur.id}</td>
                                        <td className="py-3 px-4">{directeur.nom}</td>
                                        <td className="py-3 px-4">{directeur.prenom}</td>
                                        <td className="py-3 px-4">{directeur.direction_nom || 'N/A'}</td>
                                        <td className="py-3 px-4">{directeur.utilisateur_login || 'N/A'}</td>
                                        <td className="py-3 px-4">
                                            <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                                                {directeur.utilisateur_role || 'N/A'}
                                            </span>
                                        </td>
                                        <td className="py-3 px-4">
                                            <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                                                {directeur.nombre_missions || 0}
                                            </span>
                                        </td>
                                        <td className="py-3 px-4">
                                            {directeur.created_at ? new Date(directeur.created_at).toLocaleDateString('fr-FR') : 'N/A'}
                                        </td>
                                        <td className="py-3 px-4 flex space-x-2">
                                            {hasPermission('directeur:update') && (
                                                <button 
                                                    onClick={() => handleEditClick(directeur)} 
                                                    disabled={loading}
                                                    className="bg-blue-500 text-white py-1 px-3 rounded-md text-sm hover:bg-blue-600 transition duration-150 ease-in-out disabled:opacity-50"
                                                >
                                                    Modifier
                                                </button>
                                            )}
                                            {hasPermission('directeur:delete') && (
                                                <button 
                                                    onClick={() => handleDelete(directeur.id)} 
                                                    disabled={loading}
                                                    className="bg-red-500 text-white py-1 px-3 rounded-md text-sm hover:bg-red-600 transition duration-150 ease-in-out disabled:opacity-50"
                                                >
                                                    Supprimer
                                                </button>
                                            )}
                                            {!(hasPermission('directeur:update') || hasPermission('directeur:delete')) && (
                                                <span className="text-gray-500 text-sm">Pas d'actions</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Pagination */}
            <div className="flex justify-center items-center space-x-4 mt-8">
                <button
                    onClick={() => setPage(prev => Math.max(prev - 1, 1))}
                    disabled={page === 1 || loading}
                    className="bg-gray-300 text-gray-800 py-2 px-4 rounded-md hover:bg-gray-400 transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Précédent
                </button>
                <span className="text-lg font-semibold text-gray-700">
                    Page {page} sur {totalPages} ({totalItems} éléments)
                </span>
                <button
                    onClick={() => setPage(prev => Math.min(prev + 1, totalPages))}
                    disabled={page === totalPages || loading}
                    className="bg-gray-300 text-gray-800 py-2 px-4 rounded-md hover:bg-gray-400 transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Suivant
                </button>
            </div>
        </div>
    );
};

export default DirecteursPage;