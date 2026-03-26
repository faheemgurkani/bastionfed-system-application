'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import type { FLClient } from '@/lib/types';
import { MOCK_FL_CLIENTS } from '@/lib/mock-data';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError, flEventsSourceUrl } from '@/lib/api';

type FLClientsContextValue = FLClient[];

const FLClientsContext = createContext<FLClientsContextValue | undefined>(undefined);

export function FLClientsProvider({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [clients, setClients] = useState<FLClient[]>(MOCK_FL_CLIENTS);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    async function loadClients() {
      try {
        type FLClientsResponse = { clients: FLClient[] };
        let data: FLClientsResponse;
        if (isGuest) {
          data = await apiFetchJson<FLClientsResponse>('/api/fl/clients', { guest: true });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<FLClientsResponse>('/api/fl/clients', {
            headers: { Authorization: `Bearer ${token}` },
          });
        } else {
          return;
        }

        if (!cancelled) setClients(data.clients);
      } catch (e) {
        if (!cancelled) console.warn(e instanceof ApiError ? e.message : 'Failed to load FL clients');
      }
    }

    void loadClients();
    return () => {
      cancelled = true;
    };
  }, [authLoading, isGuest, user]);

  useEffect(() => {
    if (authLoading) return;
    if (!isGuest && !user) return;

    let es: EventSource | null = null;
    let closed = false;

    async function connect() {
      let token: string | null = null;
      if (!isGuest && user) token = await user.getIdToken();
      if (closed) return;

      es = new EventSource(flEventsSourceUrl(token, isGuest));

      es.onmessage = (event: MessageEvent<string>) => {
        try {
          const patch: Partial<FLClient> & { id: string } = JSON.parse(event.data);
          const { id, ...updates } = patch;
          if (!id) return;

          setClients((prev) => prev.map((c) => (c.id === id ? { ...c, ...updates } : c)));
        } catch (e) {
          console.error('Failed to parse FL client SSE data', e);
        }
      };

      es.onerror = () => {
        /* browser will retry automatically */
      };
    };
    void connect();

    return () => {
      closed = true;
      es?.close();
    };
  }, [authLoading, isGuest, user]);

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
