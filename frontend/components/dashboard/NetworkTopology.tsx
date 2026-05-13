'use client';

import { useEffect, useState } from 'react';
import { Loader2, UserRound } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { apiFetchJson } from '@/lib/api';
import type { FLClient } from '@/lib/types';

const SVG_W = 800;
const SVG_H = 480;
const CENTER = { x: SVG_W / 2, y: SVG_H / 2 };

function clientColor(client: FLClient) {
  const label = `${client.nodeName ?? ''} ${client.department ?? ''} ${client.id ?? ''}`.toUpperCase();
  if (label.includes('CMH') || label.includes('PIMS')) {
    return '#2563eb';
  }
  const status = client.status;
  switch (status) {
    case 'ACTIVE':            return 'var(--border-strong)';
    case 'DEGRADED':          return '#b45309';
    case 'OFFLINE':           return 'var(--border-default)';
    case 'POISONING_SUSPECT': return '#dc2626';
    default:                  return 'var(--border-default)';
  }
}

/** Evenly distribute N items in a ring of radius r around cx,cy. */
function ring(n: number, r: number, cx = CENTER.x, cy = CENTER.y, offsetDeg = -90) {
  return Array.from({ length: n }, (_, i) => {
    const angle = ((offsetDeg + (360 / n) * i) * Math.PI) / 180;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
}

export function NetworkTopology() {
  const { user, isDevMode, sessionReady } = useAuth();
  const { viewScopeKey } = useViewMode();

  const [clients, setClients] = useState<FLClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const opts = isDevMode
          ? { devMode: true as const, signal: ac.signal }
          : user && sessionReady
            ? { headers: { Authorization: `Bearer ${await user.getIdToken()}` }, signal: ac.signal }
            : null;

        if (!opts) { setLoading(false); return; }

        const clientsRes = await apiFetchJson<{ clients: FLClient[] }>('/api/fl/clients', opts);

        if (!cancelled) {
          setClients(clientsRes.clients);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load topology');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; ac.abort(); };
  }, [user, isDevMode, sessionReady, viewScopeKey]);

  const clientPositions = ring(Math.max(clients.length, 1), 170);

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-[480px]">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <span className="font-display text-xs text-white uppercase tracking-wider">Network Topology</span>
        {!loading && !error && clients.length > 0 ? (
          <span className="text-[11px] font-mono uppercase tracking-wider text-text-muted">
            Direct client nodes
          </span>
        ) : null}
      </div>
      <div
        className="relative flex-1 overflow-hidden bg-bg-base border border-border-default rounded-md"
      >
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-base/40">
            <Loader2 className="w-6 h-6 text-text-muted animate-spin" />
          </div>
        )}
        {!loading && error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs text-text-muted font-mono">{error}</span>
          </div>
        )}
        {!loading && !error && clients.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs text-text-muted font-mono">No clients provisioned yet.</span>
          </div>
        )}
        {!loading && !error && clients.length > 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="shadow-2xl">
              <svg width={SVG_W} height={SVG_H} viewBox={`0 0 ${SVG_W} ${SVG_H}`} className="block rounded-sm ring-1 ring-white/[0.06]">
                <defs>
                  <pattern id="topology-map-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path
                      d="M 40 0 L 0 0 0 40"
                      fill="none"
                      stroke="rgba(255,255,255,0.16)"
                      strokeWidth="1.35"
                    />
                  </pattern>
                </defs>
                <rect width={SVG_W} height={SVG_H} fill="var(--bg-base)" />
                <rect width={SVG_W} height={SVG_H} fill="url(#topology-map-grid)" />
            {/* Edges: server → clients */}
            {clients.map((c, i) => {
              const cp = clientPositions[i];
              if (!cp) return null;
              return (
                <line
                  key={`edge-server-${c.id}`}
                  x1={CENTER.x} y1={CENTER.y}
                  x2={cp.x} y2={cp.y}
                  stroke="var(--border-default)"
                  strokeWidth="1.5"
                />
              );
            })}

            {/* FL Aggregation Server (centre) */}
            <g transform={`translate(${CENTER.x}, ${CENTER.y})`}>
              <title>FL Aggregation Server</title>
              <polygon
                points="0,-25 18,-18 25,0 18,18 0,25 -18,18 -25,0 -18,-18"
                fill="var(--border-default)"
                stroke="var(--border-strong)"
                strokeWidth="2"
              />
              <text y="40" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[11px]">
                FL Server
              </text>
            </g>

            {/* FL Client nodes */}
            {clients.map((c, i) => {
              const cp = clientPositions[i];
              if (!cp) return null;
              const label = c.nodeName ?? c.department ?? c.id.slice(0, 8);
              const shortLabel = label.length > 16 ? label.slice(0, 15) + '…' : label;
              const color = clientColor(c);
              const isPerson = c.clientType === 'PERSON';
              return (
                <g key={c.id} transform={`translate(${cp.x}, ${cp.y})`}>
                  <title>{`${label}\nType: ${c.clientType ?? 'DEVICE'}\nStatus: ${c.status}`}</title>
                  {isPerson ? (
                    /* Person client — circle with person icon */
                    <>
                      <circle r="16" fill={color} stroke="var(--border-strong)" strokeWidth="2" strokeDasharray="4 2" />
                      <foreignObject x="-8" y="-9" width="16" height="16">
                        <UserRound className="w-4 h-4 text-white" />
                      </foreignObject>
                    </>
                  ) : (
                    /* Device client — square */
                    <rect x="-14" y="-14" width="28" height="28" fill={color} stroke="var(--border-strong)" strokeWidth="2" rx="3" />
                  )}
                  <text y="28" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[10px]">
                    {shortLabel}
                  </text>
                  {isPerson && (
                    <text y="38" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[9px]" opacity="0.6">
                      person
                    </text>
                  )}
                </g>
              );
            })}
              </svg>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
