'use client';

import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';
import { useEffect, useState } from 'react';

export type DashboardKpis = {
  activeThreats: number;
  avgConfidence: number;
  devicesUnderWatch: number;
  flRound: number;
  openIncidents: number;
  criticalAlerts: number;
  resolvedToday: number;
  falsePositiveRate: number;
};

export function KPICards() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      try {
        if (isGuest) {
          const data = await apiFetchJson<DashboardKpis>('/api/dashboard/kpis', {
            guest: true,
            signal: ac.signal,
          });
          if (!cancelled) setKpis(data);
        } else if (user) {
          const token = await user.getIdToken();
          const data = await apiFetchJson<DashboardKpis>('/api/dashboard/kpis', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });
          if (!cancelled) setKpis(data);
        } else {
          if (!cancelled) setKpis(null);
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : 'Failed to load KPIs');
          setKpis(null);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isGuest, user]);

  const activeThreats = kpis?.activeThreats ?? '—';
  const avgConfidence = kpis != null ? kpis.avgConfidence.toFixed(1) : '—';
  const devicesWatch = kpis?.devicesUnderWatch ?? '—';
  const flRound = kpis != null ? `${kpis.flRound} / 100` : '—';

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {error && (
        <div className="col-span-full text-sm text-severity-high font-mono">
          KPIs: {error}
        </div>
      )}
      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">Active Threats</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-3xl text-white">{activeThreats}</span>
          <span className="text-xs text-text-secondary">Real-time</span>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">Devices Under Watch</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-3xl text-white">{devicesWatch}</span>
          <span className="text-xs text-text-secondary">Stable</span>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">FL Training Round</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-3xl text-white">{flRound}</span>
          <span className="text-xs text-text-secondary">Aggregating...</span>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">Avg Detection Confidence</span>
        <div className="mt-2 flex flex-col gap-2">
          <span className="font-mono text-3xl text-white">{avgConfidence}%</span>
          <div className="w-full h-1 bg-bg-subtle rounded-full overflow-hidden">
            <div
              className="h-full bg-white"
              style={{ width: `${kpis != null ? Math.min(100, kpis.avgConfidence) : 0}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
