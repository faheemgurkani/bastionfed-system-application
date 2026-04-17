'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';

type BucketRow = { id?: string; name?: string; public?: boolean; file_size_limit?: number };

export function StorageBucketsPanel() {
  const { user, loading: authLoading, isDevMode } = useAuth();
  const [buckets, setBuckets] = useState<BucketRow[]>([]);
  const [selectedBucket, setSelectedBucket] = useState<string>('');
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
        const rows = Array.isArray(data.buckets) ? data.buckets : [];
        setBuckets(rows);
        setSelectedBucket((prev) => {
          if (prev && rows.some((b) => (b.name ?? b.id ?? '') === prev)) return prev;
          return rows[0] ? (rows[0].name ?? rows[0].id ?? '') : '';
        });
      } catch (e) {
        if (isAbortError(e)) return;
        setErr(e instanceof ApiError ? e.message : 'Could not list buckets');
        setBuckets([]);
        setSelectedBucket('');
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
        <div className="space-y-2">
          <select
            value={selectedBucket}
            onChange={(e) => setSelectedBucket(e.target.value)}
            className="bg-bg-surface border border-white/20 rounded px-3 py-2 font-mono text-xs text-white focus:outline-none focus:border-white/40 cursor-pointer appearance-none w-full max-w-xs"
            aria-label="Supabase storage bucket selector"
          >
            {buckets.map((b) => {
              const bucketName = b.name ?? b.id ?? '';
              return (
                <option key={b.id ?? b.name} value={bucketName}>
                  {bucketName}
                </option>
              );
            })}
          </select>
          {(() => {
            const active = buckets.find((b) => (b.name ?? b.id ?? '') === selectedBucket);
            if (!active) return null;
            return (
              <p className="text-xs font-mono text-text-muted">
                {active.public ? 'public' : 'private'}
              </p>
            );
          })()}
        </div>
      )}
    </div>
  );
}
