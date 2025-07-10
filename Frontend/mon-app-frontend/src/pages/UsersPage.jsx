// src/pages/UsersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { axiosInstance, useAuth } from '../contexts/AuthContext';
import '../styles/professionalStyles.css'; // Import the shared professional styles

const UsersPage = () => {
    const { hasPermission } = useAuth();
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(1);
    const [size, setSize] = useState(10);
    const [totalItems, setTotalItems] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [filters, setFilters] = useState({ login: '', role: '' });
    const [showForm, setShowForm] = useState(false);
    const [editingUser, setEditingUser] = useState(null);

    const [formData, setFormData] = useState({
        login: '',
        motDePasse: '',
        role: ''
    });

    const loadUsers = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            if (!hasPermission('user:read')) {
                throw new Error("Vous n'avez pas la permission de consulter les utilisateurs.");
            }

            const params = new URLSearchParams({
                page: page.toString(),
                size: size.toString(),
            });

            if (filters.login) params.append('login', filters.login);
            if (filters.role) params.append('role', filters.role);

            const response = await axiosInstance.get(`/admin/users?${params.toString()}`);
            const data = response.data;
            setUsers(data.items);
            setTotalItems(data.total);
            setTotalPages(data.pages);
        } catch (err) {
            console.error("Erreur lors du chargement des utilisateurs:", err.response?.data || err.message);
            setError(err.response?.data?.detail || err.message || 'Erreur lors du chargement des utilisateurs');
        } finally {
            setLoading(false);
        }
    }, [page, size, filters, hasPermission]);

    useEffect(() => {
        loadUsers();
    }, [loadUsers]);

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
        setLoading(true);
        try {
            if (editingUser) {
                if (!hasPermission('user:update')) {
                    throw new Error('Vous n\'avez pas la permission de modifier un utilisateur.');
                }
                const dataToUpdate = { login: formData.login, role: formData.role };
                if (formData.motDePasse) {
                    dataToUpdate.motDePasse = formData.motDePasse;
                }

                await axiosInstance.put(`/admin/users/${editingUser.id}`, dataToUpdate);
                alert('Utilisateur mis à jour avec succès !');
            } else {
                if (!hasPermission('user:create')) {
                    throw new Error('Vous n\'avez pas la permission de créer un utilisateur.');
                }
                await axiosInstance.post('/admin/users', formData);
                alert('Utilisateur créé avec succès !');
            }
            setShowForm(false);
            setEditingUser(null);
            setFormData({ login: '', motDePasse: '', role: '' });
            loadUsers();
        } catch (err) {
            console.error("Erreur soumission formulaire:", err.response?.data || err.message);

            let errorMessage = 'Erreur lors de la soumission du formulaire.';

            if (err.response?.data) {
                if (typeof err.response.data === 'string') {
                    errorMessage = err.response.data;
                } else if (err.response.data.detail) {
                    if (typeof err.response.data.detail === 'string') {
                        errorMessage = err.response.data.detail;
                    } else if (Array.isArray(err.response.data.detail)) {
                        errorMessage = err.response.data.detail.map(error =>
                            typeof error === 'string' ? error : error.msg || JSON.stringify(error)
                        ).join(', ');
                    } else {
                        errorMessage = err.response.data.detail.msg || JSON.stringify(err.response.data.detail);
                    }
                } else if (err.response.data.message) {
                    errorMessage = err.response.data.message;
                }
            } else if (err.message) {
                errorMessage = err.message;
            }

            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    const handleEditClick = (user) => {
        if (!hasPermission('user:update')) {
            alert('Vous n\'avez pas la permission de modifier un utilisateur.');
            return;
        }
        setEditingUser(user);
        setFormData({ login: user.login, motDePasse: '', role: user.role });
        setShowForm(true);
    };

    const handleDelete = async (id) => {
        if (!hasPermission('user:delete')) {
            alert('Vous n\'avez pas la permission de supprimer un utilisateur.');
            return;
        }
        if (window.confirm('Êtes-vous sûr de vouloir supprimer cet utilisateur ? Cette action est irréversible.')) {
            setLoading(true);
            setError(null);
            try {
                await axiosInstance.delete(`/admin/users/${id}`);
                alert('Utilisateur supprimé avec succès !');
                loadUsers();
            } catch (err) {
                console.error("Erreur suppression utilisateur:", err.response?.data || err.message);
                setError(err.response?.data?.detail || err.message || 'Erreur lors de la suppression.');
            } finally {
                setLoading(false);
            }
        }
    };

    // Affiche un message d'erreur spécifique si la permission de lecture est manquante
    if (error && error.includes("Vous n'avez pas la permission de consulter les utilisateurs.")) {
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
                <p className="text-xl font-semibold text-blue-600">Chargement des utilisateurs...</p>
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
        <div className="min-h-screen-bg p-8 font-sans">
            <div className="container-max-w-7xl">
                <h1 className="title-main">
                    Gestion des Utilisateurs <span className="text-secondary text-4xl">👥</span>
                </h1>

                {/* Section Filtres */}
                <div className="mb-10 card-panel">
                    <h2 className="title-section">Filtres de Recherche</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end">
                        <div>
                            <label htmlFor="filterLogin" className="block text-sm font-semibold mb-2 text-text">Login</label>
                            <input
                                type="text"
                                name="login"
                                id="filterLogin"
                                placeholder="Filtrer par login..."
                                value={filters.login}
                                onChange={handleFilterChange}
                            />
                        </div>
                        <div>
                            <label htmlFor="filterRole" className="block text-sm font-semibold mb-2 text-text">Rôle</label>
                            <select
                                name="role"
                                id="filterRole"
                                value={filters.role}
                                onChange={handleFilterChange}
                            >
                                <option value="">Tous les rôles</option>
                                <option value="admin">ADMIN</option>
                                <option value="directeur">DIRECTEUR</option>
                                <option value="controleur">CONTROLEUR</option>
                                <option value="collaborateur">COLLABORATEUR</option>
                            </select>
                        </div>
                        <div className="flex items-end">
                            <button onClick={applyFilters} className="btn btn-primary w-full">
                                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                                Appliquer les filtres
                            </button>
                        </div>
                    </div>
                </div>

                {/* Section Formulaire de création/modification */}
                <div className="mb-10 card-panel">
                    {hasPermission('user:create') || hasPermission('user:update') ? (
                        <button
                            onClick={() => {
                                setShowForm(!showForm);
                                setEditingUser(null);
                                setFormData({ login: '', motDePasse: '', role: '' });
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
                                    Ajouter / Modifier un utilisateur
                                </>
                            )}
                        </button>
                    ) : (
                        <p className="text-muted text-center text-lg py-4">Vous n'avez pas les permissions nécessaires pour gérer les utilisateurs.</p>
                    )}

                    {showForm && (
                        <div className="mt-6 card-panel">
                            <h2 className="title-section">{editingUser ? 'Modifier l\'Utilisateur' : 'Ajouter un Nouvel Utilisateur'}</h2>
                            <form onSubmit={handleFormSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label htmlFor="login" className="block text-sm font-semibold mb-2 text-text">Login:</label>
                                    <input type="text" name="login" id="login" value={formData.login} onChange={handleFormChange} required />
                                </div>
                                <div>
                                    <label htmlFor="motDePasse" className="block text-sm font-semibold mb-2 text-text">Mot de passe:</label>
                                    <input type="password" name="motDePasse" id="motDePasse" value={formData.motDePasse} onChange={handleFormChange} required={!editingUser} />
                                    {editingUser && <p className="text-xs text-muted mt-1">Laissez vide pour ne pas changer le mot de passe.</p>}
                                </div>
                                <div>
                                    <label htmlFor="role" className="block text-sm font-semibold mb-2 text-text">Rôle:</label>
                                    <select name="role" id="role" value={formData.role} onChange={handleFormChange} required>
                                        <option value="">Sélectionner un rôle</option>
                                        <option value="admin">ADMIN</option>
                                        <option value="directeur">DIRECTEUR</option>
                                        <option value="controleur">CONTROLEUR</option>
                                        <option value="collaborateur">COLLABORATEUR</option>
                                    </select>
                                </div>

                                <div className="col-span-1 md:col-span-2 flex justify-end space-x-4 mt-4">
                                    <button type="submit" className="btn btn-primary" disabled={loading}>
                                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                        {editingUser ? 'Mettre à jour' : 'Créer'}
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

                {/* Section Tableau des utilisateurs */}
                <div className="mb-10 card-panel">
                    <h2 className="title-section">Liste des Utilisateurs</h2>
                    {users.length === 0 ? (
                        <p className="text-muted text-center py-8 text-lg">Aucun utilisateur trouvé avec les filtres actuels.</p>
                    ) : (
                        <div className="overflow-x-auto border border-accent rounded-lg shadow-sm">
                            <table className="min-w-full bg-surface">
                                <thead className="table-header">
                                    <tr>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">ID</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Login</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Rôle</th>
                                        <th className="py-4 px-6 text-left text-sm font-semibold">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map((user, index) => (
                                        <tr key={user.id} className={`border-b border-accent table-row ${index % 2 === 0 ? 'table-row-even' : 'table-row-odd'}`}>
                                            <td className="py-3 px-6 text-text">{user.id}</td>
                                            <td className="py-3 px-6 text-text font-medium">{user.login}</td>
                                            <td className="py-3 px-6 text-text">{user.role}</td>
                                            <td className="py-3 px-6 flex flex-wrap gap-2">
                                                {hasPermission('user:update') && (
                                                    <button onClick={() => handleEditClick(user)} className="btn btn-primary text-sm py-2 px-4">
                                                        Modifier
                                                    </button>
                                                )}
                                                {hasPermission('user:delete') && (
                                                    <button onClick={() => handleDelete(user.id)} className="btn btn-danger text-sm py-2 px-4">
                                                        Supprimer
                                                    </button>
                                                )}
                                                {!(hasPermission('user:update') || hasPermission('user:delete')) && (
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

export default UsersPage;