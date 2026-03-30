'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useActiveRoute } from '@/hooks/use-active-route';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';
import { Map, Bell, Activity, Shield, Search, FileText, MessageSquare, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useEffect, useState } from 'react';

function useUptime() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      setSeconds(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);
  const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
  const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function getInitials(name: string | null | undefined): string {
  if (!name) return 'G';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0]!.substring(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

function getUserId(uid: string | undefined, isGuest: boolean): string {
  if (isGuest) return 'GUEST';
  if (!uid) return '—';
  return uid.substring(0, 8).toUpperCase();
}

function useSidebarStats() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [currentRound, setCurrentRound] = useState(0);
  const [activeMissions, setActiveMissions] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      const opts = isGuest
        ? { guest: true as const, signal: ac.signal }
        : user
        ? { headers: { Authorization: `Bearer ${await user.getIdToken()}` }, signal: ac.signal }
        : null;
      if (!opts) return;
      try {
        const [status, incidents] = await Promise.all([
          apiFetchJson<{ currentRound: number; activeClients: number }>('/api/fl/status', opts),
          apiFetchJson<{ items: { status: string }[]; total: number }>('/api/incidents', opts),
        ]);
        if (!cancelled) {
          setCurrentRound(status.currentRound);
          const ongoing = incidents.items.filter(
            (i) => i.status !== 'RESOLVED' && i.status !== 'POST_MORTEM',
          ).length;
          setActiveMissions(ongoing);
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled && e instanceof ApiError) console.warn('Sidebar stats:', e.message);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isGuest, user]);

  return { currentRound, activeMissions };
}

export function Sidebar({
  collapsed = false,
  onToggleCollapsed,
}: {
  collapsed?: boolean;
  onToggleCollapsed: () => void;
}) {
  const activeRoute = useActiveRoute();
  const { user, isGuest } = useAuth();
  const signedInUser = !isGuest ? user : null;
  const uptime = useUptime();
  const { currentRound, activeMissions } = useSidebarStats();

  const displayName = isGuest ? 'Guest' : (signedInUser?.displayName ?? signedInUser?.email ?? 'Unknown');
  const initials = isGuest ? 'G' : getInitials(signedInUser?.displayName ?? signedInUser?.email);
  const userId = getUserId(signedInUser?.uid, isGuest);

  const navItems = [
    { href: '/dashboard', icon: Map, label: 'Threat Map' },
    { href: '/alerts', icon: Bell, label: 'Alert Feed' },
    { href: '/fl-health', icon: Activity, label: 'FL Monitor' },
    { href: '/incidents', icon: Shield, label: 'Incidents' },
    { href: '/forensics', icon: Search, label: 'Forensics' },
    { href: '/audit', icon: FileText, label: 'Audit Logs' },
    { href: '/bastionbot', icon: MessageSquare, label: 'BastionBot' },
  ];

  return (
    <aside
      className={`fixed left-0 top-0 z-50 flex h-full flex-col border-r border-border-default bg-bg-base transition-[width] duration-200 ${
        collapsed ? 'w-[88px]' : 'w-[240px]'
      }`}
    >
      <div className={`border-b border-border-default ${collapsed ? 'p-3' : 'pl-5 pr-1 py-5'}`}>
        <div className={`flex ${collapsed ? 'items-center justify-center' : 'items-center justify-between gap-4'}`}>
          {!collapsed && (
            <Link href="/" className="flex min-w-0 flex-1 items-center pr-2 hover:opacity-90 transition-opacity">
              <span className="truncate font-display text-[20px] font-bold leading-none text-white tracking-tight">
                BASTIONFED
              </span>
            </Link>
          )}
          <button
            onClick={onToggleCollapsed}
            className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-transparent bg-bg-surface text-text-secondary transition-colors hover:border-border-default hover:text-white ${
              collapsed ? '' : '-translate-x-1'
            }`}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          </button>
        </div>
      </div>

      <nav className={`flex-1 overflow-y-auto no-scrollbar ${collapsed ? 'py-5' : 'py-4'}`}>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = activeRoute?.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href as any}
                  className={`flex items-center transition-all duration-150 ${
                    collapsed ? 'justify-center px-3 py-4' : 'gap-[10px] px-4 py-3'
                  } ${
                    isActive
                      ? 'border-l-2 border-white bg-bg-overlay text-white'
                      : 'border-l-2 border-transparent text-text-secondary hover:bg-bg-overlay hover:text-white'
                  }`}
                  title={collapsed ? item.label : undefined}
                >
                  <item.icon className={collapsed ? 'w-5 h-5' : 'w-4 h-4'} />
                  {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className={`border-t border-border-default ${collapsed ? 'p-3' : 'p-4'} space-y-4`}>
        {/* System status block */}
        {collapsed ? (
          <div className="flex justify-center">
            <span className="relative flex h-3 w-3 flex-shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
            </span>
          </div>
        ) : (
          <div className="bg-bg-overlay border border-border-strong rounded-md px-3 py-2.5 space-y-2">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
              </span>
              <span className="text-[11px] font-mono font-bold text-white tracking-widest uppercase">SYSTEM ONLINE</span>
            </div>
            <div className="space-y-1">
              <p className="font-mono text-[10px] text-text-muted tracking-wider">
                UPTIME: <span className="text-white">{uptime}</span>
              </p>
              <p className="font-mono text-[10px] text-text-muted tracking-wider">
                FL ROUND: <span className="text-white">{currentRound} ACTIVE</span>
              </p>
              <p className="font-mono text-[10px] text-text-muted tracking-wider">
                INCIDENTS: <span className="text-white">{activeMissions} ONGOING</span>
              </p>
            </div>
          </div>
        )}

        {/* Current user */}
        <div className={`flex ${collapsed ? 'justify-center' : 'items-center gap-3'}`}>
          <div className="w-10 h-10 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0 relative overflow-hidden">
            {signedInUser?.photoURL ? (
              <Image src={signedInUser.photoURL} alt={displayName} fill className="object-cover grayscale" referrerPolicy="no-referrer" sizes="40px" />
            ) : (
              initials
            )}
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="text-sm text-white font-medium truncate">{displayName}</span>
              <span className="text-[11px] text-text-muted font-mono">ID: {userId}</span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
