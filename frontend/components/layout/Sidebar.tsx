'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useActiveRoute } from '@/hooks/use-active-route';
import { useAuth } from '@/contexts/auth-context';
import { MOCK_FL_ROUNDS, MOCK_FL_CLIENTS, MOCK_INCIDENTS } from '@/lib/mock-data';
import { Map, Bell, Activity, Shield, Search, FileText, MessageSquare } from 'lucide-react';
import { useEffect, useState } from 'react';

const CURRENT_ROUND = MOCK_FL_ROUNDS[MOCK_FL_ROUNDS.length - 1]?.round ?? 0;
const ACTIVE_AGENTS = MOCK_FL_CLIENTS.filter(c => c.status === 'ACTIVE').length;
const ACTIVE_MISSIONS = MOCK_INCIDENTS.filter(i => i.status !== 'RESOLVED' && i.status !== 'POST_MORTEM').length;

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

export function Sidebar() {
  const activeRoute = useActiveRoute();
  const { user, isGuest } = useAuth();
  const uptime = useUptime();

  const displayName = isGuest ? 'Guest' : (user?.displayName ?? user?.email ?? 'Unknown');
  const initials = isGuest ? 'G' : getInitials(user?.displayName ?? user?.email);
  const userId = getUserId(user?.uid, isGuest);

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
    <aside className="w-[240px] fixed left-0 top-0 h-full bg-bg-base border-r border-border-default flex flex-col z-50">
      <div className="h-16 flex items-center px-4 border-b border-border-default">
        <Link href="/" className="flex items-center hover:opacity-90 transition-opacity">
          <span className="font-display font-bold text-white tracking-[0.15em] text-sm">
            BASTIONFED
          </span>
        </Link>
      </div>

      <nav className="flex-1 py-4 overflow-y-auto no-scrollbar">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = activeRoute?.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href as any}
                  className={`flex items-center gap-[10px] px-4 py-3 transition-all duration-150 ${
                    isActive
                      ? 'border-l-2 border-white bg-bg-overlay text-white'
                      : 'border-l-2 border-transparent text-text-secondary hover:bg-bg-overlay hover:text-white'
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-4 border-t border-border-default space-y-4">
        {/* System status block */}
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
              FL ROUND: <span className="text-white">{CURRENT_ROUND} ACTIVE</span>
            </p>
            <p className="font-mono text-[10px] text-text-muted tracking-wider">
              INCIDENTS: <span className="text-white">{ACTIVE_MISSIONS} ONGOING</span>
            </p>
          </div>
        </div>

        {/* Current user */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0 relative overflow-hidden">
            {user?.photoURL ? (
              <Image src={user.photoURL} alt={displayName} fill className="object-cover grayscale" referrerPolicy="no-referrer" sizes="40px" />
            ) : (
              initials
            )}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm text-white font-medium truncate">{displayName}</span>
            <span className="text-[11px] text-text-muted font-mono">ID: {userId}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
