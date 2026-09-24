import { beforeEach, describe, expect, it, vi } from 'vitest';

import { setAuthSession, takeAuthNotice, type AuthSession } from '../authSession';
import { parseKtpFile } from './ktp';
import {
  ApiError,
  readPersistentRequestCache,
  rememberPersistentRequestCache,
  request,
  requestCached,
} from './client';

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

const session: AuthSession = {
  access_token: 'access',
  refresh_token: 'refresh',
  expires_in: 3600,
  user: {
    id: 1,
    profile_id: 1,
    name: 'Teacher',
    login_name: 'teacher.1',
    role: 'teacher',
    grade: null,
    must_change_password: false,
  },
};

function jsonResponse(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('authenticated API errors', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage());
    vi.stubGlobal('sessionStorage', memoryStorage());
    vi.stubGlobal('window', new EventTarget());
    setAuthSession(session);
  });

  it('sends KTP files with authentication and browser multipart headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ sections: [] }, 200));
    vi.stubGlobal('fetch', fetchMock);
    const file = new File(['sample'], 'plan.xlsx');
    await expect(parseKtpFile(file)).resolves.toEqual({ sections: [] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/ktp/parse');
    expect(init.headers).toEqual({ Authorization: 'Bearer access' });
    expect(init.body.get('file')).toBe(file);
  });

  it('retries the same KTP file after refreshing an expired access token', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Требуется вход в систему' }, 401))
      .mockResolvedValueOnce(jsonResponse({ ...session, access_token: 'renewed' }, 200))
      .mockResolvedValueOnce(jsonResponse({ sections: [] }, 200));
    vi.stubGlobal('fetch', fetchMock);
    await expect(parseKtpFile(new File(['sample'], 'plan.xlsx'))).resolves.toEqual({ sections: [] });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/auth/refresh');
    expect(fetchMock.mock.calls[2][1].headers).toEqual({ Authorization: 'Bearer renewed' });
    expect(fetchMock.mock.calls[2][1].body).toBe(fetchMock.mock.calls[0][1].body);
    expect(takeAuthNotice()).toBe('');
  });

  it('clears persisted content snapshots after a successful mutation', async () => {
    rememberPersistentRequestCache('/subjects', [{ id: 1 }], 300000);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ ok: true }, 200)));
    await request('/topics/1/archive', { method: 'POST' });
    expect(readPersistentRequestCache('/subjects')).toBeUndefined();
  });

  it('ends the local session when the backend reports a blocked account', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      detail: 'Аккаунт заблокирован.',
      code: 'account_blocked',
    }, 403)));

    await expect(request('/subjects')).rejects.toMatchObject<ApiError>({
      status: 403,
      code: 'account_blocked',
    });
    expect(takeAuthNotice()).toBe('Аккаунт заблокирован. Обратитесь к администратору.');
  });

  it('keeps the session for an ordinary role denial', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      detail: 'Недостаточно прав для этого действия.',
    }, 403)));

    await expect(request('/accounts/teachers')).rejects.toMatchObject<ApiError>({ status: 403 });
    expect(takeAuthNotice()).toBe('');
  });

  it('stores successful GET payloads in a short-lived persistent cache', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([{ id: 1, title: 'Алгебра' }], 200)));

    const payload = await requestCached('/subjects', 1_000);

    expect(payload).toEqual([{ id: 1, title: 'Алгебра' }]);
    expect(readPersistentRequestCache('/subjects', Date.now() + 500)?.data).toEqual(payload);
    expect(readPersistentRequestCache('/subjects', Date.now() + 1_500)).toBeUndefined();
  });

  it('keeps persistent cache entries scoped to the signed-in profile', () => {
    rememberPersistentRequestCache('/subjects', [{ id: 1 }], 1_000, 100);

    expect(readPersistentRequestCache('/subjects', 200)?.data).toEqual([{ id: 1 }]);

    setAuthSession({
      ...session,
      user: {
        ...session.user,
        id: 2,
        profile_id: 2,
        name: 'Other teacher',
      },
    });

    expect(readPersistentRequestCache('/subjects', 200)).toBeUndefined();
  });
});
