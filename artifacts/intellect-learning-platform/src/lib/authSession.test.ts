import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AUTH_SESSION_ENDED_EVENT,
  endAuthSession,
  getAuthSession,
  setAuthSession,
  takeAuthNotice,
  type AuthSession,
} from './authSession';

const session: AuthSession = {
  access_token: 'access',
  refresh_token: 'refresh',
  expires_in: 3600,
  user: {
    id: 1,
    profile_id: 1,
    name: 'Student',
    login_name: 'student.7a',
    role: 'student',
    grade: 7,
    must_change_password: false,
  },
};

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => { values.delete(key); },
    setItem: (key, value) => { values.set(key, String(value)); },
  };
}

describe('auth session lifecycle', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage());
    vi.stubGlobal('sessionStorage', memoryStorage());
    vi.stubGlobal('window', new EventTarget());
    localStorage.clear();
    sessionStorage.clear();
    setAuthSession(null);
  });

  it('clears credentials, publishes an event and preserves a one-time notice', () => {
    setAuthSession(session);
    const listener = vi.fn();
    window.addEventListener(AUTH_SESSION_ENDED_EVENT, listener);

    endAuthSession('Аккаунт заблокирован.');

    expect(getAuthSession()).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    expect(takeAuthNotice()).toBe('Аккаунт заблокирован.');
    expect(takeAuthNotice()).toBe('');
    window.removeEventListener(AUTH_SESSION_ENDED_EVENT, listener);
  });
});
