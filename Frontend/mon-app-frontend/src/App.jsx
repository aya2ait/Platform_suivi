// src/App.jsx - Version debug corrigée
import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Header from './components/common/Header';
import MissionsList from './components/missions/MissionsList';
import DirectionsPage from './pages/DirectionsPage';
import UsersPage from './pages/UsersPage';
import DirecteursPage from './pages/DirecteursPage';
import MoroccoInteractiveMap from './components/carte/carte';
import CollaborateurMissions from './components/collaborateurs/CollaborateurMissions'; // Import the new component

// Placeholders pour d'autres onglets
import CollaborateursTab from './components/placeholders/CollaborateursTab'; // Keep if still needed for other purposes, otherwise remove
import VehiculesTab from './components/placeholders/VehiculesTab';
import RapportsTab from './components/placeholders/RapportsTab';
import Login from './components/auth/Login';

// --- Composant pour les routes protégées ---
const ProtectedRoute = ({ children, requiredPermissions = [] }) => {
    const { isAuthenticated, authReady, hasPermission, loading } = useAuth();

    // Afficher un loading pendant que l'authentification se charge
    if (loading || !authReady) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-100">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p className="text-gray-700 text-lg">Chargement de l'application...</p>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Login />;
    }

    if (requiredPermissions.length > 0) {
        const userHasAllPermissions = requiredPermissions.every(permission => hasPermission(permission));
        if (!userHasAllPermissions) {
            return (
                <div className="min-h-screen flex items-center justify-center bg-red-50">
                    <div className="text-center p-8 bg-white rounded-lg shadow-md">
                        <div className="text-red-600 text-6xl mb-4">🚫</div>
                        <h2 className="text-2xl font-bold text-red-800 mb-2">Accès refusé</h2>
                        <p className="text-red-600">Vous n'avez pas les permissions nécessaires pour accéder à cette section.</p>
                    </div>
                </div>
            );
        }
    }

    return children;
};

// --- Composant Dashboard principal ---
const Dashboard = () => {
    const { hasPermission, user, authReady } = useAuth();
    const [activeTab, setActiveTab] = useState(null);

    console.log('=== DASHBOARD RENDER ===');
    console.log('User:', user);
    console.log('AuthReady:', authReady);
    console.log('Active tab:', activeTab);

    // Définir les onglets disponibles
    const getAvailableTabs = () => {
        if (!authReady || !user) {
            console.log('Auth not ready or no user, returning empty tabs');
            return [];
        }

        const tabs = [];

        const permissions = [
            { permission: 'mission:read', tab: { id: 'missions', name: 'Missions' } },
            { permission: 'direction:read', tab: { id: 'directions', name: 'Directions' } },
            { permission: 'user:read', tab: { id: 'users', name: 'Utilisateurs' } },
            { permission: 'directeur:read', tab: { id: 'directeurs', name: 'Directeurs' } },
            { permission: 'collab:mission:read', tab: { id: 'collaborateurs', name: 'Collaborateurs' } }, // This tab will now render CollaborateurMissions
            { permission: 'vehicule:read', tab: { id: 'vehicules', name: 'Véhicules' } },
            { permission: 'rapports:read', tab: { id: 'rapports', name: 'Rapports' } },
            { permission: 'carte:read', tab: { id: 'carte', name: 'carte' } },

        ];

        permissions.forEach(({ permission, tab }) => {
            const hasAccess = hasPermission(permission);
            console.log(`Permission ${permission}: ${hasAccess ? '✅' : '❌'}`);
            if (hasAccess) {
                tabs.push(tab);
            }
        });

        console.log('Available tabs:', tabs);
        return tabs;
    };

    const availableTabs = getAvailableTabs();

    // Handler pour les clics d'onglets
    const handleTabChange = (tabId) => {
        console.log('=== TAB CHANGE HANDLER ===');
        console.log('Changing to tab:', tabId);
        console.log('Available tabs:', availableTabs.map(t => t.id));

        if (availableTabs.some(tab => tab.id === tabId)) {
            setActiveTab(tabId);
            console.log('✅ Tab changed successfully to:', tabId);
        } else {
            console.log('❌ Tab not found in available tabs:', tabId);
        }
    };

    // Initialiser l'onglet actif
    useEffect(() => {
        console.log('=== ACTIVE TAB EFFECT ===');
        console.log('AuthReady:', authReady);
        console.log('Available tabs:', availableTabs.length);
        console.log('Current active tab:', activeTab);

        if (!authReady || availableTabs.length === 0) {
            console.log('Not ready or no tabs available');
            return;
        }

        // Si pas d'onglet actif ou si l'onglet actif n'est plus disponible
        if (!activeTab || !availableTabs.some(tab => tab.id === activeTab)) {
            const firstTab = availableTabs[0];
            console.log('Setting first available tab:', firstTab.id);
            setActiveTab(firstTab.id);
        }
    }, [authReady, availableTabs, activeTab]);

    // Rendu du contenu
    const renderContent = () => {


        if (!authReady) {
            return (
                <div className="flex items-center justify-center h-64">
                    <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                        <p className="text-gray-600">Initialisation...</p>
                    </div>
                </div>
            );
        }

        if (!activeTab || availableTabs.length === 0) {
            return (
                <div className="text-center py-12">
                    <div className="bg-yellow-50 rounded-lg p-8 max-w-md mx-auto">
                        <div className="text-yellow-600 text-5xl mb-4">⚠️</div>
                        <h3 className="text-lg font-semibold text-yellow-800 mb-2">
                            Aucun accès disponible
                        </h3>
                        <p className="text-yellow-700 text-sm">
                            Vous n'avez pas les permissions pour accéder aux sections du tableau de bord.
                        </p>
                        <div className="mt-4 text-xs text-left bg-white p-3 rounded border">
                            <strong>Informations de debug :</strong><br/>
                            Utilisateur : {user?.nom} ({user?.role})<br/>
                            Permissions : {user?.permissions?.join(', ') || 'Aucune'}<br/>
                            Onglets disponibles : {availableTabs.length}
                        </div>
                    </div>
                </div>
            );
        }

        // Rendu basé sur l'onglet actif
        switch (activeTab) {
            case 'missions':
                return <MissionsList />;
            case 'directions':
                return <DirectionsPage />;
            case 'users':
                return <UsersPage />;
            case 'directeurs':
                return <DirecteursPage />;
            case 'collaborateurs':
                return <CollaborateurMissions />; {/* Changed from CollaborateursTab */}
            case 'vehicules':
                return <VehiculesTab />;
            case 'rapports':
                return <RapportsTab />;
            case 'carte':
                return <MoroccoInteractiveMap />;

            default:
                return (
                    <div className="text-center py-12">
                        <div className="bg-red-50 rounded-lg p-8 max-w-md mx-auto">
                            <div className="text-red-600 text-5xl mb-4">❌</div>
                            <h3 className="text-lg font-semibold text-red-800 mb-2">
                                Onglet inconnu
                            </h3>
                            <p className="text-red-700 text-sm">
                                L'onglet "{activeTab}" n'existe pas.
                            </p>
                        </div>
                    </div>
                );
        }
    };

    // Ne pas rendre si l'auth n'est pas prête
    if (!authReady) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p className="text-gray-700 text-lg">Chargement du tableau de bord...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">


            <Header
                activeTab={activeTab}
                setActiveTab={handleTabChange}
                availableTabs={availableTabs}
            />

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-grow w-full">
                {renderContent()}
            </main>
        </div>
    );
};

// --- Composant Router simple ---
const AppRouter = () => {
    const [currentPath, setCurrentPath] = useState(window.location.pathname);
    const { isAuthenticated, authReady } = useAuth();

    useEffect(() => {
        const handlePopState = () => setCurrentPath(window.location.pathname);
        window.addEventListener('popstate', handlePopState);
        return () => window.removeEventListener('popstate', handlePopState);
    }, []);

    useEffect(() => {
        if (!authReady) return;

        if (isAuthenticated && currentPath === '/login') {
            window.history.replaceState({}, '', '/');
            setCurrentPath('/');
        } else if (!isAuthenticated && currentPath !== '/login') {
            window.history.replaceState({}, '', '/login');
            setCurrentPath('/login');
            // No need to reload, the Login component will handle authentication
        }
    }, [isAuthenticated, currentPath, authReady]);

    if (currentPath === '/login') {
        return <Login />;
    }

    return (
        <ProtectedRoute>
            <Dashboard />
        </ProtectedRoute>
    );
};

// --- App principal avec Provider ---
const App = () => {
    return (
        <AuthProvider>
            <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet" />
            <style>
                {`
                    body {
                        font-family: "Inter", sans-serif;
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }
                `}
            </style>
            <AppRouter />
        </AuthProvider>
    );
};

export default App;
