'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import type { FLClient } from '@/lib/types';
import { MOCK_FL_CLIENTS } from '@/lib/mock-data';

type FLClientsContextValue = FLClient[];

const FLClientsContext = createContext<FLClientsContextValue | undefined>(undefined);

export function FLClientsProvider({ children }: { children: React.ReactNode }) {
  const [clients, setClients] = useState<FLClient[]>(MOCK_FL_CLIENTS);

  useEffect(() => {
    const eventSource = new EventSource('/api/fl-events');

    eventSource.onmessage = (event: MessageEvent<string>) => {
      try {
        const patch: Partial<FLClient> & { id: string } = JSON.parse(event.data);
        const { id, ...updates } = patch;
        if (!id) return;

        setClients((prev) =>
          prev.map((c) =>
            c.id === id ? { ...c, ...updates } : c
          )
        );
      } catch (e) {
        console.error('Failed to parse FL client SSE data', e);
      }
    };

    return () => {
      eventSource.close();
    };
  }, []);

  return (
    <FLClientsContext.Provider value={clients}>
      {children}
    </FLClientsContext.Provider>
  );
}

export function useFLClientsContext(): FLClientsContextValue {
  const value = useContext(FLClientsContext);
  if (value === undefined) {
    throw new Error('useFLClients must be used within FLClientsProvider');
  }
  return value;
}

/** Hook to consume live FL clients from the FLClientsProvider (SSE /api/fl-events). */
export function useFLClients(): FLClientsContextValue {
  return useFLClientsContext();
}
