'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useFLClients } from '@/contexts/fl-clients-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { apiFetchJson, apiUrl, ApiError, getClientViewIdsForRequests, isAbortError } from '@/lib/api';

type RegistryModel = {
  name: string;
  type: string;
  accuracy: number;
  fpRate: number;
  size: string;
  trainedOn: string;
  description: string;
  active: boolean;
  flClientId?: string | null;
  modelScope?: string;
  storagePath?: string | null;
};

const MODEL_TYPES = ['DNN', 'CNN', 'GNN', 'HYB', 'CUSTOM'] as const;

export function ModelZoo() {
  const { user, loading: authLoading, isDevMode, role } = useAuth();
  const { viewScopeKey } = useViewMode();
  const clients = useFLClients();
  const [models, setModels] = useState<RegistryModel[]>([]);
  const [activeModel, setActiveModel] = useState<string>('');
  const [switching, setSwitching] = useState<string | null>(null);
  const [activateClientId, setActivateClientId] = useState<string>('');

  const [genBusy, setGenBusy] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [genFile, setGenFile] = useState<File | null>(null);
  const [genName, setGenName] = useState('');
  const [genType, setGenType] = useState<string>('DNN');

  const [perBusy, setPerBusy] = useState(false);
  const [perMsg, setPerMsg] = useState<string | null>(null);
  const [perFile, setPerFile] = useState<File | null>(null);
  const [perName, setPerName] = useState('');
  const [perType, setPerType] = useState<string>('DNN');
  const [perClientId, setPerClientId] = useState<string>('');

  const [syncBusy, setSyncBusy] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const isAdmin = role === 'owner' || role === 'admin';

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();
    (async () => {
      try {
        if (isDevMode) return;
        if (!user) {
          setModels([]);
          return;
        }
        const token = await user.getIdToken();
        const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
        const cv = getClientViewIdsForRequests();
        if (cv) headers['X-Client-View-Ids'] = cv;
        const data = await apiFetchJson<{ models: RegistryModel[] }>('/api/fl/models', {
          headers,
          signal: ac.signal,
        });
        if (!cancelled) {
          setModels(data.models ?? []);
          const active = (data.models ?? []).find((m) => m.active);
          if (active) setActiveModel(active.name);
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled && e instanceof ApiError) console.warn('FL models:', e.message);
      }
    })();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isDevMode, user, viewScopeKey]);

  useEffect(() => {
    if (!activateClientId && clients.length === 1) {
      setActivateClientId(clients[0]!.id);
    }
  }, [clients, activateClientId]);

  useEffect(() => {
    if (!perClientId && clients.length === 1) {
      setPerClientId(clients[0]!.id);
    }
  }, [clients, perClientId]);

  async function refreshModels(headers: Record<string, string>) {
    const data = await apiFetchJson<{ models: RegistryModel[] }>('/api/fl/models', { headers });
    setModels(data.models ?? []);
  }

  async function handleActivate(modelName: string, forClientId?: string | null) {
    if (modelName === activeModel || isDevMode) return;
    setSwitching(modelName);
    try {
      const token = user ? await user.getIdToken() : null;
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const cv = getClientViewIdsForRequests();
      if (cv) headers['X-Client-View-Ids'] = cv;
      const cid = (forClientId ?? activateClientId) || '';
      const qs =
        cid && (role === 'client_user' || isAdmin)
          ? `?flClientId=${encodeURIComponent(cid)}`
          : '';
      const res = await fetch(apiUrl(`/api/fl/models/${encodeURIComponent(modelName)}/activate`) + qs, {
        method: 'POST',
        headers,
      });
      if (res.ok) {
        setActiveModel(modelName);
      }
    } catch {
      /* ignore */
    } finally {
      setSwitching(null);
    }
  }

  async function uploadGeneric() {
    if (!user || !genFile || !genName.trim()) {
      setGenMsg('Name and file required.');
      return;
    }
    setGenBusy(true);
    setGenMsg(null);
    try {
      const token = await user.getIdToken();
      const fd = new FormData();
      fd.append('file', genFile);
      fd.append('name', genName.trim());
      fd.append('modelType', genType);
      fd.append('description', 'Generic tenant model (admin upload)');
      fd.append('trainedOn', new Date().toISOString());
      fd.append('sizeLabel', `${genFile.size} bytes`);
      fd.append('accuracy', '0');
      fd.append('fpRate', '0');
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
      const cv = getClientViewIdsForRequests();
      if (cv) headers['X-Client-View-Ids'] = cv;
      const res = await fetch(apiUrl('/api/fl/models/upload'), { method: 'POST', headers, body: fd });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail?.detail || j?.detail || `HTTP ${res.status}`);
      }
      setGenMsg('Registered. Activate below.');
      setGenFile(null);
      setGenName('');
      await refreshModels(headers);
    } catch (e) {
      setGenMsg(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setGenBusy(false);
    }
  }

  async function uploadPersonalized() {
    if (!user || !perFile || !perName.trim()) {
      setPerMsg('Name and file required.');
      return;
    }
    if (!perClientId) {
      setPerMsg('Select the FL client this personalized model belongs to.');
      return;
    }
    setPerBusy(true);
    setPerMsg(null);
    try {
      const token = await user.getIdToken();
      const fd = new FormData();
      fd.append('file', perFile);
      fd.append('name', perName.trim());
      fd.append('modelType', perType);
      fd.append('description', 'Client-scoped personalized model (admin upload)');
      fd.append('trainedOn', new Date().toISOString());
      fd.append('sizeLabel', `${perFile.size} bytes`);
      fd.append('accuracy', '0');
      fd.append('fpRate', '0');
      fd.append('flClientId', perClientId);
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
      const cv = getClientViewIdsForRequests();
      if (cv) headers['X-Client-View-Ids'] = cv;
      const res = await fetch(apiUrl('/api/fl/models/upload'), { method: 'POST', headers, body: fd });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail?.detail || j?.detail || `HTTP ${res.status}`);
      }
      setPerMsg('Registered. Activate for that client below.');
      setPerFile(null);
      setPerName('');
      await refreshModels(headers);
    } catch (e) {
      setPerMsg(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setPerBusy(false);
    }
  }

  async function syncDiskBundles() {
    if (!user) return;
    setSyncBusy(true);
    setSyncMsg(null);
    try {
      const token = await user.getIdToken();
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
      const cv = getClientViewIdsForRequests();
      if (cv) headers['X-Client-View-Ids'] = cv;
      const data = await apiFetchJson<{
        uploaded: string[];
        registered: string[];
        skippedMissing: string[];
        storageFailed: string[];
        driftObject: string | null;
      }>('/api/fl/models/sync-global-bundles', { method: 'POST', headers });
      const parts = [
        data.registered?.length ? `Registered: ${data.registered.join(', ')}` : null,
        data.skippedMissing?.length ? `Missing on disk: ${data.skippedMissing.join(', ')}` : null,
        data.storageFailed?.length ? `Storage errors: ${data.storageFailed.join(', ')}` : null,
        data.driftObject ? `Drift bundle: ${data.driftObject}` : null,
      ].filter(Boolean);
      setSyncMsg(parts.length ? parts.join(' · ') : 'Nothing to sync (no weight files under backend/data/models).');
      await refreshModels(headers);
    } catch (e) {
      setSyncMsg(e instanceof ApiError ? e.message : 'Sync failed');
    } finally {
      setSyncBusy(false);
    }
  }

  const tenantWide = models.filter((m) => !m.flClientId);
  const perClient = models.filter((m) => !!m.flClientId);

  return (
    <div className="flex flex-col gap-6">
      {isAdmin && !isDevMode && (
        <>
          <div className="border border-border-default rounded-lg p-4 bg-bg-surface space-y-3">
            <span className="font-display text-xs text-white uppercase tracking-wider">Generic models (tenant-wide)</span>
            <p className="text-[11px] text-text-muted">
              Stored under <code className="text-white/80">global/&lt;slug&gt;/…</code> in the models bucket. All clients
              can use these alongside any personalized weights.
            </p>
            {genMsg && <p className="text-xs text-amber-400 font-mono">{genMsg}</p>}
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
              <input
                placeholder="Model slug (e.g. my-dnn-v1)"
                value={genName}
                onChange={(e) => setGenName(e.target.value)}
                className="bg-bg-base border border-white/20 rounded px-2 py-1.5 text-xs font-mono text-white min-w-[12rem]"
              />
              <select
                aria-label="Generic model type"
                value={genType}
                onChange={(e) => setGenType(e.target.value)}
                className="bg-bg-base border border-white/20 rounded px-2 py-1.5 text-xs text-white"
              >
                {MODEL_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                aria-label="Generic model weights file"
                title="Model weights file"
                type="file"
                onChange={(e) => setGenFile(e.target.files?.[0] ?? null)}
                className="text-xs text-white file:mr-2 file:rounded file:border-0 file:bg-white file:text-black file:px-2 file:py-1"
              />
              <button
                type="button"
                disabled={genBusy}
                onClick={() => void uploadGeneric()}
                className="rounded bg-white text-black px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
              >
                {genBusy ? 'Uploading…' : 'Upload generic model'}
              </button>
            </div>
          </div>

          <div className="border border-border-default rounded-lg p-4 bg-bg-surface space-y-3">
            <span className="font-display text-xs text-white uppercase tracking-wider">Personalized models (one client)</span>
            <p className="text-[11px] text-text-muted">
              Only the selected client sees and can activate this row. Path:{' '}
              <code className="text-white/80">&lt;tenant&gt;/clients/&lt;client&gt;/models/…</code>
            </p>
            {perMsg && <p className="text-xs text-amber-400 font-mono">{perMsg}</p>}
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
              <select
                aria-label="FL client for personalized model"
                value={perClientId}
                onChange={(e) => setPerClientId(e.target.value)}
                className="bg-bg-base border border-white/20 rounded px-2 py-1.5 text-xs text-white min-w-[10rem]"
              >
                <option value="">Select FL client…</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nodeName?.trim() || c.department || c.id}
                  </option>
                ))}
              </select>
              <input
                placeholder="Model slug"
                value={perName}
                onChange={(e) => setPerName(e.target.value)}
                className="bg-bg-base border border-white/20 rounded px-2 py-1.5 text-xs font-mono text-white min-w-[12rem]"
              />
              <select
                aria-label="Personalized model type"
                value={perType}
                onChange={(e) => setPerType(e.target.value)}
                className="bg-bg-base border border-white/20 rounded px-2 py-1.5 text-xs text-white"
              >
                {MODEL_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                aria-label="Personalized model weights file"
                title="Model weights file"
                type="file"
                onChange={(e) => setPerFile(e.target.files?.[0] ?? null)}
                className="text-xs text-white file:mr-2 file:rounded file:border-0 file:bg-white file:text-black file:px-2 file:py-1"
              />
              <button
                type="button"
                disabled={perBusy}
                onClick={() => void uploadPersonalized()}
                className="rounded bg-white text-black px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
              >
                {perBusy ? 'Uploading…' : 'Upload personalized model'}
              </button>
            </div>
          </div>

          <div className="border border-dashed border-white/20 rounded-lg p-4 bg-bg-surface space-y-2">
            <span className="font-display text-xs text-white uppercase tracking-wider">Seed bundled globals from disk</span>
            <p className="text-[11px] text-text-muted">
              Reads <code className="text-white/80">backend/data/models/pytorch/global/*.pth</code> and uploads flat keys{' '}
              <code className="text-white/80">global/&lt;filename&gt;</code> plus <code className="text-white/80">drift_reference.npz</code>{' '}
              when present.
            </p>
            {syncMsg && <p className="text-xs text-amber-400 font-mono">{syncMsg}</p>}
            <button
              type="button"
              disabled={syncBusy}
              onClick={() => void syncDiskBundles()}
              className="rounded border border-white/30 text-white px-3 py-1.5 text-xs font-semibold disabled:opacity-50 hover:bg-white/10"
            >
              {syncBusy ? 'Syncing…' : 'Sync global bundles to bucket'}
            </button>
          </div>
        </>
      )}

      <div className="border border-border-default rounded-lg p-3 bg-bg-surface space-y-2">
        <span className="font-mono text-[10px] text-text-muted uppercase">Per-client activate (optional)</span>
        <select
          aria-label="FL client for per-client model activation"
          value={activateClientId}
          onChange={(e) => setActivateClientId(e.target.value)}
          className="bg-bg-base border border-white/20 rounded px-2 py-1.5 text-xs text-white max-w-xs"
        >
          <option value="">Tenant default (owner/admin)</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nodeName?.trim() || c.department || c.id}
            </option>
          ))}
        </select>
      </div>

      <div>
        <span className="font-display text-xs text-white uppercase tracking-wider">Tenant &amp; global models</span>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
          {tenantWide.map((m) => {
            const isActive = m.name === activeModel;
            const loading = switching === m.name;
            return (
              <div
                key={m.name}
                className={`bg-bg-surface rounded-lg p-4 flex flex-col gap-3 ${
                  isActive ? 'border-2 border-white' : 'border border-border-default'
                }`}
              >
                <div className="flex justify-between items-start gap-2">
                  <span className="font-mono text-sm text-white break-all">{m.name}</span>
                  <span className="font-mono text-xs text-white shrink-0">{m.accuracy}%</span>
                </div>
                <p className="text-xs text-text-secondary flex-1 line-clamp-4">{m.description}</p>
                <div className="flex gap-1 flex-wrap">
                  <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full border border-border-strong text-text-secondary">
                    {m.modelScope ?? 'tenant'}
                  </span>
                  <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full border border-border-strong text-text-secondary">
                    {m.type}
                  </span>
                </div>
                <button
                  type="button"
                  disabled={isActive || loading || isDevMode}
                  onClick={() => void handleActivate(m.name)}
                  className={`mt-1 py-1.5 rounded-md text-xs font-medium transition-colors disabled:cursor-not-allowed ${
                    isActive
                      ? 'bg-white text-black'
                      : 'border border-border-default text-white hover:bg-bg-overlay disabled:opacity-50'
                  }`}
                >
                  {loading ? 'Switching…' : isActive ? 'Active' : 'Activate'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {perClient.length > 0 && (
        <div>
          <span className="font-display text-xs text-white uppercase tracking-wider">Client-scoped models</span>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
            {perClient.map((m) => {
              const isActive = m.name === activeModel;
              const loading = switching === m.name;
              return (
                <div
                  key={m.name}
                  className={`rounded-lg p-4 flex flex-col gap-2 ${
                    isActive ? 'border-2 border-white bg-bg-surface' : 'border border-border-default bg-white/[0.01]'
                  }`}
                >
                  <span className="font-mono text-xs text-white">{m.name}</span>
                  <span className="text-[10px] text-text-muted font-mono">client: {m.flClientId}</span>
                  <p className="text-xs text-text-secondary line-clamp-3">{m.description}</p>
                  <button
                    type="button"
                    disabled={isActive || loading || isDevMode}
                    onClick={() => void handleActivate(m.name, m.flClientId ?? null)}
                    className="py-1.5 rounded-md text-xs border border-border-default text-white hover:bg-bg-overlay disabled:opacity-50"
                  >
                    {loading ? '…' : isActive ? 'Active' : 'Activate for this client'}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
