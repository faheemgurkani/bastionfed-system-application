'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useFLClients } from '@/contexts/fl-clients-context';
import { apiFetchJson, apiUrl, ApiError, getClientViewIdsForRequests, isAbortError } from '@/lib/api';

type ArtifactRow = {
  id: string;
  fl_client_id: string;
  label: string;
  kind: string;
  filename: string;
  sha256: string;
  status: string;
  created_at: string;
};

export function ClientArtifactsSection() {
  const { user, loading: authLoading, isDevMode, role } = useAuth();
  const clients = useFLClients();
  const [artifacts, setArtifacts] = useState<ArtifactRow[]>([]);
  const [flClientId, setFlClientId] = useState('');
  const [label, setLabel] = useState<'benign' | 'malware'>('benign');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const canAccessArtifacts = role === 'owner' || role === 'admin' || role === 'client_user';

  const load = useCallback(async () => {
    if (authLoading || isDevMode || !user || !canAccessArtifacts) return;
    setMsg(null);
    try {
      const token = await user.getIdToken();
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
      const cv = getClientViewIdsForRequests();
      if (cv) headers['X-Client-View-Ids'] = cv;
      const qs = flClientId ? `?flClientId=${encodeURIComponent(flClientId)}` : '';
      const data = await apiFetchJson<{ artifacts: ArtifactRow[] }>(`/api/storage/client-artifacts${qs}`, {
        headers,
      });
      setArtifacts(data.artifacts ?? []);
    } catch (e) {
      if (isAbortError(e)) return;
      setArtifacts([]);
      setMsg(e instanceof ApiError ? e.message : 'Could not load artifacts (Postgres + images bucket required)');
    }
  }, [authLoading, isDevMode, user, flClientId, canAccessArtifacts]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!flClientId && clients.length === 1) {
      setFlClientId(clients[0]!.id);
    }
  }, [clients, flClientId]);

  async function upload() {
    if (!user || !file || !flClientId) {
      setMsg('Pick an FL client and a file.');
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const token = await user.getIdToken();
      const fd = new FormData();
      fd.append('flClientId', flClientId);
      fd.append('label', label);
      fd.append('file', file);
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
      const cv = getClientViewIdsForRequests();
      if (cv) headers['X-Client-View-Ids'] = cv;
      const res = await fetch(apiUrl('/api/storage/client-artifacts'), { method: 'POST', headers, body: fd });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail?.detail || j?.detail || `HTTP ${res.status}`);
      }
      setFile(null);
      setMsg('Uploaded.');
      await load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  }

  if (isDevMode) {
    return null;
  }

  return (
    <div className="border border-white/10 bg-white/[0.02] p-4 space-y-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        Client training artifacts (bucket path: tenant / client / benign|malware / …)
      </p>
      {!canAccessArtifacts && user && (
        <p className="text-xs text-text-muted">
          Training artifact uploads and listing are limited to tenant admins and client users.
        </p>
      )}
      {msg && <p className="text-xs font-mono text-amber-400">{msg}</p>}
      {canAccessArtifacts && (
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-text-muted">FL client</span>
            <select
              value={flClientId}
              onChange={(e) => setFlClientId(e.target.value)}
              className="bg-bg-surface border border-white/20 rounded px-2 py-1.5 font-mono text-xs text-white min-w-[10rem]"
            >
              <option value="">Select…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nodeName?.trim() || c.department || c.id}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-text-muted">Label</span>
            <select
              value={label}
              onChange={(e) => setLabel(e.target.value as 'benign' | 'malware')}
              className="bg-bg-surface border border-white/20 rounded px-2 py-1.5 font-mono text-xs text-white"
            >
              <option value="benign">benign</option>
              <option value="malware">malware</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-text-muted">File</span>
            <input
              type="file"
              accept="image/*,.json,application/json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-xs text-white file:mr-2 file:rounded file:border-0 file:bg-white file:text-black file:px-2 file:py-1"
            />
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() => void upload()}
            className="rounded bg-white text-black px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
          >
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      )}
      <div className="max-h-48 overflow-y-auto border border-white/10 rounded">
        <table className="w-full text-left text-[11px] font-mono">
          <thead className="text-text-muted border-b border-white/10">
            <tr>
              <th className="p-2">ID</th>
              <th className="p-2">Client</th>
              <th className="p-2">Label</th>
              <th className="p-2">File</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.map((a) => (
              <tr key={a.id} className="border-b border-white/5 text-white/90">
                <td className="p-2">{a.id}</td>
                <td className="p-2 truncate max-w-[8rem]">{a.fl_client_id}</td>
                <td className="p-2">{a.label}</td>
                <td className="p-2 truncate max-w-[12rem]">{a.filename}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
