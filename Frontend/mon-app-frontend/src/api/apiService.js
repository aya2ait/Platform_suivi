// src/api/apiService.js
import { axiosInstance } from '../contexts/AuthContext';

class ApiService {
  static baseURL = 'http://localhost:8000';

  // Enhanced request method with better error handling and debugging
  static async request(endpoint, options = {}) {
    try {
      // Add timeout configuration
      const config = {
        url: endpoint,
        method: options.method || 'GET',
        timeout: 30000, // 30 seconds timeout
        ...options,
      };

      // If there's a body, add it to the config
      if (options.body) {
        config.data = JSON.parse(options.body);
        delete config.body;
      }

      console.log('Making API request:', {
        url: config.url,
        method: config.method,
        data: config.data
      });

      const response = await axiosInstance(config);
      console.log('API response received:', response.status);
      return response.data;

    } catch (error) {
      console.error('API Request failed:', {
        endpoint,
        error: error.message,
        code: error.code,
        status: error.response?.status,
        data: error.response?.data
      });
      
      // Handle axios error format
      if (error.response) {
        // Server responded with error status
        const errorData = error.response.data;
        let errorMessage = `HTTP error! Status: ${error.response.status}`;

        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ');
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          } else if (typeof errorData.detail === 'object') {
            // Handle conflict errors with detailed information
            if (errorData.detail.message && errorData.detail.conflicts) {
              errorMessage = `${errorData.detail.message}: ${errorData.detail.conflicts.join(', ')}`;
            } else {
              errorMessage = JSON.stringify(errorData.detail);
            }
          }
        } else if (errorData.message) {
          errorMessage = errorData.message;
        }

        // Special handling for authentication errors
        if (error.response.status === 401) {
          throw new Error('Session expired. Please log in again.');
        }
        if (error.response.status === 403) {
          throw new Error('Access forbidden - insufficient permissions');
        }

        throw new Error(errorMessage);
      } else if (error.request) {
        // Request was made but no response received
        console.error('No response received:', error.request);
        
        // Check for specific error codes
        if (error.code === 'ECONNABORTED') {
          throw new Error('Request timeout - server took too long to respond');
        } else if (error.code === 'ECONNREFUSED') {
          throw new Error('Connection refused - make sure the server is running on http://localhost:8000');
        } else if (error.code === 'ENOTFOUND') {
          throw new Error('Server not found - check your network connection');
        } else {
          throw new Error(`No response received from server. Please check if the server is running and accessible at ${this.baseURL}`);
        }
      } else {
        // Request setup error
        throw new Error(error.message || 'Request setup error');
      }
    }
  }

  // Missions Endpoints
  static async getMissions(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/missions${queryString ? `?${queryString}` : ''}`);
  }

  static async getMission(id) {
    return this.request(`/missions/${id}`);
  }

  static async createMission(data) {
    return this.request('/missions/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateMission(id, data) {
    return this.request(`/missions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  static async deleteMission(id) {
    return this.request(`/missions/${id}`, {
      method: 'DELETE',
    });
  }

  // Collaborator Management - Fixed endpoints
  static async manageMissionCollaborators(missionId, collaboratorsData) {
    return this.request(`/missions/${missionId}/manage-collaborators`, {
      method: 'PATCH',
      body: JSON.stringify(collaboratorsData),
    });
  }

  static async assignCollaborators(missionId, collaborators) {
    return this.request(`/missions/${missionId}/assign_collaborators/`, {
      method: 'POST',
      body: JSON.stringify({ collaborateurs: collaborators }),
    });
  }

  // Fixed: Remove trailing slash for consistency
  static async getMissionCollaborators(missionId) {
    return this.request(`/missions/${missionId}/collaborators`);
  }

  static async getAllCollaborators() {
    return this.request('/collaborateurs/');
  }

  // Additional methods
  static async getCollaborator(matricule) {
    return this.request(`/collaborateurs/${matricule}/`);
  }

  static async createCollaborator(data) {
    return this.request('/collaborateurs/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateCollaborator(matricule, data) {
    return this.request(`/collaborateurs/${matricule}/`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  static async deleteCollaborator(matricule) {
    return this.request(`/collaborateurs/${matricule}/`, {
      method: 'DELETE',
    });
  }

  // Mission parameters
  static async getMissionParameters() {
    return this.request('/parametres/');
  }

  static async updateMissionParameters(data) {
    return this.request('/parametres/', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // Reports and statistics
  static async getMissionReport(missionId) {
    return this.request(`/missions/${missionId}/report/`);
  }

  static async getMissionsStatistics(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/missions/statistics${queryString ? `?${queryString}` : ''}`);
  }

  // Download reports
  static async downloadMissionReport(missionId, format = 'pdf') {
    const response = await axiosInstance({
      url: `/missions/${missionId}/download/?format=${format}`,
      method: 'GET',
      responseType: 'blob',
      timeout: 60000, // Longer timeout for downloads
    });
    return response.data;
  }

  // Health check method to verify server connectivity
  static async healthCheck() {
    try {
      await axiosInstance.get('/health', { timeout: 5000 });
      return true;
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }
}

export default ApiService;