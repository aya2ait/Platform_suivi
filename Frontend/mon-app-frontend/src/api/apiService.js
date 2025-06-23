// src/api/apiService.js

class ApiService {
  static baseURL = 'http://localhost:8000'; // Make sure this matches your backend URL

  static async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        // Attempt to parse error message from response body
        const contentType = response.headers.get("content-type");
        let errorData = { message: `HTTP error! Status: ${response.status}` };

        if (contentType && contentType.includes("application/json")) {
          try {
            errorData = await response.json();
          } catch (jsonError) {
            console.error("Error parsing error response JSON:", jsonError);
          }
        } else {
          try {
            const errorText = await response.text();
            errorData.message = errorText || response.statusText;
          } catch (textError) {
            console.error("Error reading error response text:", textError);
          }
        }
        // FastAPI 422 errors usually have 'detail' key with a list of errors
        const errorMessage = errorData.detail 
                               ? errorData.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ')
                               : errorData.message;
        throw new Error(errorMessage || `HTTP error! Status: ${response.status}`);
      }

      // If the response status is 204 (No Content), there will be no body to parse.
      // Also, check the Content-Type header. If it's not JSON, don't try to parse it.
      const contentType = response.headers.get("content-type");
      if (response.status === 204 || !(contentType && contentType.includes("application/json"))) {
        return null; // Return null for no content or non-JSON responses
      }

      // Otherwise, assume JSON and parse it
      return await response.json();

    } catch (error) {
      console.error('API Request failed:', error);
      throw error; // Re-throw to be caught by component-level error handling
    }
  }

  // Missions Endpoints
  static async getMissions(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return this.request(`/missions/${queryString ? `?${queryString}` : ''}`);
  }

  static async getMission(id) {
    return this.request(`/missions/${id}/`);
  }

  static async createMission(data) {
    return this.request('/missions/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateMission(id, data) {
    return this.request(`/missions/${id}/`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  static async deleteMission(id) {
    return this.request(`/missions/${id}/`, {
      method: 'DELETE',
    });
  }

  // --- New method for Collaborator Management ---
  static async manageMissionCollaborators(missionId, collaboratorsData) {
    // This endpoint should correspond to your backend's PATCH route
    // It expects a body like: { "collaborateurs": [{ matricule: "...", action: "...", ... }] }
    return this.request(`/missions/${missionId}/manage-collaborators`, {
      method: 'PATCH', // Use PATCH as indicated by your backend logs
      body: JSON.stringify(collaboratorsData), // collaboratorsData should already be in the correct { collaborateurs: [...] } format
    });
  }
  // ---------------------------------------------

  static async assignCollaborators(missionId, collaborators) {
    // This method might become redundant if `manageMissionCollaborators` handles all assignment/management
    return this.request(`/missions/${missionId}/assign_collaborators/`, {
      method: 'POST',
      body: JSON.stringify({ collaborateurs: collaborators }),
    });
  }

  static async getMissionCollaborators(missionId) {
    // This is useful for fetching the current list of collaborators for a mission
    return this.request(`/missions/${missionId}/collaborators/`);
  }

  // You would add more static methods here for other resources (collaborateurs, vehicules, etc.)
  static async getAllCollaborators() {
    // Assuming you have an endpoint to get all possible collaborators for selection
    return this.request('/collaborateurs/'); 
  }
}

export default ApiService;