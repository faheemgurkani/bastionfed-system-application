"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AuthGate } from "@/components/auth/AuthGate";
import { IncidentKanban } from "@/components/incidents/IncidentKanban";
import { IncidentDetail } from "@/components/incidents/IncidentDetail";
import { PlaybookLibrary } from "@/components/incidents/PlaybookLibrary";
import { Incident, IncidentStatus } from "@/lib/types";
import { useAuth } from "@/contexts/auth-context";
import { useViewMode } from "@/contexts/view-mode-context";
import { apiFetchJson, ApiError, isAbortError } from "@/lib/api";

type IncidentListResponse = {
  items: Incident[];
  nextCursor: string | null;
  total: number;
};

function IncidentsPageContent() {
  const { user, loading: authLoading, isDevMode } = useAuth();
  const { viewScopeKey } = useViewMode();
  const searchParams = useSearchParams();
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);

  async function updateIncidentStatus(incidentId: string, status: IncidentStatus) {
    const current = incidents.find((inc) => inc.id === incidentId);
    if (!current || current.status === status) return;

    const prevIncidents = incidents;
    setIncidents((rows) =>
      rows.map((inc) => (inc.id === incidentId ? { ...inc, status } : inc))
    );
    setSelectedIncident((prev) =>
      prev && prev.id === incidentId ? { ...prev, status } : prev
    );
    setIncidentsError(null);

    try {
      if (isDevMode) {
        const updated = await apiFetchJson<Incident>(`/api/incidents/${encodeURIComponent(incidentId)}`, {
          method: "PATCH",
          body: JSON.stringify({
            status,
            assignee: current.assignee,
            notes: `Status moved to ${status} from kanban drag-drop`,
          }),
          devMode: true,
        });
        setIncidents((rows) =>
          rows.map((inc) => (inc.id === incidentId ? updated : inc))
        );
        setSelectedIncident((prev) => (prev && prev.id === incidentId ? updated : prev));
        return;
      }

      if (!user) throw new Error("No authenticated user");
      const token = await user.getIdToken();
      const updated = await apiFetchJson<Incident>(`/api/incidents/${encodeURIComponent(incidentId)}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          status,
          assignee: current.assignee,
          notes: `Status moved to ${status} from kanban drag-drop`,
        }),
      });
      setIncidents((rows) =>
        rows.map((inc) => (inc.id === incidentId ? updated : inc))
      );
      setSelectedIncident((prev) => (prev && prev.id === incidentId ? updated : prev));
    } catch (e) {
      setIncidents(prevIncidents);
      setSelectedIncident((prev) =>
        prev && prev.id === incidentId ? current : prev
      );
      setIncidentsError(
        e instanceof ApiError ? e.message : "Failed to update incident status"
      );
    }
  }

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;
    const ac = new AbortController();

    async function loadIncidents() {
      setIncidentsLoading(true);
      setIncidentsError(null);

      try {
        let data: IncidentListResponse;
        if (isDevMode) {
          data = await apiFetchJson<IncidentListResponse>('/api/incidents', {
            devMode: true,
            signal: ac.signal,
          });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<IncidentListResponse>('/api/incidents', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });
        } else {
          return;
        }

        if (cancelled) return;
        setIncidents(data.items);
        setSelectedIncident((prev) => {
          if (prev && data.items.some((inc) => inc.id === prev.id)) return prev;
          const focusedIncidentId = searchParams.get('incidentId');
          if (focusedIncidentId) {
            return data.items.find((incident) => incident.id === focusedIncidentId) ?? null;
          }
          return null;
        });
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled) {
          setIncidentsError(e instanceof ApiError ? e.message : "Failed to load incidents");
        }
      } finally {
        if (!cancelled) setIncidentsLoading(false);
      }
    }

    void loadIncidents();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isDevMode, searchParams, user, viewScopeKey]);

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
                onMoveIncident={updateIncidentStatus}
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

export default function IncidentsPage() {
  return (
    <Suspense
      fallback={
        <AuthGate>
          <div className="flex h-full items-center justify-center text-sm font-mono text-text-muted">
            Loading incidents...
          </div>
        </AuthGate>
      }
    >
      <IncidentsPageContent />
    </Suspense>
  );
}
