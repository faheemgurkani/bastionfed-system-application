'use client';

import { useEffect, useState } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { IncidentKanban } from '@/components/incidents/IncidentKanban';
import { IncidentDetail } from '@/components/incidents/IncidentDetail';
import { PlaybookLibrary } from '@/components/incidents/PlaybookLibrary';
import { Incident } from '@/lib/types';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError } from '@/lib/api';

type IncidentListResponse = {
  items: Incident[];
  nextCursor: string | null;
  total: number;
};

export default function IncidentsPage() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function loadIncidents() {
      setIncidentsLoading(true);
      setIncidentsError(null);

      try {
        let data: IncidentListResponse;
        if (isGuest) {
          data = await apiFetchJson<IncidentListResponse>('/api/incidents', { guest: true });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<IncidentListResponse>('/api/incidents', {
            headers: { Authorization: `Bearer ${token}` },
          });
        } else {
          return;
        }

        if (cancelled) return;
        setIncidents(data.items);
        setSelectedIncident((prev) => {
          if (prev && data.items.some((inc) => inc.id === prev.id)) return prev;
          return data.items[0] ?? null;
        });
      } catch (e) {
        if (!cancelled) setIncidentsError(e instanceof ApiError ? e.message : 'Failed to load incidents');
      } finally {
        if (!cancelled) setIncidentsLoading(false);
      }
    }

    void loadIncidents();
    return () => {
      cancelled = true;
    };
  }, [authLoading, isGuest, user]);

  return (
    <AuthGate>
    <div className="flex flex-col gap-6 h-full">
      {incidentsError && (
        <p className="text-sm font-mono text-severity-high px-1">{incidentsError}</p>
      )}
      {selectedIncident ? (
        <IncidentDetail incident={selectedIncident} onBack={() => setSelectedIncident(null)} />
      ) : (
        <>
          <div className="flex-1 min-h-[500px]">
            <IncidentKanban
              incidents={incidents}
              onSelectIncident={setSelectedIncident}
              loading={incidentsLoading}
            />
          </div>
          <div className="h-[320px]">
            <PlaybookLibrary />
          </div>
        </>
      )}
    </div>
    </AuthGate>
  );
}
