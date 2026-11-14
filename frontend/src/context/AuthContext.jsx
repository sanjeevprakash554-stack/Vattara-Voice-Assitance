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
      // 1. If we have a stored token, try loading the real user profile
      if (token && token !== 'demo_token' && !token.startsWith('mock_jwt_token')) {
        try {
          const profile = await authService.getProfile();
          setUser(profile.user);
          setBusiness(profile.business);
          setLoading(false);
          return;
        } catch (err) {
          console.warn('Stored token expired or invalid, attempting automatic demo re-authentication:', err);
        }
      }

      // 2. Automatically obtain a genuine JWT token from live backend with demo credentials
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
          setLoading(false);
          return;
        }
      } catch (loginErr) {
        console.warn('Backend auto-login failed, falling back to mock client state:', loginErr);
      }

      // 3. Fallback mock user if backend is unreachable
      const fallbackUser = {
        id: 'demo-user-1',
        email: 'admin@vattara.com',
        full_name: 'Dr. Rajesh Kumar',
        role: 'admin',
      };
      const fallbackBiz = {
        id: 'demo-biz-1',
        name: 'Vattara City Clinic & Diagnostics',
        vertical: 'clinic',
        phone: '+91 44 2828 9000',
      };
      setUser(fallbackUser);
      setBusiness(fallbackBiz);
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
        isAuthenticated: !!user,
        login,
        register,
        logout,
        updateProfile,
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

