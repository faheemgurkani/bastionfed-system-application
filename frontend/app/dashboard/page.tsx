import { AuthGate } from '@/components/auth/AuthGate';
import { KPICards } from '@/components/dashboard/KPICards';
import { NetworkTopology } from '@/components/dashboard/NetworkTopology';
import { EventsFeed } from '@/components/dashboard/EventsFeed';

export default function DashboardPage() {
  // Real-time data: KPICards, NetworkTopology, and EventsFeed consume SSE from /api/events via useAlerts().
  return (
    <AuthGate>
    <div className="flex flex-col gap-6">
      <KPICards />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col gap-6">
          <NetworkTopology />
        </div>
        <div className="lg:col-span-1">
          <EventsFeed />
        </div>
      </div>
    </div>
    </AuthGate>
  );
}
