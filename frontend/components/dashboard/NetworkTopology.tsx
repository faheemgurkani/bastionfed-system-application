'use client';

import { useEffect, useRef, useState } from 'react';
import { Lock, Loader2, Minus, Plus, RotateCcw, UserRound } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { useAlerts } from '@/hooks/use-alerts';
import { apiFetchJson } from '@/lib/api';
import type { FLClient, Device } from '@/lib/types';

const SVG_W = 800;
const SVG_H = 480;
const CENTER = { x: SVG_W / 2, y: SVG_H / 2 };

const ZOOM_MIN = 0.35;
const ZOOM_MAX = 3.5;

function clientColor(status: FLClient['status']) {
  switch (status) {
    case 'ACTIVE':            return 'var(--border-strong)';
    case 'DEGRADED':          return '#b45309';
    case 'OFFLINE':           return 'var(--border-default)';
    case 'POISONING_SUSPECT': return '#dc2626';
    default:                  return 'var(--border-default)';
  }
}

function deviceColor(status: Device['status'], alerts: number) {
  if (alerts > 0) return 'var(--text-primary)';
  switch (status) {
    case 'SUSPICIOUS':   return '#b45309';
    case 'COMPROMISED':  return '#dc2626';
    case 'ISOLATED':     return 'var(--bg-base)';
    default:             return 'var(--border-default)';
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
  const alerts = useAlerts();

  const mapViewportRef = useRef<HTMLDivElement | null>(null);
  const [mapPan, setMapPan] = useState({ x: 0, y: 0 });
  const [mapZoom, setMapZoom] = useState(1);
  const dragRef = useRef<{ active: boolean; px: number; py: number }>({
    active: false,
    px: 0,
    py: 0,
  });

  const [clients, setClients] = useState<FLClient[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = mapViewportRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      const isZoom = e.ctrlKey || e.metaKey;
      if (isZoom) {
        e.preventDefault();
        const factor = Math.exp(-e.deltaY * 0.0018);
        setMapZoom((z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z * factor)));
        return;
      }
      e.preventDefault();
      setMapPan((p) => ({ x: p.x - e.deltaX, y: p.y - e.deltaY }));
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

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

        const [clientsRes, devicesRes] = await Promise.all([
          apiFetchJson<{ clients: FLClient[] }>('/api/fl/clients', opts),
          apiFetchJson<{ items: Device[] }>('/api/devices', opts),
        ]);

        if (!cancelled) {
          setClients(clientsRes.clients);
          setDevices(devicesRes.items);
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

  const alertsByDevice = new Map<string, number>(
    devices.map((d) => [
      d.id,
      alerts.filter((a) => a.deviceId === d.id && a.status === 'OPEN').length,
    ])
  );

  const clientPositions = ring(Math.max(clients.length, 1), 140);
  const clientById = new Map(clients.map((c, i) => [c.id, { client: c, pos: clientPositions[i] }]));

  /** For each client, position its devices in a tighter ring around the client node. */
  function devicePositions(clientId: string, devList: Device[]) {
    const cp = clientById.get(clientId)?.pos ?? CENTER;
    if (devList.length === 0) return [];
    const r = Math.min(70, 200 / Math.max(devList.length, 1));
    return ring(devList.length, 70, cp.x, cp.y);
  }

  const devicesByClient = new Map<string, Device[]>();
  for (const d of devices) {
    const list = devicesByClient.get(d.flClientId) ?? [];
    list.push(d);
    devicesByClient.set(d.flClientId, list);
  }

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-[480px]">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <span className="font-display text-xs text-white uppercase tracking-wider">Network Topology</span>
        {!loading && !error && clients.length > 0 ? (
          <div className="flex flex-wrap items-center justify-end">
            <div className="flex rounded-md border border-white/[0.08] bg-bg-base/80 p-0.5">
              <button
                type="button"
                aria-label="Zoom out"
                className="rounded p-1.5 text-text-muted hover:bg-white/[0.06] hover:text-white"
                onClick={() => setMapZoom((z) => Math.max(ZOOM_MIN, z / 1.2))}
              >
                <Minus className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                aria-label="Zoom in"
                className="rounded p-1.5 text-text-muted hover:bg-white/[0.06] hover:text-white"
                onClick={() => setMapZoom((z) => Math.min(ZOOM_MAX, z * 1.2))}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                aria-label="Reset map view"
                className="rounded p-1.5 text-text-muted hover:bg-white/[0.06] hover:text-white"
                onClick={() => {
                  setMapPan({ x: 0, y: 0 });
                  setMapZoom(1);
                }}
              >
                <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          </div>
        ) : null}
      </div>
      <div
        ref={mapViewportRef}
        className="relative flex-1 overflow-hidden bg-bg-base border border-border-default rounded-md touch-none select-none"
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
          dragRef.current = { active: true, px: e.clientX, py: e.clientY };
        }}
        onPointerMove={(e) => {
          const d = dragRef.current;
          if (!d.active) return;
          const dx = e.clientX - d.px;
          const dy = e.clientY - d.py;
          d.px = e.clientX;
          d.py = e.clientY;
          setMapPan((p) => ({ x: p.x + dx, y: p.y + dy }));
        }}
        onPointerUp={(e) => {
          dragRef.current.active = false;
          try {
            (e.currentTarget as HTMLDivElement).releasePointerCapture(e.pointerId);
          } catch {
            /* not captured */
          }
        }}
        onPointerCancel={() => {
          dragRef.current.active = false;
        }}
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
          <div className="absolute inset-0 flex items-center justify-center cursor-grab active:cursor-grabbing">
            <div
              className="will-change-transform shadow-2xl"
              style={{
                width: SVG_W,
                height: SVG_H,
                transform: `translate(${mapPan.x}px, ${mapPan.y}px) scale(${mapZoom})`,
                transformOrigin: 'center center',
              }}
            >
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

            {/* Edges: client → devices (DEVICE-type clients only) */}
            {clients.map((c, i) => {
              if (c.clientType === 'PERSON') return null;
              const devList = devicesByClient.get(c.id) ?? [];
              const dps = devicePositions(c.id, devList);
              const cp = clientPositions[i];
              return devList.map((d, j) => (
                <line
                  key={`edge-dev-${d.id}`}
                  x1={cp.x} y1={cp.y}
                  x2={dps[j].x} y2={dps[j].y}
                  stroke={d.status === 'ISOLATED' ? 'var(--text-primary)' : 'var(--border-default)'}
                  strokeWidth="1"
                  strokeDasharray={d.status === 'ISOLATED' ? '4' : undefined}
                />
              ));
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
              const label = c.nodeName ?? c.department ?? c.id.slice(0, 8);
              const shortLabel = label.length > 10 ? label.slice(0, 9) + '…' : label;
              const color = clientColor(c.status);
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

            {/* Device nodes (DEVICE-type clients only — PERSON clients have no IoT devices) */}
            {clients.map((c, i) => {
              if (c.clientType === 'PERSON') return null;
              const devList = devicesByClient.get(c.id) ?? [];
              const dps = devicePositions(c.id, devList);
              return devList.map((d, j) => {
                const dp = dps[j];
                const alertCount = alertsByDevice.get(d.id) ?? 0;
                const fill = deviceColor(d.status, alertCount);
                const isIsolated = d.status === 'ISOLATED';
                const label = d.name.length > 10 ? d.name.slice(0, 9) + '…' : d.name;
                return (
                  <g key={d.id} transform={`translate(${dp.x}, ${dp.y})`}>
                    <title>{`${d.name}\nIP: ${d.ip}\nStatus: ${d.status}\nAlerts: ${alertCount}`}</title>
                    {alertCount > 0 && (
                      <circle r="20" fill="none" stroke="var(--text-primary)" strokeWidth="1" className="animate-pulse" />
                    )}
                    <circle
                      r="12"
                      fill={isIsolated ? 'var(--bg-base)' : fill}
                      stroke={isIsolated ? 'var(--border-strong)' : fill}
                      strokeWidth="2"
                      strokeDasharray={isIsolated ? '3' : undefined}
                    />
                    {isIsolated && (
                      <foreignObject x="-6" y="-6" width="12" height="12">
                        <Lock className="w-3 h-3 text-text-muted" />
                      </foreignObject>
                    )}
                    <text y="24" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[9px]">
                      {label}
                    </text>
                  </g>
                );
              });
            })}
              </svg>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
