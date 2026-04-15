'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useActiveRoute } from '@/hooks/use-active-route';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { useFLClients } from '@/contexts/fl-clients-context';
import { Bell, LogOut, ArrowRight, Layers } from 'lucide-react';
import { useAlerts } from '@/hooks/use-alerts';
import { useActiveIncidentsCount } from '@/hooks/use-active-incidents-count';

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: 'text-red-400',
  HIGH: 'text-orange-400',
};

function clientLabel(c: { id: string; department: string; nodeName?: string | null }): string {
  return c.nodeName?.trim() || c.department || c.id;
}

export function Header({ sidebarCollapsed = false }: { sidebarCollapsed?: boolean }) {
  const activeRoute = useActiveRoute();
  const router = useRouter();
  const { user, loading, isDevMode, signOutUser, role } = useAuth();
  const {
    canUseAdminClientView,
    mode: adminViewMode,
    setMode: setAdminViewMode,
    selectedClientId,
    setSelectedClientId,
  } = useViewMode();
  const flClients = useFLClients();
  const signedInUser = !isDevMode ? user : null;
  const alerts = useAlerts();
  const activeIncidentsCount = useActiveIncidentsCount();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const isClientUser = role === 'client_user';
  const clientScopeLabels = isClientUser
    ? flClients.map((c) => clientLabel(c)).filter(Boolean)
    : [];

  const priorityAlerts = alerts
    .filter((a) => (a.severity === 'CRITICAL' || a.severity === 'HIGH') && a.status === 'OPEN')
    .slice(0, 5);

  const onAlerts = activeRoute?.startsWith('/alerts') ?? false;

  const getPageTitle = () => {
    if (!activeRoute) return 'DASHBOARD';
    if (activeRoute.startsWith('/dashboard')) return 'THREAT MAP';
    if (activeRoute.startsWith('/alerts')) return 'ALERT FEED';
    if (activeRoute.startsWith('/fl-health')) return 'FL MONITOR';
    if (activeRoute.startsWith('/incidents')) return 'INCIDENTS';
    if (activeRoute.startsWith('/forensics')) return 'FORENSICS';
    if (activeRoute.startsWith('/audit')) return 'AUDIT LOGS';
    if (activeRoute.startsWith('/bastionbot')) return 'BASTIONBOT';
    return 'DASHBOARD';
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <header
      className={`h-16 bg-bg-base border-b border-border-default flex items-center justify-between px-6 fixed top-0 right-0 left-0 z-40 transition-[margin] duration-200 ${
        sidebarCollapsed ? 'ml-[88px]' : 'ml-[240px]'
      }`}
    >
      <div className="flex items-center">
        <h1 className="font-display text-24px text-white uppercase tracking-tight">{getPageTitle()}</h1>
      </div>

      {/* Centre: view-scope control */}
      <div className="flex min-w-0 flex-1 justify-center px-4">
        {/* Admin: all-clients / single-client toggle */}
        {canUseAdminClientView && (
          <div className="flex min-w-0 max-w-4xl flex-wrap items-center justify-center gap-x-3 gap-y-2">
            <div className="flex min-w-0 flex-shrink-0 flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:gap-3">
              <div
                className="inline-flex shrink-0 rounded-lg border border-white/[0.08] bg-bg-surface p-0.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                role="group"
                aria-label="Client data scope"
              >
                <button
                  type="button"
                  onClick={() => setAdminViewMode('tenant')}
                  className={`rounded-md px-3.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] transition-all duration-150 ${
                    adminViewMode === 'tenant'
                      ? 'bg-white text-black shadow-sm'
                      : 'text-text-muted hover:bg-white/[0.04] hover:text-white'
                  }`}
                >
                  All clients
                </button>
                <button
                  type="button"
                  onClick={() => setAdminViewMode('client')}
                  className={`rounded-md px-3.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] transition-all duration-150 ${
                    adminViewMode === 'client'
                      ? 'bg-white text-black shadow-sm'
                      : 'text-text-muted hover:bg-white/[0.04] hover:text-white'
                  }`}
                >
                  Single client
                </button>
              </div>

              {adminViewMode === 'client' && (
                <select
                  aria-label="FL client for admin client view"
                  title="FL client for admin client view"
                  value={selectedClientId ?? ''}
                  onChange={(e) => setSelectedClientId(e.target.value || null)}
                  className="h-[36px] min-w-[11rem] max-w-[16rem] rounded-lg border-2 border-white/45 bg-bg-surface px-3 pr-8 text-[11px] font-semibold text-white shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_8px_24px_-4px_rgba(0,0,0,0.55)] ring-1 ring-white/15 transition-[border-color,box-shadow] focus:border-white focus:outline-none focus:ring-2 focus:ring-white/30"
                >
                  <option value="">Select client node…</option>
                  {flClients.map((c) => (
                    <option key={c.id} value={c.id}>
                      {clientLabel(c)}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {adminViewMode === 'client' && selectedClientId ? (
              <p className="max-w-[min(18rem,calc(100vw-12rem))] shrink text-left text-[10px] font-mono leading-snug tracking-wide text-amber-400/90 sm:border-l sm:border-white/[0.12] sm:pl-3">
                <span className="text-text-muted">Previewing</span>{' '}
                <span className="text-white/90">
                  {clientLabel(
                    flClients.find((c) => c.id === selectedClientId) ?? {
                      id: selectedClientId,
                      department: selectedClientId,
                    },
                  )}
                </span>
              </p>
            ) : adminViewMode === 'tenant' ? (
              <p className="shrink-0 text-left text-[10px] font-mono leading-snug tracking-wide text-emerald-400/85 sm:border-l sm:border-white/[0.12] sm:pl-3">
                Showing all client data
              </p>
            ) : null}
          </div>
        )}

        {/* Client user: site-scope indicator */}
        {isClientUser && !isDevMode && (
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-text-muted shrink-0" aria-hidden />
            <span className="text-[11px] font-mono text-text-muted uppercase tracking-wider">Site scope:</span>
            <span className="text-[11px] font-medium text-white truncate">
              {clientScopeLabels.length > 0 ? clientScopeLabels.join(', ') : 'Loading…'}
            </span>
            <span className="text-[10px] font-mono text-text-muted whitespace-nowrap">· your data only</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {!onAlerts && (
          <div ref={dropdownRef} className="relative">
            <button
              type="button"
              onClick={() => setDropdownOpen((v) => !v)}
              className="relative text-text-secondary hover:text-white transition-colors"
              aria-label="Notifications"
            >
              <Bell className="w-5 h-5" />
              {priorityAlerts.length > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-white text-black text-[10px] font-bold flex items-center justify-center rounded-full">
                  {priorityAlerts.length}
                </span>
              )}
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 top-[calc(100%+12px)] w-80 bg-bg-surface border border-border-default shadow-xl z-50">
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-default">
                  <span className="font-mono text-[11.5px] font-bold uppercase tracking-[0.25em] text-white">
                    Critical &amp; High Alerts
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    {priorityAlerts.length} open
                  </span>
                </div>

                <ul className="divide-y divide-border-default max-h-72 overflow-y-auto">
                  {priorityAlerts.length === 0 ? (
                    <li className="px-4 py-4 text-xs font-mono text-text-muted text-center">
                      No critical or high alerts
                    </li>
                  ) : (
                    priorityAlerts.map((alert) => (
                      <li
                        key={alert.id}
                        className="px-4 py-3 hover:bg-bg-overlay cursor-pointer transition-colors"
                        onClick={() => {
                          setDropdownOpen(false);
                          router.push('/alerts');
                        }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-white truncate">{alert.type}</p>
                            <p className="text-[10px] font-mono text-text-muted truncate mt-0.5">
                              {alert.device.name} · {alert.device.wing}
                            </p>
                          </div>
                          <span
                            className={`text-[10px] font-mono font-bold uppercase flex-shrink-0 ${SEVERITY_COLOR[alert.severity] ?? 'text-text-muted'}`}
                          >
                            {alert.severity}
                          </span>
                        </div>
                      </li>
                    ))
                  )}
                </ul>

                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    router.push('/alerts');
                  }}
                  className="w-full flex items-center justify-between px-4 py-2.5 border-t border-border-default text-[10.5px] font-mono uppercase tracking-widest text-text-muted hover:text-white hover:bg-bg-overlay transition-colors"
                >
                  View all alerts
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>
        )}

        <div className="w-px h-6 bg-border-default" />

        <div className="border border-border-strong bg-bg-overlay text-xs font-mono uppercase tracking-wider px-3 py-1 rounded-full text-white">
          {signedInUser
            ? `${activeIncidentsCount} ${activeIncidentsCount === 1 ? 'INCIDENT' : 'INCIDENTS'}`
            : 'DEV'}
        </div>

        <div className="w-px h-6 bg-border-default" />

        {loading ? (
          <div className="w-20 h-8 bg-bg-surface rounded animate-pulse" aria-hidden />
        ) : signedInUser ? (
          <div className="flex items-center gap-2">
            <button onClick={signOutUser} className="p-1.5 text-text-muted hover:text-white transition-colors" title="Sign out">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : isDevMode ? (
          <button onClick={signOutUser} className="p-1.5 text-text-muted hover:text-white transition-colors" title="Exit dev mode">
            <LogOut className="w-4 h-4" />
          </button>
        ) : null}
      </div>
    </header>
  );
}
