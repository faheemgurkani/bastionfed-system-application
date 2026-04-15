'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';

/** Counts incidents that are not closed (same rule as sidebar “ongoing”). */
export function useActiveIncidentsCount(): number {
  const { user, loading: authLoading, isDevMode, sessionReady } = useAuth();
  const { viewScopeKey } = useViewMode();
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      const opts = isDevMode
        ? { devMode: true as const, signal: ac.signal }
        : user && sessionReady
          ? { headers: { Authorization: `Bearer ${await user.getIdToken()}` }, signal: ac.signal }
          : null;
      if (!opts) {
        if (!cancelled) setCount(0);
        return;
      }
      try {
        const incidents = await apiFetchJson<{ items: { status: string }[] }>('/api/incidents', opts);
        if (!cancelled) {
          const ongoing = incidents.items.filter(
            (i) => i.status !== 'RESOLVED' && i.status !== 'POST_MORTEM',
          ).length;
          setCount(ongoing);
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled && e instanceof ApiError) console.warn('Active incidents count:', e.message);
        if (!cancelled) setCount(0);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isDevMode, sessionReady, user, viewScopeKey]);

  return count;
}
