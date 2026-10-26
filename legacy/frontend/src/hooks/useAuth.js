/**
 * hooks/useAuth.js
 * ----------------
 * React hook managing authentication state via localStorage.
 * Provides login, logout and current user to any component.
 */
import { useState, useCallback } from 'react';
import { authApi } from '../services/api';

export function useAuth() {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem('user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const login = useCallback(async (username, password) => {
    const data = await authApi.login(username, password);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  }, []);

  const isAuthenticated = !!user;

  return { user, isAuthenticated, login, logout };
}
