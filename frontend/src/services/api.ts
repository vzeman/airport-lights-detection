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

    // Response interceptor to handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
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
}

export const api = new ApiClient();
export default api;