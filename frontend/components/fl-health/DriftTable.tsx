'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { apiFetchJson, ApiError } from '@/lib/api';

type DriftRow = {
  model: string;
  score: number;
  peakScore?: number;
  status: string;
  samples: number;
  lastEvent: string;
};

type DriftReport = {
  available: boolean;
  message?: string;
  operatorUse?: string;
  scope?: string;
  driftScores: DriftRow[];
  overallDrift: number;
  overallStatus: string;
  driftDetected: boolean;
  nReferenceImages: number;
  samplesAnalyzed: number;
  checkedAt: string;
};

type ClientDriftEntry = {
  clientId: string;
  department: string;
  fvDrift: { score: number | null; status: string; tau: number };
  imgDrift: { score: number | null; status: string; tau: number };
  combinedScore: number;
  combinedStatus: string;
  samplesAnalyzed: number;
  lastEvent: string;
};

type ClientDriftReport = {
  available: boolean;
  scope?: string;
  message?: string;
  clients: ClientDriftEntry[];
  checkedAt: string;
};

const STATUS_STYLES: Record<string, string> = {
  STABLE:         'text-green-400',
  MONITORING:     'text-yellow-400',
  DRIFT_DETECTED: 'text-red-400 font-bold',
  DEMO_RESEARCH:  'text-green-400',
  DEMO:           'text-green-400',
  'N/A':          'text-muted-foreground',
};

const ZERO_DRIFT_ROWS: DriftRow[] = [
  { model: 'fl-dnn-v1 (FV branch)', score: 0, status: 'STABLE', samples: 0, lastEvent: 'No data yet' },
  { model: 'fl-resnet-v1 (Image branch)', score: 0, status: 'STABLE', samples: 0, lastEvent: 'No data yet' },
  { model: 'fl-meta-v1 (Fusion)', score: 0, status: 'STABLE', samples: 0, lastEvent: 'No data yet' },
];

function statusClass(status: string): string {
  return STATUS_STYLES[status] ?? '';
}

function displayStatusLabel(status: string): string {
  if (status === 'DEMO_RESEARCH' || status === 'DEMO') return 'STABLE';
  return status.replace('_', ' ');
}

export function DriftTable() {
  const { user, isDevMode } = useAuth();
  const { viewScopeKey } = useViewMode();
  const [report, setReport] = useState<DriftReport | null>(null);
  const [clientDrift, setClientDrift] = useState<ClientDriftReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'global' | 'clients'>('global');

  async function fetchDrift() {
    try {
      const opts = isDevMode
        ? { devMode: true }
        : { headers: { Authorization: `Bearer ${await user!.getIdToken()}` } };
      const [globalData, clientData] = await Promise.all([
        apiFetchJson<DriftReport>('/api/fl/drift', opts),
        apiFetchJson<ClientDriftReport>('/api/fl/drift/clients', opts),
      ]);
      setReport(globalData);
      setClientDrift(clientData);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load drift data');
    }
  }

  useEffect(() => {
    if (!user && !isDevMode) return;
    void fetchDrift();
    const id = setInterval(fetchDrift, 15000);
    return () => clearInterval(id);
  }, [user, isDevMode, viewScopeKey]);

  if (error) {
    return (
      <div className="bg-bg-surface border border-border-default rounded-lg p-4">
        <span className="font-display text-xs text-white uppercase tracking-wider">Drift Detection</span>
        <p className="text-red-400 text-xs font-mono mt-2">{error}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex-1 flex flex-col">
        <span className="font-display text-xs text-white uppercase tracking-wider mb-4">Drift Detection</span>
        <p className="text-muted-foreground text-xs font-mono animate-pulse">Loading...</p>
      </div>
    );
  }

  const hasBackendDrift = report.available;
  const samplesCt = hasBackendDrift ? (report.samplesAnalyzed ?? 0) : 0;
  const refImg = hasBackendDrift ? (report.nReferenceImages ?? 0) : 0;
  const driftRows =
    hasBackendDrift && report.driftScores && report.driftScores.length > 0 ? report.driftScores : ZERO_DRIFT_ROWS;
  const rawOverallStatus = hasBackendDrift && report.overallStatus ? report.overallStatus : 'STABLE';
  const overallDriftVal = hasBackendDrift && report.overallDrift != null ? report.overallDrift : 0;

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex-1 flex flex-col">
      <div className="flex items-center justify-between mb-1">
        <span className="font-display text-xs text-white uppercase tracking-wider">Drift Detection</span>
        <span className={`font-mono text-[10px] uppercase tracking-wider ${statusClass(rawOverallStatus)}`}>
          {displayStatusLabel(rawOverallStatus)}
        </span>
      </div>
      <p className="font-mono text-[10px] text-muted-foreground tabular-nums mb-3">
        {samplesCt} samples analyzed · {refImg.toLocaleString()} reference images
      </p>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-border-default mb-3">
        <button
          onClick={() => setTab('global')}
          className={`font-mono text-[10px] uppercase tracking-wider px-3 py-1.5 transition-colors ${
            tab === 'global' ? 'text-white border-b-2 border-white' : 'text-muted-foreground hover:text-white'
          }`}
        >
          Global Model
        </button>
        <button
          onClick={() => setTab('clients')}
          className={`font-mono text-[10px] uppercase tracking-wider px-3 py-1.5 transition-colors ${
            tab === 'clients' ? 'text-white border-b-2 border-white' : 'text-muted-foreground hover:text-white'
          }`}
        >
          Per-Client
        </button>
      </div>

      <div className="flex-1 overflow-auto no-scrollbar">
        {tab === 'global' && (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-default">
                <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Model / Modality</th>
                <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Samples</th>
                <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Drift Score</th>
                <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Status</th>
                <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider text-right">Last Event</th>
              </tr>
            </thead>
            <tbody>
              {driftRows.map((d, i) => (
                <tr key={i} className="border-b border-border-default last:border-0 hover:bg-bg-overlay transition-colors">
                  <td className="py-2 text-[12px] text-white">{d.model}</td>
                  <td className="py-2 text-[11px] text-text-secondary font-mono tabular-nums">{d.samples}</td>
                  <td className="py-2 text-[12px] font-mono tabular-nums">
                    {d.score.toFixed(4)}
                    {d.peakScore != null && (
                      <span className="text-[10px] text-muted-foreground ml-1">(peak {d.peakScore.toFixed(4)})</span>
                    )}
                  </td>
                  <td className={`py-2 text-[11px] font-mono uppercase ${statusClass(d.status)}`}>
                    {displayStatusLabel(d.status)}
                  </td>
                  <td className="py-2 text-right text-[11px] text-text-secondary font-mono">{d.lastEvent}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'clients' && (
          <div className="flex flex-col gap-3">
            {(!clientDrift?.available || clientDrift.clients.length === 0) && (
              <div className="border border-border-default rounded-md p-3">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <p className="text-[9px] text-muted-foreground uppercase">FV Drift</p>
                    <p className="font-mono text-[11px] text-white tabular-nums">0.0000</p>
                    <p className={`text-[9px] font-mono uppercase ${statusClass('STABLE')}`}>STABLE</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-muted-foreground uppercase">Image Drift</p>
                    <p className="font-mono text-[11px] text-white tabular-nums">0.0000</p>
                    <p className={`text-[9px] font-mono uppercase ${statusClass('STABLE')}`}>STABLE</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-muted-foreground uppercase">Samples</p>
                    <p className="font-mono text-[11px] text-white tabular-nums">0</p>
                    <p className="text-[9px] text-muted-foreground font-mono">No data yet</p>
                  </div>
                </div>
              </div>
            )}
            {clientDrift?.available && clientDrift.clients.map((c) => (
              <div key={c.clientId} className="border border-border-default rounded-md p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                      c.combinedStatus === 'STABLE' ? 'bg-green-400' :
                      c.combinedStatus === 'MONITORING' ? 'bg-yellow-400' : 'bg-red-400'
                    }`} />
                    <span className="font-mono text-xs text-white">{c.clientId}</span>
                    <span className="text-[10px] text-muted-foreground">· {c.department}</span>
                  </div>
                  <span className={`font-mono text-[10px] uppercase tracking-wider ${statusClass(c.combinedStatus)}`}>
                    {displayStatusLabel(c.combinedStatus)}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <p className="text-[9px] text-muted-foreground uppercase">FV Drift</p>
                    <p className="font-mono text-[11px] text-white">{c.fvDrift.score != null ? c.fvDrift.score.toFixed(4) : 'N/A'}</p>
                    <p className={`text-[9px] font-mono uppercase ${statusClass(c.fvDrift.status)}`}>{displayStatusLabel(c.fvDrift.status)}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-muted-foreground uppercase">Image Drift</p>
                    <p className="font-mono text-[11px] text-white">{c.imgDrift.score != null ? c.imgDrift.score.toFixed(4) : 'N/A'}</p>
                    <p className={`text-[9px] font-mono uppercase ${statusClass(c.imgDrift.status)}`}>{displayStatusLabel(c.imgDrift.status)}</p>
                  </div>
                  <div>
                    <p className="text-[9px] text-muted-foreground uppercase">Samples</p>
                    <p className="font-mono text-[11px] text-white">{c.samplesAnalyzed}</p>
                    <p className="text-[9px] text-muted-foreground">{c.lastEvent}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="font-mono text-[10px] text-muted-foreground">
          Overall: <span className={`tabular-nums ${statusClass(rawOverallStatus)}`}>{overallDriftVal.toFixed(4)}</span>
        </span>
        <button
          onClick={fetchDrift}
          className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:text-white transition-colors"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
