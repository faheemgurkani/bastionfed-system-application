'use client';

import { useState } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { AuditLogTable } from '@/components/audit/AuditLogTable';
import { AuditFilters } from '@/components/audit/AuditFilters';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, ApiError } from '@/lib/api';

export default function AuditPage() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [verifyResult, setVerifyResult] = useState<string | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);

  async function runVerify() {
    setVerifyResult(null);
    if (authLoading) return;
    setVerifyBusy(true);
    try {
      let data: { valid: boolean; totalLogs?: number; firstBreakAt?: string; checkedAt?: string };
      if (isGuest) {
        data = await apiFetchJson('/api/audit/verify', { guest: true });
      } else if (user) {
        const token = await user.getIdToken();
        data = await apiFetchJson('/api/audit/verify', {
          headers: { Authorization: `Bearer ${token}` },
        });
      } else {
        setVerifyResult('Sign in or use guest mode.');
        return;
      }
      setVerifyResult(
        data.valid
          ? `Chain valid (${data.totalLogs ?? 0} logs) at ${data.checkedAt ?? ''}`
          : `Tamper detected at ${data.firstBreakAt ?? '?'} (${data.totalLogs ?? 0} logs)`
      );
    } catch (e) {
      setVerifyResult(e instanceof ApiError ? e.message : 'Verify failed');
    } finally {
      setVerifyBusy(false);
    }
  }

  return (
    <AuthGate>
    <div className="flex flex-col gap-6 h-full">
      <div className="flex justify-between items-center flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-medium text-white mb-1">Audit Logs</h1>
          <p className="text-sm text-text-secondary">Comprehensive record of all system and user activities for compliance and forensics.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void runVerify()}
            disabled={verifyBusy}
            className="px-4 py-2 bg-bg-overlay border border-border-default text-white text-sm font-medium rounded-md hover:bg-bg-base transition-colors disabled:opacity-50"
          >
            {verifyBusy ? 'Verifying…' : 'Verify chain'}
          </button>
        <button className="px-4 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-interactive-hover transition-colors">
          Export CSV
        </button>
        </div>
      </div>
      {verifyResult && (
        <p className="text-sm font-mono text-text-secondary border border-border-default rounded-md p-3 bg-bg-surface">{verifyResult}</p>
      )}
      
      <AuditFilters />
      
      <div className="flex-1 min-h-[500px]">
        <AuditLogTable />
      </div>
    </div>
    </AuthGate>
  );
}
