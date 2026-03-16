'use client';

import { AuthGate } from '@/components/auth/AuthGate';
import { AuditLogTable } from '@/components/audit/AuditLogTable';
import { AuditFilters } from '@/components/audit/AuditFilters';
import { MOCK_AUDIT_LOGS } from '@/lib/mock-data';

export default function AuditPage() {
  // FastAPI endpoint: GET http://localhost:8000/api/audit/logs
  // TODO: Replace with fetch() when backend is connected
  const data = MOCK_AUDIT_LOGS;

  return (
    <AuthGate>
    <div className="flex flex-col gap-6 h-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-medium text-white mb-1">Audit Logs</h1>
          <p className="text-sm text-text-secondary">Comprehensive record of all system and user activities for compliance and forensics.</p>
        </div>
        <button className="px-4 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-interactive-hover transition-colors">
          Export CSV
        </button>
      </div>
      
      <AuditFilters />
      
      <div className="flex-1 min-h-[500px]">
        <AuditLogTable />
      </div>
    </div>
    </AuthGate>
  );
}
