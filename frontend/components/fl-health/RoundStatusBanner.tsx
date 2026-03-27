'use client';

import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';

type FLStatus = {
  currentRound: number;
  totalRounds: number;
  activeClients: number;
  totalClients: number;
  nextRoundIn: number;
  aggregatorStatus: string;
  latestAccuracy: number;
  latestFpRate: number;
  driftDetected: boolean;
};

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function RoundStatusBanner() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [status, setStatus] = useState<FLStatus | null>(null);
  const [remaining, setRemaining] = useState(180);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    let ac = new AbortController();

    async function load() {
      ac.abort();
      ac = new AbortController();
      const sig = ac.signal;
      try {
        if (isGuest) {
          const data = await apiFetchJson<FLStatus>('/api/fl/status', { guest: true, signal: sig });
          if (!cancelled) setStatus(data);
        } else if (user) {
          const token = await user.getIdToken();
          const data = await apiFetchJson<FLStatus>('/api/fl/status', {
            headers: { Authorization: `Bearer ${token}` },
            signal: sig,
          });
          if (!cancelled) setStatus(data);
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled && e instanceof ApiError) console.warn('FL status:', e.message);
      }
    }

    void load();
    const id = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      ac.abort();
      clearInterval(id);
    };
  }, [authLoading, isGuest, user]);

  useEffect(() => {
    if (status) setRemaining(status.nextRoundIn);
  }, [status]);

  useEffect(() => {
    const id = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(id);
  }, []);

  const round = status?.currentRound ?? 47;
  const total = status?.totalRounds ?? 100;
  const active = status?.activeClients ?? 12;
  const totalClients = status?.totalClients ?? 15;
  const agg = status?.aggregatorStatus ?? 'AGGREGATING';
  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-6 flex items-center justify-between">
      <div className="flex flex-col gap-3">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-5xl text-white tracking-tight">ROUND {round}</span>
          <span className="font-mono text-xl text-text-muted">/ {total}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Status:</span>
          <div className="flex items-center gap-2 border border-border-strong bg-bg-overlay px-3 py-1.5 rounded-full">
            <Loader2 className="w-4 h-4 text-white animate-spin" />
            <span className="font-mono text-xs text-white uppercase tracking-wider">{agg}</span>
          </div>
          {status?.driftDetected && (
            <span className="text-[10px] font-mono uppercase text-severity-high">Drift</span>
          )}
        </div>
      </div>

      <div className="flex items-start gap-8">
        <div className="flex flex-col items-end gap-2">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
            {active} / {totalClients} CLIENTS ACTIVE
          </span>
          <div className="flex gap-1 mt-2">
            {Array.from({ length: totalClients }).map((_, i) => {
              const isActive = i < active;
              const isLastActive = i === active - 1;
              return (
                <div key={i} className="relative flex items-center justify-center">
                  {isLastActive && isActive && (
                    <span className="animate-ping absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-2.5 w-2.5 rounded-full bg-white opacity-75" />
                  )}
                  <div
                    className={`relative w-2.5 h-2.5 rounded-full ${isActive ? 'bg-white' : 'bg-border-strong'}`}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">NEXT ROUND IN</span>
          <span className="font-mono text-lg text-white">{formatCountdown(remaining)}</span>
        </div>
      </div>
    </div>
  );
}
