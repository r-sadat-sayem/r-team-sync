import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../services/api';
import type { AuthUser } from '../types';

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (displayName: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const currentUser = await api.getCurrentUser();
        if (!cancelled) {
          setUser(currentUser);
          api.setStorageNamespace(`user:${currentUser.id}`);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          api.setStorageNamespace(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email: string, password: string) => {
    const currentUser = await api.login(email, password);
    setUser(currentUser);
    api.setStorageNamespace(`user:${currentUser.id}`);
  };

  const signup = async (displayName: string, email: string, password: string) => {
    const currentUser = await api.signup(displayName, email, password);
    setUser(currentUser);
    api.setStorageNamespace(`user:${currentUser.id}`);
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      api.setStorageNamespace(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
