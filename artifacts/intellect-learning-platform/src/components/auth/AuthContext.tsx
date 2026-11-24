import { createContext, useContext, ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMe, logoutRequest, type User, type Role } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  /** Store the user returned by login / change-password. */
  setUser: (user: User) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);
const ME_KEY = ['auth', 'me'];

export function homePath(role: Role) {
  if (role === 'student') return '/learn';
  if (role === 'admin') return '/admin';
  return '/dashboard';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  // The session lives in an httpOnly cookie; the server is the source of truth.
  const { data: user = null, isLoading } = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 5 * 60_000 });

  const setUser = (next: User) => queryClient.setQueryData(ME_KEY, next);

  const logout = async () => {
    await logoutRequest().catch(() => undefined);
    queryClient.clear();
    queryClient.setQueryData(ME_KEY, null);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
