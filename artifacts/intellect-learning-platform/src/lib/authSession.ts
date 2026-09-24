import type { User } from './api/types';

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
};

const SESSION_KEY = 'intellect_auth_session';
const NOTICE_KEY = 'intellect_auth_notice';
export const AUTH_SESSION_ENDED_EVENT = 'intellect:auth-session-ended';
let memorySession: AuthSession | null | undefined;
let refreshPromise: Promise<AuthSession | null> | null = null;

export function getAuthSession(): AuthSession | null {
  if (memorySession !== undefined) return memorySession;
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return (memorySession = null);
  try {
    return (memorySession = JSON.parse(raw) as AuthSession);
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return (memorySession = null);
  }
}

export function setAuthSession(session: AuthSession | null) {
  memorySession = session;
  if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(SESSION_KEY);
}

export function endAuthSession(message: string) {
  setAuthSession(null);
  sessionStorage.setItem(NOTICE_KEY, message);
  window.dispatchEvent(new CustomEvent(AUTH_SESSION_ENDED_EVENT, { detail: message }));
}

export function takeAuthNotice(): string {
  const message = sessionStorage.getItem(NOTICE_KEY) || '';
  sessionStorage.removeItem(NOTICE_KEY);
  return message;
}

export async function refreshAuthSession(): Promise<AuthSession | null> {
  if (refreshPromise) return refreshPromise;
  const current = getAuthSession();
  if (!current?.refresh_token) return null;
  refreshPromise = fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: current.refresh_token }),
  }).then(async (response) => {
    if (!response.ok) {
      endAuthSession('Сессия истекла. Войдите снова.');
      return null;
    }
    const session = await response.json() as AuthSession;
    setAuthSession(session);
    return session;
  }).finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}
