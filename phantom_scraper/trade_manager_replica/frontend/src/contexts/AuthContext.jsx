/**
 * Authentication Context
 * Manages user authentication state
 */

import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  // BYPASS AUTH - Set authenticated immediately in initial state
  const [user, setUser] = useState({ username: 'demo', id: 1 });
  const [loading, setLoading] = useState(false);
  const [authenticated, setAuthenticated] = useState(true);

  useEffect(() => {
    // BYPASS AUTH - Ensure authenticated
    console.log('🔍 AuthContext: Bypassing auth check');
    setLoading(false);
    setAuthenticated(true);
    setUser({ username: 'demo', id: 1 });
    sessionStorage.setItem('auth_checked', 'true');
  }, []);

  const checkAuth = async () => {
    // BYPASS AUTH - Just set as authenticated
    setLoading(false);
    setAuthenticated(true);
    setUser({ username: 'demo', id: 1 });
  };

  const login = async (username, password, captchaToken = null) => {
    try {
      setLoading(true); // Set loading during login
      // For now, use a placeholder captcha token if not provided
      const captcha = captchaToken || 'test-captcha-token';
      const response = await authAPI.login(username, password, captcha);
      // API returns { user: {...} } directly (no success flag)
      if (response.data.user) {
        setUser(response.data.user);
        setAuthenticated(true);
        sessionStorage.setItem('auth_checked', 'true');
        setLoading(false); // Clear loading on success
        return { success: true };
      }
      setLoading(false); // Clear loading on failure
      return { success: false, error: response.data.error || 'Login failed' };
    } catch (error) {
      console.error('Login error:', error);
      setLoading(false); // Clear loading on error
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Login failed',
      };
    }
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setAuthenticated(false);
      sessionStorage.removeItem('auth_checked');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        authenticated,
        loading,
        login,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

