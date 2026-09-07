"use client";

import { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { apiGet, apiPost } from '../utils/api';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize from session check on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (response.ok) {
          const data = await response.json();
          if (data && data.user) {
            setUser(data.user);
          }
        } else {
          console.log('No active session found.');
        }
      } catch (err) {
        console.log('Session check failed:', err);
      } finally {
        setLoading(false);
      }
    };
    checkSession();
  }, []);

  const login = useCallback((token, userData = null) => {
    setUser(userData);
    setError(null);
    return true;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiPost('/api/auth/signout');
    } catch (err) {
      console.error('Signout request failed:', err);
    }
    setUser(null);
  }, []);

  const signup = useCallback((token, userData) => {
    return login(null, userData);
  }, [login]);

  const value = {
    user,
    loading,
    error,
    login,
    logout,
    signup,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
