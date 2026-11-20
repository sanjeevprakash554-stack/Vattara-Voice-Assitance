import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [business, setBusiness] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('vattara_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      // If we have a stored token, authenticate with real backend profile
      if (token && token !== 'demo_token' && !token.startsWith('mock_jwt_token')) {
        try {
          const profile = await authService.getProfile();
          setUser(profile.user);
          setBusiness(profile.business);
        } catch (err) {
          console.warn('Stored token expired or invalid:', err);
          localStorage.removeItem('vattara_token');
          setToken(null);
          setUser(null);
          setBusiness(null);
        } finally {
          setLoading(false);
        }
        return;
      }

      // Check if explicit demo auto-login is enabled for dev sandbox
      const isAutoLoginEnabled = import.meta.env.VITE_ENABLE_AUTO_LOGIN === 'true';
      if (isAutoLoginEnabled) {
        try {
          const loginData = await authService.login({
            email: 'admin@vattara.com',
            password: 'Admin@123',
          });
          if (loginData?.access_token) {
            localStorage.setItem('vattara_token', loginData.access_token);
            setToken(loginData.access_token);
            setUser(loginData.user);
            setBusiness(loginData.business);
          }
        } catch (loginErr) {
          console.warn('Development auto-login unavailable:', loginErr);
        }
      }

      setLoading(false);
    }

    loadUser();
  }, []);

  const login = async (credentials) => {
    const data = await authService.login(credentials);
    localStorage.setItem('vattara_token', data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    setBusiness(data.business);
    return data;
  };

  const register = async (payload) => {
    const data = await authService.register(payload);
    localStorage.setItem('vattara_token', data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    setBusiness(data.business);
    return data;
  };

  const logout = () => {
    localStorage.removeItem('vattara_token');
    setToken(null);
    setUser(null);
    setBusiness(null);
  };

  const updateProfile = async (profileData) => {
    const res = await authService.updateProfile(profileData);
    if (res.user) setUser(res.user);
    if (res.business) setBusiness(res.business);
    return res;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        business,
        token,
        loading,
        login,
        register,
        logout,
        updateProfile,
        isAuthenticated: !!token && !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
