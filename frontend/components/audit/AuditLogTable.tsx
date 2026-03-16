'use client';

import { MOCK_AUDIT_LOGS } from '@/lib/mock-data';
import { ShieldAlert, LogIn, Settings, Database, Server, AlertTriangle } from 'lucide-react';

export function AuditLogTable() {
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
            {MOCK_AUDIT_LOGS.map((log) => (
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
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="p-4 border-t border-border-default bg-bg-base flex justify-between items-center mt-auto">
        <span className="text-xs text-text-muted font-mono">Showing 1-10 of 1,248 logs</span>
        <div className="flex gap-2">
          <button className="px-3 py-1 border border-border-default rounded text-xs text-text-muted hover:text-white transition-colors disabled:opacity-50">Previous</button>
          <button className="px-3 py-1 border border-border-default rounded text-xs text-text-muted hover:text-white transition-colors">Next</button>
        </div>
      </div>
    </div>
  );
}
