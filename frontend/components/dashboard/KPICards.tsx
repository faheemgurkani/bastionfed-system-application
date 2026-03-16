'use client';

import { useAlerts } from '@/hooks/use-alerts';

export function KPICards() {
  const alerts = useAlerts();
  const activeThreats = alerts.filter(a => a.status === 'OPEN').length;
  const avgConfidence = alerts.length > 0 ? (alerts.reduce((acc, a) => acc + a.confidence, 0) / alerts.length).toFixed(1) : '0.0';

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">Active Threats</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-3xl text-white">{activeThreats}</span>
          <span className="text-xs text-text-secondary">Real-time</span>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">Devices Under Watch</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-3xl text-white">23</span>
          <span className="text-xs text-text-secondary">Stable</span>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">FL Training Round</span>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="font-mono text-3xl text-white">47 / 100</span>
          <span className="text-xs text-text-secondary">Aggregating...</span>
        </div>
      </div>

      <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col justify-between">
        <span className="font-display text-xs text-text-muted uppercase tracking-wider">Avg Detection Confidence</span>
        <div className="mt-2 flex flex-col gap-2">
          <span className="font-mono text-3xl text-white">{avgConfidence}%</span>
          <div className="w-full h-1 bg-bg-subtle rounded-full overflow-hidden">
            <div className="h-full bg-white" style={{ width: `${avgConfidence}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}
