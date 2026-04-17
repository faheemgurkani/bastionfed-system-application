import { AuthGate } from '@/components/auth/AuthGate';
import { RoundStatusBanner } from '@/components/fl-health/RoundStatusBanner';
import { PerformanceCharts } from '@/components/fl-health/PerformanceCharts';
import { ClientGrid } from '@/components/fl-health/ClientGrid';
import { DriftTable } from '@/components/fl-health/DriftTable';
import { ModelZoo } from '@/components/fl-health/ModelZoo';

export default function FLHealthPage() {
  return (
    <AuthGate>
    <div className="flex flex-col gap-6">
      <RoundStatusBanner />
      <PerformanceCharts />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ClientGrid />
        </div>
        <div className="lg:col-span-1 flex flex-col gap-6">
          <div className="bg-bg-surface border border-border-default rounded-lg p-4">
            <span className="font-display text-xs text-white uppercase tracking-wider mb-4 block">Aggregation Server Stats</span>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-text-secondary">CPU Usage</span>
                  <span className="font-mono text-xs text-white">67%</span>
                </div>
                <div className="w-full h-1.5 bg-bg-subtle rounded-full overflow-hidden">
                  <div className="h-full bg-white" style={{ width: '67%' }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-text-secondary">Memory</span>
                  <span className="font-mono text-xs text-white">4.2 / 8.0 GB</span>
                </div>
                <div className="w-full h-1.5 bg-bg-subtle rounded-full overflow-hidden">
                  <div className="h-full bg-white" style={{ width: '52.5%' }} />
                </div>
              </div>
            </div>
          </div>
          <DriftTable />
        </div>
      </div>
      <ModelZoo />
    </div>
    </AuthGate>
  );
}
