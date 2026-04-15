'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';

type BucketRow = { id?: string; name?: string; public?: boolean; file_size_limit?: number };

export function StorageBucketsPanel() {
  const { user, loading: authLoading, isDevMode } = useAuth();
  const [buckets, setBuckets] = useState<BucketRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || isDevMode || !user) return;
    const ac = new AbortController();
    (async () => {
      setErr(null);
      try {
        const token = await user.getIdToken();
        const data = await apiFetchJson<{ buckets: BucketRow[] }>('/api/storage/buckets', {
          headers: { Authorization: `Bearer ${token}` },
          signal: ac.signal,
        });
        setBuckets(Array.isArray(data.buckets) ? data.buckets : []);
      } catch (e) {
        if (isAbortError(e)) return;
        setErr(e instanceof ApiError ? e.message : 'Could not list buckets');
        setBuckets([]);
      }
    })();
    return () => ac.abort();
  }, [authLoading, isDevMode, user]);

  if (isDevMode) {
    return (
      <p className="text-xs font-mono text-text-muted">Bucket list is hidden in dev mode.</p>
    );
  }

  return (
    <div className="border border-white/10 bg-white/[0.02] p-4 space-y-2">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Supabase storage buckets</p>
      {err && <p className="text-xs text-amber-400 font-mono">{err}</p>}
      {!err && buckets.length === 0 && user && (
        <p className="text-xs text-text-muted">No buckets returned (check service key / project URL).</p>
      )}
      {buckets.length > 0 && (
        <ul className="space-y-1.5">
          {buckets.map((b) => (
            <li key={b.id ?? b.name} className="flex flex-wrap items-baseline gap-x-3 text-xs font-mono text-white">
              <span className="font-semibold">{b.name ?? b.id}</span>
              {b.public !== undefined && (
                <span className="text-text-muted">{b.public ? 'public' : 'private'}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
