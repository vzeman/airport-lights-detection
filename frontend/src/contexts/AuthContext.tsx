import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import api from '../services/api';

interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
  is_superuser: boolean;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isSuperAdmin: boolean;
  isAirportAdmin: boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (token) {
        const userData = await api.getCurrentUser();
        setUser(userData);
      }
    } catch (error) {
      api.logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (username: string, password: string) => {
    await api.login(username, password);
    const userData = await api.getCurrentUser();
    setUser(userData);
  };

  const logout = () => {
    api.logout();
    setUser(null);
    window.location.href = '/login';
  };

  const hasRole = (role: string) => {
    return user?.role === role || user?.is_superuser === true;
  };

  const value: AuthContextType = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
    isSuperAdmin: user?.is_superuser === true,
    isAirportAdmin: hasRole('airport_admin'),
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};