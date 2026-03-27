'use client';

import { useState, useEffect } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { SampleList } from '@/components/forensics/SampleList';
import { AnalysisReport } from '@/components/forensics/AnalysisReport';
import { MalwareSample } from '@/lib/types';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';

type SampleListResponse = {
  items: MalwareSample[];
  nextCursor: string | null;
  total: number;
};

export default function ForensicsPage() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [samples, setSamples] = useState<MalwareSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<MalwareSample | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      setError(null);
      try {
        let data: SampleListResponse;
        if (isGuest) {
          data = await apiFetchJson<SampleListResponse>('/api/forensics/samples', {
            guest: true,
            signal: ac.signal,
          });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<SampleListResponse>('/api/forensics/samples', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });
        } else {
          return;
        }
        if (!cancelled) {
          setSamples(data.items);
          setSelectedSample((prev) => {
            if (prev && data.items.some((s) => s.id === prev.id)) return prev;
            return data.items[0] ?? null;
          });
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Failed to load samples');
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isGuest, user]);

  return (
    <AuthGate>
      <div className="flex flex-col gap-2 h-full">
        {error && (
          <p className="text-sm font-mono text-severity-high px-1">{error}</p>
        )}
        <div className="flex gap-6 flex-1 min-h-0">
          <div className="w-1/3 min-w-[320px] h-full">
            <SampleList
              samples={samples}
              selectedId={selectedSample?.id}
              onSelect={setSelectedSample}
            />
          </div>
          <div className="flex-1 h-full overflow-hidden">
            {selectedSample ? (
              <AnalysisReport sample={selectedSample} />
            ) : (
              <div className="text-text-muted text-sm p-6">No samples loaded.</div>
            )}
          </div>
        </div>
      </div>
    </AuthGate>
  );
}
