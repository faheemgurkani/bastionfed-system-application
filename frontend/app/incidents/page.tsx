'use client';

import { useState } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { IncidentKanban } from '@/components/incidents/IncidentKanban';
import { IncidentDetail } from '@/components/incidents/IncidentDetail';
import { PlaybookLibrary } from '@/components/incidents/PlaybookLibrary';
import { Incident } from '@/lib/types';
import { MOCK_INCIDENTS } from '@/lib/mock-data';

export default function IncidentsPage() {
  // FastAPI endpoint: GET http://localhost:8000/api/incidents
  // TODO: Replace with fetch() when backend is connected
  const data = MOCK_INCIDENTS;
  
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  return (
    <AuthGate>
    <div className="flex flex-col gap-6 h-full">
      {selectedIncident ? (
        <IncidentDetail incident={selectedIncident} onBack={() => setSelectedIncident(null)} />
      ) : (
        <>
          <div className="flex-1 min-h-[500px]">
            <IncidentKanban onSelectIncident={setSelectedIncident} />
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
