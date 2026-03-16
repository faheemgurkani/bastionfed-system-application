'use client';

import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { useAlerts } from '@/hooks/use-alerts';

export function EventsFeed() {
  const router = useRouter();
  const alerts = useAlerts();
  const recentEvents = alerts.slice(0, 10);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'border-l-severity-critical';
      case 'HIGH': return 'border-l-severity-high';
      case 'MEDIUM': return 'border-l-severity-medium';
      case 'LOW': return 'border-l-severity-low';
      default: return 'border-l-border-default';
    }
  };

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-xs text-white uppercase tracking-wider">Recent Events</span>
        <button
          type="button"
          onClick={() => router.push('/alerts')}
          className="flex items-center gap-1.5 text-[10.5px] font-mono uppercase tracking-widest text-text-muted hover:text-white transition-colors"
        >
          View all alerts
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 pr-2">
        {recentEvents.map((event) => (
          <div key={event.id} className={`pl-3 border-l-2 ${getSeverityColor(event.severity)} flex flex-col gap-1 py-1`}>
            <div className="flex justify-between items-start">
              <span className="font-mono text-[11px] text-text-muted" suppressHydrationWarning>
                {new Date(event.timestamp).toLocaleTimeString([], { hour12: false })}
              </span>
              <span className="border border-border-strong bg-bg-overlay text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full text-white">
                {event.severity}
              </span>
            </div>
            <span className="text-[13px] text-white font-medium">{event.device.name}</span>
            <span className="text-[12px] text-text-secondary">{event.type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
