import { useEffect, useState } from 'react';

import { getAuthSession, refreshAuthSession } from './authSession';

type ProtectedMedia = {
  url: string;
  isLoading: boolean;
  error: boolean;
};

type ProtectedMediaOptions = {
  enabled?: boolean;
};

export function useProtectedMediaUrl(
  source?: string | null,
  { enabled = true }: ProtectedMediaOptions = {},
): ProtectedMedia {
  const requiresAuth = Boolean(source?.startsWith('/api/'));
  const [state, setState] = useState<ProtectedMedia>({
    url: requiresAuth && !enabled ? '' : requiresAuth ? '' : source || '',
    isLoading: requiresAuth && enabled,
    error: false,
  });

  useEffect(() => {
    if (!enabled && source?.startsWith('/api/')) {
      setState({ url: '', isLoading: false, error: false });
      return;
    }
    if (!source || !source.startsWith('/api/')) {
      setState({ url: source || '', isLoading: false, error: false });
      return;
    }

    const controller = new AbortController();
    let objectUrl = '';
    let cancelled = false;

    const load = async () => {
      setState({ url: '', isLoading: true, error: false });
      let session = getAuthSession();
      let response = await fetch(source, {
        signal: controller.signal,
        headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : undefined,
      });
      if (response.status === 401 && session?.refresh_token) {
        session = await refreshAuthSession();
        if (session) response = await fetch(source, {
          signal: controller.signal,
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
      }
      if (!response.ok) throw new Error(`Media request failed: ${response.status}`);
      objectUrl = URL.createObjectURL(await response.blob());
      if (cancelled) URL.revokeObjectURL(objectUrl);
      else setState({ url: objectUrl, isLoading: false, error: false });
    };

    void load().catch((error: unknown) => {
      if (!cancelled && !(error instanceof DOMException && error.name === 'AbortError')) {
        setState({ url: '', isLoading: false, error: true });
      }
    });

    return () => {
      cancelled = true;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [enabled, source]);

  return state;
}
