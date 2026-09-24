import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { changePassword as changePasswordRequest, getCurrentUser, loginWithPassword, logoutSession } from '@/lib/api';
import { AUTH_SESSION_ENDED_EVENT, getAuthSession, refreshAuthSession, setAuthSession } from '@/lib/authSession';
import type { User } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (login: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  changePassword: (password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(getAuthSession()?.user || null);
  const [isLoading, setIsLoading] = useState(Boolean(getAuthSession()));

  useEffect(() => {
    if (!getAuthSession()) {
      setIsLoading(false);
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(async () => {
        const session = await refreshAuthSession();
        setUser(session?.user || null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    const sessionEnded = () => {
      setUser(null);
      setIsLoading(false);
    };
    window.addEventListener(AUTH_SESSION_ENDED_EVENT, sessionEnded);
    return () => window.removeEventListener(AUTH_SESSION_ENDED_EVENT, sessionEnded);
  }, []);

  const login = async (loginName: string, password: string) => {
    const session = await loginWithPassword(loginName, password);
    setAuthSession(session);
    setUser(session.user);
    return session.user;
  };

  const logout = async () => {
    try {
      await logoutSession();
    } finally {
      setAuthSession(null);
      setUser(null);
    }
  };

  const changePassword = async (password: string) => {
    await changePasswordRequest(password);
    const updated = user ? { ...user, must_change_password: false } : null;
    setUser(updated);
    const session = getAuthSession();
    if (session && updated) setAuthSession({ ...session, user: updated });
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
