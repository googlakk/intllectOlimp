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

async function apiError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
  return new Error(formatApiDetail(body.detail ?? body));
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return response.json() as Promise<T>;
}

export async function requestNullable<T>(path: string, init?: RequestInit): Promise<T | null> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw await apiError(response);
  }
  return response.json() as Promise<T>;
}
