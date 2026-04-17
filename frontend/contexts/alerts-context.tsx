'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { Alert } from '@/lib/types';
import { apiFetchJson, ApiError, eventsSourceUrl, isAbortError } from '@/lib/api';

type AlertListResponse = {
  items: Alert[];
  nextCursor: string | null;
  total: number;
};

export type AlertsContextValue = {
  alerts: Alert[];
  alertsLoading: boolean;
  alertsError: string | null;
  /** Replace one alert after PATCH (or full object from server). */
  replaceAlert: (alert: Alert) => void;
};

const AlertsContext = createContext<AlertsContextValue | undefined>(undefined);

function isFullAlertPayload(data: unknown): data is Alert {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return (
    typeof d.id === 'string' &&
    typeof d.timestamp === 'string' &&
    typeof d.device === 'object' &&
    d.device !== null
  );
}

export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading, isDevMode, sessionReady } = useAuth();
  const { viewScopeKey } = useViewMode();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const replaceAlert = useCallback((updated: Alert) => {
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }, []);

  const fetchAlertsList = useCallback(
    async (signal?: AbortSignal): Promise<Alert[] | null> => {
      if (isDevMode) {
        const data = await apiFetchJson<AlertListResponse>('/api/alerts', {
          devMode: true,
          signal,
        });
        return data.items;
      }
      if (user && sessionReady) {
        const token = await user.getIdToken();
        const data = await apiFetchJson<AlertListResponse>('/api/alerts', {
          headers: { Authorization: `Bearer ${token}` },
          signal,
        });
        return data.items;
      }
      return null;
    },
    [isDevMode, sessionReady, user]
  );

  // Initial load: GET /api/alerts
  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      setAlertsLoading(true);
      setAlertsError(null);
      try {
        const items = await fetchAlertsList(ac.signal);
        if (cancelled) return;
        if (items !== null) {
          setAlerts(items);
        } else {
          setAlerts([]);
          setAlertsError('Sign in or continue in dev mode to load alerts.');
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled) {
          const msg = e instanceof ApiError ? e.message : 'Failed to load alerts';
          setAlertsError(msg);
        }
      } finally {
        if (!cancelled) setAlertsLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, fetchAlertsList, viewScopeKey]);

  // SSE: /api/events — full Alert from PATCH; forensic/ingest send minimal payloads → refetch list
  useEffect(() => {
    if (authLoading) return;
    let es: EventSource | null = null;
    let closed = false;

    async function connect() {
      let url: string;
      if (isDevMode) {
        url = eventsSourceUrl(null, true);
      } else if (user && sessionReady) {
        const token = await user.getIdToken();
        if (closed) return;
        url = eventsSourceUrl(token, false);
      } else {
        return;
      }
      es = new EventSource(url);
      es.onmessage = (event: MessageEvent<string>) => {
        try {
          const data: unknown = JSON.parse(event.data);
          if (isFullAlertPayload(data)) {
            setAlerts((prev) => {
              if (prev.some((a) => a.id === data.id)) return prev;
              return [data, ...prev];
            });
            return;
          }
          void (async () => {
            try {
              const items = await fetchAlertsList();
              if (items !== null) setAlerts(items);
            } catch (e) {
              console.error('Alerts refetch after SSE failed', e);
            }
          })();
        } catch (e) {
          console.error('Failed to parse SSE data', e);
        }
      };
      es.onerror = () => {
        /* browser will retry; avoid noisy logs */
      };
    }

    void connect();
    return () => {
      closed = true;
      es?.close();
    };
  }, [authLoading, fetchAlertsList, isDevMode, sessionReady, user, viewScopeKey]);

  const value = useMemo(
    () => ({
      alerts,
      alertsLoading,
      alertsError,
      replaceAlert,
    }),
    [alerts, alertsLoading, alertsError, replaceAlert]
  );

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlertsContext(): AlertsContextValue {
  const value = useContext(AlertsContext);
  if (value === undefined) {
    throw new Error('useAlertsContext must be used within AlertsProvider');
  }
  return value;
}
