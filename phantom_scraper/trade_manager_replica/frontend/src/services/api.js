/**
 * API Service for Just.Trades
 * Handles all backend API calls
 */

import axios from 'axios';

// Always use /api when built (served from same origin as Flask)
// Only use full URL in dev mode with Vite dev server
// Check if we're in production by checking window location
const getAPIBaseURL = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // Always use relative /api in production builds
  return '/api';
};

const API_BASE_URL = getAPIBaseURL();

// Debug logging
if (typeof window !== 'undefined') {
  console.log('API Configuration:', {
    PROD: import.meta.env.PROD,
    MODE: import.meta.env.MODE,
    API_BASE_URL
  });
}

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add CSRF token
api.interceptors.request.use(
  async (config) => {
    // Skip CSRF for login endpoint (no session yet)
    if (config.url?.includes('/auth/login/')) {
      return config;
    }
    
    // Get CSRF token from session or fetch it
    let csrfToken = sessionStorage.getItem('csrf_token');
    if (!csrfToken) {
      // Fetch CSRF token (but don't block request)
      try {
        const csrfUrl = API_BASE_URL.startsWith('http') 
          ? `${API_BASE_URL}/system/csrf-token`
          : `${API_BASE_URL}/system/csrf-token`;
        const response = await axios.get(csrfUrl, { withCredentials: true });
        csrfToken = response.data.csrfToken || response.data.csrf_token;
        if (csrfToken) {
          sessionStorage.setItem('csrf_token', csrfToken);
        }
      } catch (error) {
        console.error('Failed to fetch CSRF token:', error);
        // Don't block the request if CSRF fails
      }
    }
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Unauthorized - only redirect if not already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth endpoints
export const authAPI = {
  checkAuth: () => api.get('/auth/check-auth/'),
  login: (username, password, captchaToken) => api.post('/auth/login/', { 
    username, 
    password, 
    captchaToken 
  }),
  logout: () => api.post('/auth/logout/'),
};

// Accounts endpoints
export const accountsAPI = {
  getAll: () => api.get('/accounts/'),
  addTradovate: (data) => api.post('/accounts/add-tradovate/', data),
  testConnection: (data) => api.post('/accounts/test-tradovate-connection/', data),
  update: (id, data) => api.put(`/accounts/${id}/`, data),
  delete: (id) => api.delete(`/accounts/${id}/`),
  refreshSubaccounts: (id) => api.post(`/accounts/${id}/refresh/`),
};

// Strategies endpoints
export const strategiesAPI = {
  getAll: (params = {}) => api.get('/strategies/', { params }),
  getByVal: (val) => api.get('/strategies/', { params: { val } }),
  getByStyle: (style) => api.get('/strategies/', { params: { style } }),
  getManual: () => api.get('/strategies/', { params: { manual: 'true' } }),
  getStrategy: (id) => api.get('/strategies/get-strat/', { params: { id } }),
  create: (data) => api.post('/strategies/create/', data),
  update: (data) => api.post('/strategies/update/', data),  // Partial update
  updateFull: (id, data) => api.put(`/strategies/${id}/`, data),  // Full update
  delete: (id) => api.delete(`/strategies/${id}/`),
};

// Recorder endpoints
export const recorderAPI = {
  start: (strategyId) => api.post(`/recorder/start/${strategyId}/`),
  stop: (strategyId) => api.post(`/recorder/stop/${strategyId}/`),
  getPositions: (strategyId) => api.get(`/recorder/positions/${strategyId}/`),
};

// Dashboard endpoints
export const dashboardAPI = {
  getSummary: () => api.get('/dashboard/summary/'),
  getAnalytics: (params = {}) => api.get('/dashboard/analytics/', { params }),
};

// Trades endpoints
export const tradesAPI = {
  getAll: (params = {}) => api.get('/trades/', { params }),
  getOpen: (params = {}) => api.get('/trades/open/', { params }),
  getTickers: (strat = '') => api.get('/trades/tickers/', { params: { strat } }),
  getTimeframes: (strat = '') => api.get('/trades/timeframes/', { params: { strat } }),
  execute: (data) => api.post('/trades/execute/', data),
};

// Profiles endpoints
export const profilesAPI = {
  getLimits: () => api.get('/profiles/get-limits/'),
  getStatConfig: () => api.get('/profiles/get-stat-config'),  // No trailing slash
  updateStatConfig: (data) => api.post('/profiles/update-stat-config/', data),
  getFavorites: () => api.get('/profiles/get-favorites'),  // No trailing slash
  setFavorites: (data) => api.post('/profiles/set-favorites/', data),
  getWidgetInfo: (params = {}) => api.get('/profiles/get-widget-info/', { params }),
  getDetails: () => api.get('/profiles/details/'),
  updateUsername: (data) => api.post('/profiles/update-username/', data),
  changePassword: (data) => api.post('/profiles/change-password/', data),
  togglePushNotification: () => api.post('/profiles/toggle-push-notification/'),
  toggleDiscordDM: () => api.post('/profiles/toggle-discord-dm/'),
};

// Discord endpoints
export const discordAPI = {
  connect: () => api.get('/discord/oauth/connect/'),
};

// System endpoints
export const systemAPI = {
  getCSRFToken: () => api.get('/system/csrf-token'),  // No trailing slash
};

export default api;

