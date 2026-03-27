'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useActiveRoute } from '@/hooks/use-active-route';
import { useAuth } from '@/contexts/auth-context';
import { Bell, Search, LogOut, ArrowRight } from 'lucide-react';
import { useAlerts } from '@/hooks/use-alerts';

const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: 'text-red-400',
  HIGH: 'text-orange-400',
};

export function Header() {
  const activeRoute = useActiveRoute();
  const router = useRouter();
  const { user, loading, isGuest, signOutUser } = useAuth();
  const alerts = useAlerts();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

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

  // Close dropdown when clicking outside
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
    <header className="h-16 bg-bg-base border-b border-border-default flex items-center justify-between px-6 ml-[240px] fixed top-0 right-0 left-0 z-40">
      <div className="flex items-center">
        <h1 className="font-display text-24px text-white uppercase tracking-tight">{getPageTitle()}</h1>
      </div>

      <div className="flex-1 max-w-md mx-8">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted group-hover:text-text-secondary transition-colors" />
          <input
            type="text"
            placeholder="⌘K to search"
            className="w-full bg-bg-surface border border-border-default rounded-md py-1.5 pl-9 pr-4 text-sm text-white placeholder:text-text-muted focus:outline-none focus:border-border-focus transition-all duration-150"
            readOnly
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Bell — hidden when already on /alerts */}
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
                {/* Header row */}
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-default">
                  <span className="font-mono text-[11.5px] font-bold uppercase tracking-[0.25em] text-white">
                    Critical &amp; High Alerts
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    {priorityAlerts.length} open
                  </span>
                </div>

                {/* Alert list */}
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

                {/* Footer — navigate to alerts */}
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
          {user ? '3 INCIDENTS' : 'GUEST'}
        </div>

        <div className="w-px h-6 bg-border-default" />

        {loading ? (
          <div className="w-20 h-8 bg-bg-surface rounded animate-pulse" aria-hidden />
        ) : user ? (
          <div className="flex items-center gap-2">
            <button onClick={signOutUser} className="p-1.5 text-text-muted hover:text-white transition-colors" title="Sign out">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : isGuest ? (
          <button onClick={signOutUser} className="p-1.5 text-text-muted hover:text-white transition-colors" title="Exit guest">
            <LogOut className="w-4 h-4" />
          </button>
        ) : null}
      </div>
    </header>
  );
}
