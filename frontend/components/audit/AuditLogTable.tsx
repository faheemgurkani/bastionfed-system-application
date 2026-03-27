'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, isAbortError } from '@/lib/api';
import type { AuditLog } from '@/lib/types';
import { ShieldAlert, LogIn, Settings, Database, Server, AlertTriangle } from 'lucide-react';

interface AuditLogTableProps {
  searchQuery: string;
  activeFilter: string | null;
  last24h: boolean;
  onRecentLogsCheck: (hasRecent: boolean) => void;
}

export function AuditLogTable({ searchQuery, activeFilter, last24h, onRecentLogsCheck }: AuditLogTableProps) {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);
      try {
        let data: { items: AuditLog[]; nextCursor: string | null; total: number };
        if (isGuest) {
          data = await apiFetchJson('/api/audit/logs?limit=10', { guest: true, signal: ac.signal });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson('/api/audit/logs?limit=10', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
            // Fetch first page only; pagination UI can be added later.
          });
        } else {
          return;
        }

        if (cancelled) return;
        setLogs(data.items);
        setTotal(data.total);
        setNextCursor(data.nextCursor);
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Failed to load audit logs');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isGuest, user]);

  useEffect(() => {
    if (logs.length === 0) return;
    const now = Date.now();
    const hasRecent = logs.some(log => (now - new Date(log.timestamp).getTime()) < 24 * 60 * 60 * 1000);
    onRecentLogsCheck(hasRecent);
  }, [logs, onRecentLogsCheck]);

  const filteredLogs = logs.filter(log => {
    // 1. Search Query
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const match = log.actor.toLowerCase().includes(q) ||
        log.action.toLowerCase().includes(q) ||
        log.target.toLowerCase().includes(q) ||
        log.result.toLowerCase().includes(q) ||
        log.hash.toLowerCase().includes(q);
      if (!match) return false;
    }
    
    // 2. Last 24 Hours
    if (last24h) {
      const isRecent = (Date.now() - new Date(log.timestamp).getTime()) < 24 * 60 * 60 * 1000;
      if (!isRecent) return false;
    }

    // 3. Quick Filters
    if (activeFilter) {
      if (activeFilter === 'Authentication' && !log.action.includes('LOGIN') && !log.action.includes('AUTH')) return false;
      if (activeFilter === 'Configuration Changes' && !log.action.includes('CONFIG') && !log.action.includes('UPDATE')) return false;
      if (activeFilter === 'Data Access' && !log.action.includes('DATA') && !log.action.includes('EXPORT')) return false;
      if (activeFilter === 'System Events' && !log.action.includes('SYSTEM') && !log.action.includes('SERVICE')) return false;
      if (activeFilter === 'Failed Actions' && log.result === 'SUCCESS') return false;
    }

    return true;
  });

  const getActionIcon = (action: string) => {
    if (action.includes('LOGIN') || action.includes('AUTH')) return <LogIn className="w-4 h-4" />;
    if (action.includes('CONFIG') || action.includes('UPDATE')) return <Settings className="w-4 h-4" />;
    if (action.includes('DATA') || action.includes('EXPORT')) return <Database className="w-4 h-4" />;
    if (action.includes('SYSTEM') || action.includes('SERVICE')) return <Server className="w-4 h-4" />;
    if (action.includes('ALERT') || action.includes('QUARANTINE')) return <ShieldAlert className="w-4 h-4" />;
    return <AlertTriangle className="w-4 h-4" />;
  };

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg h-full flex flex-col overflow-hidden">
      <div className="overflow-x-auto">
        {error && (
          <p className="p-3 text-sm font-mono text-severity-high border-b border-border-default bg-bg-base">
            {error}
          </p>
        )}
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-bg-base border-b border-border-default">
              <th className="p-4 font-display text-[10px] text-text-muted uppercase tracking-wider w-[180px]">Timestamp</th>
              <th className="p-4 font-display text-[10px] text-text-muted uppercase tracking-wider w-[120px]">Actor</th>
              <th className="p-4 font-display text-[10px] text-text-muted uppercase tracking-wider w-[200px]">Action</th>
              <th className="p-4 font-display text-[10px] text-text-muted uppercase tracking-wider">Target</th>
              <th className="p-4 font-display text-[10px] text-text-muted uppercase tracking-wider w-[120px]">Hash</th>
              <th className="p-4 font-display text-[10px] text-text-muted uppercase tracking-wider w-[100px]">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {loading && logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-4 text-text-secondary text-sm font-mono">
                  Loading…
                </td>
              </tr>
            ) : filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-4 text-text-secondary text-sm font-mono text-center">
                  No logs match current filters
                </td>
              </tr>
            ) : (
              filteredLogs.map((log) => (
              <tr key={log.id} className="hover:bg-bg-overlay transition-colors">
                <td className="p-4 font-mono text-[11px] text-text-secondary whitespace-nowrap">
                  {new Date(log.timestamp).toLocaleString()}
                </td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-bg-base border border-border-strong flex items-center justify-center text-[8px] font-bold text-white">
                      {log.actor.split(' ').map(n => n[0]).join('')}
                    </div>
                    <span className="text-sm text-white font-medium">{log.actor}</span>
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex items-center gap-2 text-text-secondary">
                    {getActionIcon(log.action)}
                    <span className="font-mono text-xs text-white">{log.action}</span>
                  </div>
                </td>
                <td className="p-4">
                  <span className="text-sm text-text-secondary">{log.target}</span>
                </td>
                <td className="p-4 font-mono text-xs text-text-muted">
                  {log.hash}
                </td>
                <td className="p-4">
                  <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${
                    log.result === 'SUCCESS' ? 'border-border-strong text-text-secondary' :
                    'border-severity-critical text-severity-critical'
                  }`}>
                    {log.result}
                  </span>
                </td>
              </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      
      <div className="p-4 border-t border-border-default bg-bg-base flex justify-between items-center mt-auto">
        <span className="text-xs text-text-muted font-mono">
          Showing {filteredLogs.length} of {total} total logs
        </span>
        <div className="flex gap-2">
          <button className="px-3 py-1 border border-border-default rounded text-xs text-text-muted hover:text-white transition-colors disabled:opacity-50" disabled>
            Previous
          </button>
          <button
            className="px-3 py-1 border border-border-default rounded text-xs text-text-muted hover:text-white transition-colors disabled:opacity-50"
            disabled={!nextCursor}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
