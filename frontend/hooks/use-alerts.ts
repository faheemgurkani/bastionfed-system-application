import { useAlertsContext } from '@/contexts/alerts-context';

/** Alert list from GET /api/alerts + SSE /api/events (FastAPI). */
export function useAlerts() {
  return useAlertsContext().alerts;
}
