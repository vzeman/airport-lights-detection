import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private client: AxiosInstance;
  private refreshing: Promise<any> | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle token refresh and authentication errors
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // Handle authentication errors
        if (error.response?.status === 401 || 
            (error.response?.status === 422 && 
             error.response?.data?.detail === "Could not validate credentials")) {
          
          // Don't retry if already attempted or if it's a credential validation error
          if (originalRequest._retry || error.response?.data?.detail === "Could not validate credentials") {
            this.logout();
            window.location.href = '/login';
            return Promise.reject(error);
          }

          originalRequest._retry = true;

          if (!this.refreshing) {
            this.refreshing = this.refreshToken();
          }

          try {
            await this.refreshing;
            this.refreshing = null;
            return this.client(originalRequest);
          } catch (refreshError) {
            this.refreshing = null;
            this.logout();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  private async refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) throw new Error('No refresh token');

    const response = await axios.post(`${API_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });

    const { access_token, refresh_token: newRefreshToken } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', newRefreshToken);
    return response.data;
  }

  // Auth endpoints
  async login(username: string, password: string) {
    const response = await this.client.post('/auth/login', { username, password });
    const { access_token, refresh_token } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    return response.data;
  }

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  async changePassword(currentPassword: string, newPassword: string) {
    return this.client.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  // User management
  async getUsers(params?: any) {
    const response = await this.client.get('/users', { params });
    return response.data;
  }

  async getUser(id: string) {
    const response = await this.client.get(`/users/${id}`);
    return response.data;
  }

  async createUser(data: any) {
    const response = await this.client.post('/users', data);
    return response.data;
  }

  async updateUser(id: string, data: any) {
    const response = await this.client.patch(`/users/${id}`, data);
    return response.data;
  }

  async deleteUser(id: string) {
    return this.client.delete(`/users/${id}`);
  }

  async assignUserToAirport(userId: string, airportId: string) {
    return this.client.post(`/users/${userId}/assign-airport/${airportId}`);
  }

  async unassignUserFromAirport(userId: string, airportId: string) {
    return this.client.delete(`/users/${userId}/unassign-airport/${airportId}`);
  }

  // Airport management
  async getAirports(params?: any) {
    const response = await this.client.get('/airports', { params });
    return response.data;
  }

  async getAirport(id: string) {
    const response = await this.client.get(`/airports/${id}`);
    return response.data;
  }

  async createAirport(data: any) {
    const response = await this.client.post('/airports', data);
    return response.data;
  }

  async updateAirport(id: string, data: any) {
    const response = await this.client.patch(`/airports/${id}`, data);
    return response.data;
  }

  async deleteAirport(id: string) {
    return this.client.delete(`/airports/${id}`);
  }

  // Runway management
  async getAirportRunways(airportId: string) {
    const response = await this.client.get(`/airports/${airportId}/runways`);
    return response.data;
  }

  async createRunway(airportId: string, data: any) {
    const response = await this.client.post(`/airports/${airportId}/runways`, data);
    return response.data;
  }

  async updateRunway(airportId: string, runwayId: string, data: any) {
    const response = await this.client.put(`/airports/${airportId}/runways/${runwayId}`, data);
    return response.data;
  }

  async deleteRunway(airportId: string, runwayId: string) {
    return this.client.delete(`/airports/${airportId}/runways/${runwayId}`);
  }

  async getRunway(airportId: string, runwayId: string) {
    const response = await this.client.get(`/airports/${airportId}/runways/${runwayId}`);
    return response.data;
  }

  // Airport items
  async getAirportItems(airportId: string, params?: any) {
    const response = await this.client.get(`/airports/${airportId}/items`, { params });
    return response.data;
  }

  async createAirportItem(airportId: string, data: any) {
    const response = await this.client.post(`/airports/${airportId}/items`, data);
    return response.data;
  }

  async updateAirportItem(airportId: string, itemId: string, data: any) {
    const response = await this.client.patch(`/airports/${airportId}/items/${itemId}`, data);
    return response.data;
  }

  async deleteAirportItem(airportId: string, itemId: string) {
    return this.client.delete(`/airports/${airportId}/items/${itemId}`);
  }

  // Add get method for general API calls
  async get(url: string, config?: any) {
    const response = await this.client.get(url, config);
    return response;
  }

  async post(url: string, data?: any, config?: any) {
    const response = await this.client.post(url, data, config);
    return response;
  }

  // Reference Points API
  async getReferencePoints(runwayId: string) {
    const response = await this.client.get(`/runways/${runwayId}/reference-points`);
    return response.data;
  }

  async createReferencePoint(runwayId: string, data: any) {
    const response = await this.client.post(`/runways/${runwayId}/reference-points`, data);
    return response.data;
  }

  async updateReferencePoint(runwayId: string, pointId: string, data: any) {
    const response = await this.client.put(`/runways/${runwayId}/reference-points/${pointId}`, data);
    return response.data;
  }

  async deleteReferencePoint(runwayId: string, pointId: string) {
    return this.client.delete(`/runways/${runwayId}/reference-points/${pointId}`);
  }

  async bulkUpdateReferencePoints(runwayId: string, points: any[]) {
    const response = await this.client.post(`/runways/${runwayId}/reference-points/bulk`, points);
    return response.data;
  }

  // PAPI Measurement Sessions API
  async getPAPIMeasurementSessions(page: number = 1, pageSize: number = 20) {
    const response = await this.client.get(`/papi-measurements/sessions?page=${page}&page_size=${pageSize}`);
    return response.data;
  }
}

export const api = new ApiClient();
export default api;