import { useLayoutEffect, useState } from 'react';
import { useAuth } from '@/components/auth/AuthContext';

type ListPosition = { search: string; scrollY: number; restore: boolean };
function readPosition(key: string): ListPosition | null {
  try { return JSON.parse(sessionStorage.getItem(key) || 'null') as ListPosition | null; }
  catch { return null; }
}

/** The list belongs to this viewer and this tab, including when Browser Back is used. */
export function useDashboardListPosition(ready: boolean) {
  const { user } = useAuth();
  const key = `intellect-dashboard-list:${user?.profile_id ?? ''}`;
  const [search, setSearch] = useState(() => readPosition(key)?.search ?? '');
  useLayoutEffect(() => {
    const position = readPosition(key);
    if (!ready || !position?.restore) return;
    const frame = requestAnimationFrame(() => {
      window.scrollTo({ top: position.scrollY, behavior: 'instant' });
    });
    return () => cancelAnimationFrame(frame);
  }, [key, ready]);
  const remember = () => {
    try { sessionStorage.setItem(key, JSON.stringify({ search, scrollY: window.scrollY, restore: true })); }
    catch { /* Navigation must still work with storage disabled. */ }
  };
  return { search, setSearch, remember };
}
