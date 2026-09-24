import { endAuthSession, getAuthSession, refreshAuthSession } from '../authSession';

export function formatApiDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(formatApiDetail).filter(Boolean).join('; ');
  if (detail && typeof detail === 'object') {
    const value = detail as Record<string, unknown>;
    const primary = value.message ?? value.detail ?? value.error;
    const quality = value.quality;
    const qualityText = quality && typeof quality === 'object'
      ? formatApiDetail((quality as Record<string, unknown>).errors || (quality as Record<string, unknown>).gaps)
      : '';
    return [primary ? formatApiDetail(primary) : '', qualityText].filter(Boolean).join(' — ') || JSON.stringify(detail);
  }
  return detail == null ? 'Ошибка сервера' : String(detail);
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly code?: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
  return new ApiError(response.status, formatApiDetail(body.detail ?? body), typeof body.code === 'string' ? body.code : undefined);
}

const TERMINAL_AUTH_CODES = new Set(['account_blocked', 'account_inactive', 'profile_missing', 'session_invalid']);
const PERSISTENT_CACHE_PREFIX = 'intellect.api-cache.v1';

type CachedApiPayload<T> = {
  createdAt: number;
  expiresAt: number;
  userKey: string;
  value: T;
};

export type CachedApiSnapshot<T> = {
  data: T;
  updatedAt: number;
};

function storage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function authCacheUserKey(): string {
  const session = getAuthSession();
  const user = session?.user;
  return user ? `${user.role}:${user.profile_id}:${user.id}` : 'anonymous';
}

function persistentCacheKey(path: string): string {
  return `${PERSISTENT_CACHE_PREFIX}:${authCacheUserKey()}:${path}`;
}

export function readPersistentRequestCache<T>(path: string, now = Date.now()): CachedApiSnapshot<T> | undefined {
  const store = storage();
  if (!store) return undefined;
  const raw = store.getItem(persistentCacheKey(path));
  if (!raw) return undefined;
  try {
    const cached = JSON.parse(raw) as CachedApiPayload<T>;
    if (cached.userKey !== authCacheUserKey() || cached.expiresAt <= now) {
      store.removeItem(persistentCacheKey(path));
      return undefined;
    }
    return { data: cached.value, updatedAt: cached.createdAt };
  } catch {
    store.removeItem(persistentCacheKey(path));
    return undefined;
  }
}

export function rememberPersistentRequestCache<T>(path: string, value: T, ttlMs: number, now = Date.now()): void {
  const store = storage();
  if (!store || ttlMs <= 0) return;
  const payload: CachedApiPayload<T> = {
    createdAt: now,
    expiresAt: now + ttlMs,
    userKey: authCacheUserKey(),
    value,
  };
  try {
    store.setItem(persistentCacheKey(path), JSON.stringify(payload));
  } catch {
    // Browsers may reject writes when storage is full or disabled; network data still wins.
  }
}

export function clearPersistentRequestCache(): void {
  const store = storage();
  if (!store) return;
  const prefix = `${PERSISTENT_CACHE_PREFIX}:${authCacheUserKey()}:`;
  try {
    const keys = Array.from({ length: store.length }, (_, index) => store.key(index));
    keys.forEach(key => { if (key?.startsWith(prefix)) store.removeItem(key); });
  } catch { /* Storage may be unavailable; live requests still succeed. */ }
}

async function throwApiError(response: Response, hadSession: boolean): Promise<never> {
  const error = await apiError(response);
  if (hadSession && (response.status === 401 || (error.code && TERMINAL_AUTH_CODES.has(error.code)))) {
    endAuthSession(error.code === 'account_blocked' ? 'Аккаунт заблокирован. Обратитесь к администратору.' : 'Сессия истекла. Войдите снова.');
  }
  throw error;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let session = getAuthSession();
  let response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...init?.headers,
    },
  });
  const isSessionEndpoint = path === '/auth/login' || path === '/auth/refresh';
  if (response.status === 401 && session?.refresh_token && !isSessionEndpoint) {
    session = await refreshAuthSession();
    if (session) response = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access_token}`, ...init?.headers },
    });
  }
  if (!response.ok) return throwApiError(response, Boolean(session));
  if (init?.method && !['GET', 'HEAD'].includes(init.method.toUpperCase())) clearPersistentRequestCache();
  return response.json() as Promise<T>;
}

export async function requestCached<T>(path: string, ttlMs: number): Promise<T> {
  const data = await request<T>(path);
  rememberPersistentRequestCache(path, data, ttlMs);
  return data;
}

export async function requestNullable<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    return await request<T>(path, init);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function requestForm<T>(path: string, body: FormData): Promise<T> {
  let session = getAuthSession();
  let response = await fetch(`/api${path}`, {
    method: 'POST',
    body,
    headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : undefined,
  });
  if (response.status === 401 && session?.refresh_token) {
    session = await refreshAuthSession();
    if (session) response = await fetch(`/api${path}`, {
      method: 'POST',
      body,
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
  }
  if (!response.ok) return throwApiError(response, Boolean(session));
  return response.json() as Promise<T>;
}
