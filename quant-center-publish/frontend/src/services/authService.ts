import api from './api';

export const authService = {
  /**
   * Logs the user in using x-www-form-urlencoded credentials.
   * Maps to: POST /auth/login
   */
  login: async (username: string, password: string) => {
    // Backend requires application/x-www-form-urlencoded
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);

    const { data } = await api.post('/auth/login', params, {
      headers: { 
        'Content-Type': 'application/x-www-form-urlencoded' 
      },
    });
    
    // Store the actual Bearer token
    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token);
    }
    return data;
  },
  
  logout: () => {
    localStorage.removeItem('access_token');
  }
};