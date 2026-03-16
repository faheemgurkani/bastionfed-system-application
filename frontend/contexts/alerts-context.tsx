'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { Alert } from '@/lib/types';
import { MOCK_ALERTS } from '@/lib/mock-data';

type AlertsContextValue = Alert[];

const AlertsContext = createContext<AlertsContextValue | undefined>(undefined);

export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<Alert[]>(MOCK_ALERTS);

  useEffect(() => {
    const eventSource = new EventSource('/api/events');

    eventSource.onmessage = (event: MessageEvent<string>) => {
      try {
        const newAlert: Alert = JSON.parse(event.data);
        setAlerts((prev) => [newAlert, ...prev]);
      } catch (e) {
        console.error('Failed to parse SSE data', e);
      }
    };

    return () => {
      eventSource.close();
    };
  }, []);

  return (
    <AlertsContext.Provider value={alerts}>
      {children}
    </AlertsContext.Provider>
  );
}

export function useAlertsContext(): AlertsContextValue {
  const value = useContext(AlertsContext);
  if (value === undefined) {
    throw new Error('useAlerts must be used within AlertsProvider');
  }
  return value;
}
