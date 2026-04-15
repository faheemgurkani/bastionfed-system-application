'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

type FLRound = {
  round: number;
  accuracy: number;
  fpRate: number;
  trainLoss: number;
  valLoss: number;
};

type FLRoundsResponse = {
  rounds: FLRound[];
  sessionId: string;
};

export function PerformanceCharts() {
  const { user, loading: authLoading, isDevMode } = useAuth();
  const { viewScopeKey } = useViewMode();
  const [rounds, setRounds] = useState<FLRound[]>([]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      try {
        let data: FLRoundsResponse;
        if (isDevMode) {
          data = await apiFetchJson<FLRoundsResponse>('/api/fl/rounds', { devMode: true, signal: ac.signal });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<FLRoundsResponse>('/api/fl/rounds', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });
        } else {
          return;
        }
        if (!cancelled) setRounds(data.rounds);
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled && e instanceof ApiError) console.warn('FL rounds:', e.message);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isDevMode, user, viewScopeKey]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="bg-bg-surface border border-border-default rounded-lg p-4 h-[240px] flex flex-col">
        <span className="font-display text-xs text-white uppercase tracking-wider mb-4">Detection Accuracy</span>
        <div className="flex-1 w-full h-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rounds} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--bg-overlay)" />
              <XAxis dataKey="round" hide />
              <YAxis domain={[80, 100]} axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-jetbrains-mono)' }} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)', borderRadius: '8px' }}
                itemStyle={{ color: 'var(--text-primary)', fontFamily: 'var(--font-jetbrains-mono)', fontSize: '12px' }}
                labelStyle={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}
              />
              <ReferenceLine y={95} stroke="var(--text-muted)" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'TARGET', fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-jetbrains-mono)' }} />
              <Line type="monotone" dataKey="accuracy" stroke="var(--text-primary)" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 h-[240px] flex flex-col">
        <span className="font-display text-xs text-white uppercase tracking-wider mb-4">False Positive Rate</span>
        <div className="flex-1 w-full h-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rounds} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--bg-overlay)" />
              <XAxis dataKey="round" hide />
              <YAxis domain={[0, 5]} axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-jetbrains-mono)' }} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)', borderRadius: '8px' }}
                itemStyle={{ color: 'var(--text-primary)', fontFamily: 'var(--font-jetbrains-mono)', fontSize: '12px' }}
                labelStyle={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}
              />
              <ReferenceLine y={2} stroke="var(--text-muted)" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'THRESHOLD', fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-jetbrains-mono)' }} />
              <Line type="monotone" dataKey="fpRate" stroke="var(--text-primary)" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 h-[240px] flex flex-col">
        <span className="font-display text-xs text-white uppercase tracking-wider mb-4">Train/Val Loss</span>
        <div className="flex-1 w-full h-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rounds} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--bg-overlay)" />
              <XAxis dataKey="round" hide />
              <YAxis domain={[0, 1]} axisLine={false} tickLine={false} tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-jetbrains-mono)' }} />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)', borderRadius: '8px' }}
                itemStyle={{ color: 'var(--text-primary)', fontFamily: 'var(--font-jetbrains-mono)', fontSize: '12px' }}
                labelStyle={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}
              />
              <Line type="monotone" dataKey="trainLoss" stroke="var(--text-primary)" strokeWidth={2} dot={false} isAnimationActive={false} name="Train" />
              <Line type="monotone" dataKey="valLoss" stroke="var(--text-muted)" strokeWidth={2} dot={false} isAnimationActive={false} name="Val" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
