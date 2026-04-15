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

export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading, isDevMode, sessionReady } = useAuth();
  const { viewScopeKey } = useViewMode();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const replaceAlert = useCallback((updated: Alert) => {
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }, []);

  // Initial load: GET /api/alerts
  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      setAlertsLoading(true);
      setAlertsError(null);
      try {
        if (isDevMode) {
          const data = await apiFetchJson<AlertListResponse>('/api/alerts', {
            devMode: true,
            signal: ac.signal,
          });
          if (!cancelled) setAlerts(data.items);
        } else if (user && sessionReady) {
          const token = await user.getIdToken();
          const data = await apiFetchJson<AlertListResponse>('/api/alerts', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });
          if (!cancelled) setAlerts(data.items);
        } else {
          if (!cancelled) {
            setAlerts([]);
            setAlertsError('Sign in or continue in dev mode to load alerts.');
          }
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
  }, [authLoading, isDevMode, sessionReady, user, viewScopeKey]);

  // SSE: /api/events on FastAPI
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
          const newAlert: Alert = JSON.parse(event.data);
          setAlerts((prev) => [newAlert, ...prev]);
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
  }, [authLoading, isDevMode, sessionReady, user, viewScopeKey]);

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
