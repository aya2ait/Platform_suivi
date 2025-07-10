// src/contexts/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// Configuration de l'API
const API_BASE_URL = 'http://127.0.0.1:8000';

// Contexte d'authentification
const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Instance Axios configurée avec Interceptors
export const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor pour ajouter le token d'accès aux requêtes
axiosInstance.interceptors.request.use(
  (config) => {
    const accessToken = sessionStorage.getItem('access_token');
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor pour gérer le rafraîchissement du token sur les erreurs 401
axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }

        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, { 
          refresh_token: refreshToken 
        });
        const { access_token, refresh_token: newRefreshToken } = response.data;

        sessionStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', newRefreshToken);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return axiosInstance(originalRequest);
      } catch (refreshError) {
        console.error("Erreur lors du rafraîchissement du token:", refreshError);
        localStorage.clear();
        sessionStorage.clear();
        window.location.reload();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Fournisseur d'authentification
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [authReady, setAuthReady] = useState(false);

  // Fonction pour mettre à jour l'état d'authentification
  const updateAuthState = useCallback((userInfo, authenticated) => {
    console.log('Updating auth state:', { userInfo, authenticated });
    setUser(userInfo);
    setIsAuthenticated(authenticated);
    setAuthReady(true);
    setLoading(false);
  }, []);

  // Fonction de connexion
  const login = useCallback(async (username, password) => {
    try {
      setLoading(true);
      setAuthReady(false);
      
      const response = await axiosInstance.post('/auth/login', { username, password });
      const { access_token, refresh_token, user_info } = response.data;
      
      console.log('Login successful:', user_info);
      
      // Stocker les tokens
      sessionStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      
      // Récupérer les permissions
      try {
        const permissionsResponse = await axiosInstance.get('/auth/permissions');
        const userPermissions = permissionsResponse.data.permissions;
        
        const fullUserInfo = { ...user_info, permissions: userPermissions };
        console.log('User with permissions:', fullUserInfo);
        
        updateAuthState(fullUserInfo, true);
        return true;
      } catch (permError) {
        console.error('Erreur lors de la récupération des permissions:', permError);
        const userWithoutPerms = { ...user_info, permissions: [] };
        
        updateAuthState(userWithoutPerms, true);
        return true;
      }
    } catch (error) {
      console.error('Erreur de connexion:', error.response?.data || error.message);
      sessionStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      updateAuthState(null, false);
      return false;
    }
  }, [updateAuthState]);

  // Fonction de déconnexion
  const logout = useCallback(async () => {
    try {
      await axiosInstance.post('/auth/logout');
    } catch (error) {
      console.error('Erreur lors de la déconnexion côté API:', error);
    } finally {
      localStorage.clear();
      sessionStorage.clear();
      updateAuthState(null, false);
    }
  }, [updateAuthState]);

  // Vérifier les permissions
  const hasPermission = useCallback((permission) => {
    if (!user || !user.permissions) {
      console.log(`Permission check failed: user=${!!user}, permissions=${user?.permissions?.length || 0}`);
      return false;
    }
    const hasAccess = user.permissions.includes(permission);
    console.log(`Permission check for ${permission}: ${hasAccess}`);
    return hasAccess;
  }, [user]);

  // Fonction pour rafraîchir le token d'accès
  const refreshAccessToken = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      console.log('No refresh token available');
      return false;
    }
    
    try {
      const response = await axios.post(`${API_BASE_URL}/auth/refresh`, { 
        refresh_token: refreshToken 
      });
      const { access_token, refresh_token: newRefreshToken, user_info } = response.data;
      
      sessionStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', newRefreshToken);
      
      try {
        const permissionsResponse = await axiosInstance.get('/auth/permissions');
        const userPermissions = permissionsResponse.data.permissions;
        const fullUserInfo = { ...user_info, permissions: userPermissions };

        updateAuthState(fullUserInfo, true);
        return true;
      } catch (permError) {
        console.error("Erreur lors de la récupération des permissions:", permError);
        const userWithoutPerms = { ...user_info, permissions: [] };
        updateAuthState(userWithoutPerms, true);
        return true;
      }
    } catch (error) {
      console.error("Échec du rafraîchissement du token:", error);
      localStorage.clear();
      sessionStorage.clear();
      updateAuthState(null, false);
      return false;
    }
  }, [updateAuthState]);

  // Vérification de l'authentification au chargement
  useEffect(() => {
    const checkAuth = async () => {
      console.log('Checking authentication...');
      const accessToken = sessionStorage.getItem('access_token');
      const refreshToken = localStorage.getItem('refresh_token');

      if (!accessToken && !refreshToken) {
        console.log('No tokens found');
        updateAuthState(null, false);
        return;
      }

      if (accessToken) {
        try {
          // Valider le token actuel
          console.log('Validating current token...');
          const validateResponse = await axiosInstance.get('/auth/validate-token');
          const { valid } = validateResponse.data;

          if (valid) {
            console.log('Token is valid, fetching user info...');
            const userInfoResponse = await axiosInstance.get('/auth/me');
            const permissionsResponse = await axiosInstance.get('/auth/permissions');
            
            const fullUserInfo = {
              ...userInfoResponse.data,
              permissions: permissionsResponse.data.permissions,
            };
            
            console.log('Auth check successful:', fullUserInfo);
            updateAuthState(fullUserInfo, true);
            return;
          } else {
            console.log('Token is invalid, attempting refresh...');
            throw new Error('Token invalide');
          }
        } catch (error) {
          console.error('Token validation failed:', error);
          if (refreshToken) {
            console.log('Attempting token refresh...');
            const success = await refreshAccessToken();
            if (!success) {
              console.log('Token refresh failed, logging out...');
              await logout();
            }
          } else {
            console.log('No refresh token, logging out...');
            await logout();
          }
        }
      } else if (refreshToken) {
        console.log('No access token but refresh token exists, refreshing...');
        const success = await refreshAccessToken();
        if (!success) {
          console.log('Refresh failed, logging out...');
          await logout();
        }
      }
    };

    checkAuth();
  }, [refreshAccessToken, logout, updateAuthState]);

  const authContextValue = {
    user,
    isAuthenticated,
    loading,
    authReady,
    login,
    logout,
    hasPermission,
    refreshAccessToken,
    axiosInstance,
  };

  console.log('AuthProvider render:', {
    user: !!user,
    isAuthenticated,
    loading,
    authReady,
    permissions: user?.permissions?.length || 0
  });

  return (
    <AuthContext.Provider value={authContextValue}>
      {children}
    </AuthContext.Provider>
  );
};