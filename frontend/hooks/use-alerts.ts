import { useAlertsContext } from '@/contexts/alerts-context';

/** Consumes the shared alerts stream from SSE (/api/events). Must be used within AlertsProvider. */
export function useAlerts() {
  return useAlertsContext();
}
