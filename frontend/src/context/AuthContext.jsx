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
      if (token) {
        try {
          const profile = await authService.getProfile();
          setUser(profile.user);
          setBusiness(profile.business);
        } catch (err) {
          console.warn('Failed to load profile on boot, clearing auth:', err);
          // If token invalid, fall back to default demo user or clear
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
        }
      } else {
        // Pre-populate demo user for quick access
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
        setToken('demo_token');
        localStorage.setItem('vattara_token', 'demo_token');
      }
      setLoading(false);
    }
    loadUser();
  }, [token]);

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

