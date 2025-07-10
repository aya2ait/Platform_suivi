// src/pages/DirectionsPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { axiosInstance, useAuth } from '../contexts/AuthContext'; // Importez axiosInstance et useAuth
import '../styles/professionalStyles.css'; // <--- NOUVELLE IMPORTATION ICI

const DirectionsPage = () => {
    const { hasPermission } = useAuth();
    const [directions, setDirections] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(1);
    const [size, setSize] = useState(10);
    const [totalItems, setTotalItems] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [filters, setFilters] = useState({ nom: '', annee: '', mois: '' });
    const [showForm, setShowForm] = useState(false);
    const [editingDirection, setEditingDirection] = useState(null);
    const [selectedDirections, setSelectedDirections] = useState([]);

    const [formData, setFormData] = useState({
        nom: '',
        montantInitial: '',
        montantConsomme: '',
        mois: '',
        annee: ''
    });

    const loadDirections = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            if (!hasPermission('direction:read')) {
                setError("Vous n'avez pas la permission de consulter les directions.");
                setLoading(false);
                return;
            }

            const params = new URLSearchParams({
                skip: ((page - 1) * size).toString(),
                limit: size.toString(),
            });

            if (filters.nom) params.append('nom', filters.nom);
            if (filters.annee && !isNaN(parseInt(filters.annee))) params.append('annee', parseInt(filters.annee).toString());
            if (filters.mois && !isNaN(parseInt(filters.mois))) params.append('mois', parseInt(filters.mois).toString());

            const response = await axiosInstance.get(`/admin/directions?${params.toString()}`);
            const data = response.data;
            setDirections(data.items);
            setTotalItems(data.total);
            setTotalPages(data.pages);
        } catch (err) {
            console.error("Erreur lors du chargement des directions:", err.response?.data || err.message);
            setError(err.response?.data?.detail || err.message || 'Erreur lors du chargement des directions');
        } finally {
            setLoading(false);
        }
    }, [page, size, filters, hasPermission]);

    useEffect(() => {
        loadDirections();
    }, [loadDirections]);

    const handleFilterChange = (e) => {
        const { name, value } = e.target;
        setFilters(prevFilters => ({
            ...prevFilters,
            [name]: value
        }));
    };

    const applyFilters = () => {
        setPage(1);
    };

    const handleFormChange = (e) => {
        const { name, value } = e.target;
        setFormData(prevData => ({
            ...prevData,
            [name]: value
        }));
    };

    const handleFormSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            const dataToSend = {
                ...formData,
                montantInitial: parseFloat(formData.montantInitial),
                montantConsomme: parseFloat(formData.montantConsomme),
                mois: parseInt(formData.mois),
                annee: parseInt(formData.annee)
            };

            if (editingDirection) {
                if (!hasPermission('direction:update')) {
                    throw new Error('Vous n\'avez pas la permission de modifier une direction.');
                }
                await axiosInstance.put(`/admin/directions/${editingDirection.id}`, dataToSend);
                alert('Direction mise à jour avec succès !');
            } else {
                if (!hasPermission('direction:create')) {
                    throw new Error('Vous n\'avez pas la permission de créer une direction.');
                }
                await axiosInstance.post('/admin/directions', dataToSend);
                alert('Direction créée avec succès !');
            }
            setShowForm(false);
            setEditingDirection(null);
            setFormData({ nom: '', montantInitial: '', montantConsomme: '', mois: '', annee: '' });
            loadDirections();
        } catch (err) {
            console.error("Erreur soumission formulaire:", err.response?.data || err.message);
            setError(err.response?.data?.detail || err.message || 'Erreur lors de la soumission du formulaire.');
        } finally {
            setLoading(false);
        }
    };

    const handleEditClick = (direction) => {
        if (!hasPermission('direction:update')) {
            alert('Vous n\'avez pas la permission de modifier une direction.');
            return;
        }
        setEditingDirection(direction);
        setFormData({
            nom: direction.nom,
            montantInitial: direction.montantInitial.toString(),
            montantConsomme: direction.montantConsomme.toString(),
            mois: direction.mois.toString(),
            annee: direction.annee.toString()
        });
        setShowForm(true);
    };

    const handleDelete = async (id) => {
        if (!hasPermission('direction:delete')) {
            alert('Vous n\'avez pas la permission de supprimer une direction.');
            return;
        }

        if (window.confirm('Êtes-vous sûr de vouloir supprimer cette direction ? Cette action est irréversible.')) {
            setLoading(true);
            setError(null);
            try {
                await axiosInstance.delete(`/admin/directions/${id}`);
                alert('Direction supprimée avec succès !');
                loadDirections();
            } catch (err) {
                console.error("Erreur suppression direction:", err.response?.data || err.message);
                setError(err.response?.data?.detail || err.message || 'Erreur lors de la suppression.');
            } finally {
                setLoading(false);
            }
        }
    };

    const handleSelectDirection = (id) => {
        setSelectedDirections(prevSelected =>
            prevSelected.includes(id)
                ? prevSelected.filter(itemId => itemId !== id)
                : [...prevSelected, id]
        );
    };

    const handleSelectAll = (e) => {
        if (e.target.checked) {
            setSelectedDirections(directions.map(d => d.id));
        } else {
            setSelectedDirections([]);
        }
    };

    const handleBulkDelete = async () => {
        if (!hasPermission('direction:delete')) {
            alert('Vous n\'avez pas la permission de supprimer plusieurs directions.');
            return;
        }

        if (selectedDirections.length === 0) {
            alert('Veuillez sélectionner au moins une direction à supprimer.');
            return;
        }
        if (window.confirm(`Êtes-vous sûr de vouloir supprimer les ${selectedDirections.length} directions sélectionnées ? Cette action est irréversible.`)) {
            setLoading(true);
            setError(null);
            try {
                const response = await axiosInstance.post('/admin/directions/bulk_delete', { ids: selectedDirections });
                const result = response.data;
                alert(`${result.deleted_count} directions supprimées. ${result.failed_ids.length > 0 ? `Échec pour les IDs : ${result.failed_ids.join(', ')}` : ''}`);
                setSelectedDirections([]);
                loadDirections();
            } catch (err) {
                console.error("Erreur suppression en masse:", err.response?.data || err.message);
                setError(err.response?.data?.detail || err.message || 'Erreur lors de la suppression en masse.');
            } finally {
                setLoading(false);
            }
        }
    };

    // Affiche un message d'erreur spécifique si la permission de lecture est manquante
    if (error && error.includes("Vous n'avez pas la permission de consulter les directions.")) {
        return (
            <div className="min-h-screen flex items-center justify-center p-6 font-sans bg-gray-50">
                <div className="text-center p-8 rounded-lg shadow-xl bg-white border border-gray-200">
                    <p className="text-xl font-semibold mb-4 text-red-600">Accès Refusé</p>
                    <p className="text-lg text-gray-700">Vous n'êtes pas autorisé à consulter cette page.</p>
                </div>
            </div>
        );
    }

    if (loading) return (
        <div className="min-h-screen flex items-center justify-center p-6 font-sans bg-gray-50">
            <div className="flex flex-col items-center p-8 rounded-lg shadow-xl bg-white border border-gray-200">
                <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-blue-600 mb-4"></div>
                <p className="text-xl font-semibold text-blue-600">Chargement des directions...</p>
            </div>
        </div>
    );

    if (error) return (
        <div className="min-h-screen flex items-center justify-center p-6 font-sans bg-gray-50">
            <div className="text-center p-8 rounded-lg shadow-xl bg-white border border-gray-200">
                <p className="text-xl font-semibold mb-4 text-red-600">Erreur!</p>
                <p className="text-lg text-gray-700">Une erreur est survenue: {error}</p>
            </div>
        </div>
    );

    return (
        <div className="min-h-screen-bg p-8 font-sans"> {/* Utilisation de la classe pour le fond */}
            <div className="container-max-w-7xl"> {/* Utilisation de la classe pour le container */}
                <h1 className="title-main"> {/* Utilisation des classes pour le titre */}
                    Gestion des Directions <span className="text-secondary text-4xl">💧</span>
                </h1>

                {/* Section Filtres */}
                <div className="mb-10 card-panel">
                    <h2 className="title-section">Filtres de Recherche</h2> {/* Utilisation de la classe pour le titre de section */}
                    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6 items-end">
                        <div>
                            <label htmlFor="filterNom" className="block text-sm font-semibold mb-2 text-text">Nom de la Direction</label>
                            <input
                                type="text"
                                name="nom"
                                id="filterNom"
                                placeholder="Rechercher par nom..."
                                value={filters.nom}
                                onChange={handleFilterChange}
                            />
                        </div>
                        <div>
                            <label htmlFor="filterAnnee" className="block text-sm font-semibold mb-2 text-text">Année</label>
                            <input
                                type="number"
                                name="annee"
                                id="filterAnnee"
                                placeholder="Ex: 2024"
                                value={filters.annee}
                                onChange={handleFilterChange}
                                min="2020" max="2030"
                            />
                        </div>
                        <div>
                            <label htmlFor="filterMois" className="block text-sm font-semibold mb-2 text-text">Mois (1-12)</label>
                            <input
                                type="number"
                                name="mois"
                                id="filterMois"
                                placeholder="Ex: 7"
                                value={filters.mois}
                                onChange={handleFilterChange}
                                min="1" max="12"
                            />
                        </div>
                        <div className="md:col-span-1 lg:col-span-1 flex items-end">
                            <button onClick={applyFilters} className="btn btn-primary w-full">
                                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                                Appliquer les filtres
                            </button>
                        </div>
                    </div>
                </div>

                {/* Section Formulaire de création/modification */}
                <div className="mb-10 card-panel">
                    {hasPermission('direction:create') || hasPermission('direction:update') ? (
                        <button
                            onClick={() => {
                                setShowForm(!showForm);
                                setEditingDirection(null);
                                setFormData({ nom: '', montantInitial: '', montantConsomme: '', mois: '', annee: '' });
                            }}
                            className={`btn ${showForm ? 'btn-danger' : 'btn-success'} mb-6`}
                        >
                            {showForm ? (
                                <>
                                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                    Masquer le formulaire
                                </>
                            ) : (
                                <>
                                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                                    Ajouter / Modifier une direction
                                </>
                            )}
                        </button>
                    ) : (
                        <p className="text-muted text-center text-lg py-4">Vous n'avez pas les permissions nécessaires pour gérer les directions.</p>
                    )}

                    {showForm && (
                        <div className="mt-6 card-panel">
                            <h2 className="title-section">{editingDirection ? 'Modifier la Direction' : 'Ajouter une Nouvelle Direction'}</h2>
                            <form onSubmit={handleFormSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label htmlFor="formNom" className="block text-sm font-semibold mb-2 text-text">Nom:</label>
                                    <input type="text" name="nom" id="formNom" value={formData.nom} onChange={handleFormChange} required />
                                </div>
                                <div>
                                    <label htmlFor="montantInitial" className="block text-sm font-semibold mb-2 text-text">Montant Initial:</label>
                                    <input type="number" name="montantInitial" id="montantInitial" value={formData.montantInitial} onChange={handleFormChange} required step="0.01" />
                                </div>
                                <div>
                                    <label htmlFor="montantConsomme" className="block text-sm font-semibold mb-2 text-text">Montant Consommé:</label>
                                    <input type="number" name="montantConsomme" id="montantConsomme" value={formData.montantConsomme} onChange={handleFormChange} required step="0.01" />
                                </div>
                                <div>
                                    <label htmlFor="mois" className="block text-sm font-semibold mb-2 text-text">Mois (1-12):</label>
                                    <input type="number" name="mois" id="mois" value={formData.mois} onChange={handleFormChange} required min="1" max="12" />
                                </div>
                                <div>
                                    <label htmlFor="annee" className="block text-sm font-semibold mb-2 text-text">Année:</label>
                                    <input type="number" name="annee" id="annee" value={formData.annee} onChange={handleFormChange} required min="2020" max="2030" />
                                </div>
                                <div className="col-span-1 md:col-span-2 flex justify-end space-x-4 mt-4">
                                    <button type="submit" className="btn btn-primary" disabled={loading}>
                                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                        {editingDirection ? 'Mettre à jour' : 'Créer'}
                                    </button>
                                    <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary" disabled={loading}>
                                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                        Annuler
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}
                </div>

                {/* Section Tableau des directions */}
                <div className="mb-10 card-panel">
                    <h2 className="title-section">Liste des Directions</h2>

                    {hasPermission('direction:delete') && directions.length > 0 && (
                        <button
                            onClick={handleBulkDelete}
                            disabled={selectedDirections.length === 0 || loading}
                            className="btn btn-danger mb-6"
                        >
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            Supprimer la sélection ({selectedDirections.length})
                        </button>
                    )}

                    {directions.length === 0 ? (
                        <p className="text-muted text-center py-8 text-lg">Aucune direction trouvée avec les filtres actuels.</p>
                    ) : (
                        <div className="overflow-x-auto border border-accent rounded-lg shadow-sm">
                            <table className="min-w-full bg-surface">
                                <thead className="table-header">
                                    <tr>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">
                                            <input
                                                type="checkbox"
                                                onChange={handleSelectAll}
                                                checked={selectedDirections.length === directions.length && directions.length > 0}
                                                className="form-checkbox h-5 w-5"
                                            />
                                        </th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">ID</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Nom</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Montant Initial</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Montant Consommé</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Mois</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Année</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Budget Restant</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Directeurs</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Collaborateurs</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Missions</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {directions.map((direction, index) => (
                                        <tr key={direction.id} className={`border-b border-accent table-row ${index % 2 === 0 ? 'table-row-even' : 'table-row-odd'}`}>
                                            <td className="py-3 px-6">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedDirections.includes(direction.id)}
                                                    onChange={() => handleSelectDirection(direction.id)}
                                                    className="form-checkbox h-5 w-5"
                                                />
                                            </td>
                                            <td className="py-3 px-6 text-text">{direction.id}</td>
                                            <td className="py-3 px-6 text-text font-medium">{direction.nom}</td>
                                            <td className="py-3 px-6 text-text">{parseFloat(direction.montantInitial).toFixed(2)} DH</td>
                                            <td className="py-3 px-6 text-text">{parseFloat(direction.montantConsomme).toFixed(2)} DH</td>
                                            <td className="py-3 px-6 text-text">{direction.mois}</td>
                                            <td className="py-3 px-6 text-text">{direction.annee}</td>
                                            <td className="py-3 px-6 font-semibold" style={{ color: direction.budget_restant < 0 ? 'var(--color-danger)' : 'var(--color-success)' }}>
                                                {parseFloat(direction.budget_restant).toFixed(2)} DH
                                            </td>
                                            <td className="py-3 px-6 text-text">{direction.nombre_directeurs}</td>
                                            <td className="py-3 px-6 text-text">{direction.nombre_collaborateurs}</td>
                                            <td className="py-3 px-6 text-text">{direction.nombre_missions}</td>
                                            <td className="py-3 px-6 flex flex-wrap gap-2">
                                                {hasPermission('direction:update') && (
                                                    <button onClick={() => handleEditClick(direction)} className="btn btn-primary text-sm py-2 px-4">
                                                        Modifier
                                                    </button>
                                                )}
                                                {hasPermission('direction:delete') && (
                                                    <button onClick={() => handleDelete(direction.id)} className="btn btn-danger text-sm py-2 px-4">
                                                        Supprimer
                                                    </button>
                                                )}
                                                {!(hasPermission('direction:update') || hasPermission('direction:delete')) && (
                                                    <span className="text-muted text-sm italic py-2 px-4">Pas d'actions</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Section Pagination */}
                {totalPages > 1 && (
                    <div className="flex justify-center items-center space-x-6 mt-8 card-panel">
                        <button
                            onClick={() => setPage(prev => Math.max(prev - 1, 1))}
                            disabled={page === 1 || loading}
                            className="btn btn-secondary"
                        >
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path></svg>
                            Précédent
                        </button>
                        <span className="text-xl font-bold text-text">
                            Page {page} sur {totalPages} <span className="text-muted">({totalItems} éléments)</span>
                        </span>
                        <button
                            onClick={() => setPage(prev => Math.min(prev + 1, totalPages))}
                            disabled={page === totalPages || loading}
                            className="btn btn-secondary"
                        >
                            Suivant
                            <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path></svg>
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DirectionsPage;