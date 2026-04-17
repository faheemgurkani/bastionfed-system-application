'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { StorageBucketsPanel } from '@/components/storage/StorageBucketsPanel';
import { ClientArtifactsSection } from '@/components/storage/ClientArtifactsSection';
import { SampleList } from '@/components/forensics/SampleList';
import { AnalysisReport } from '@/components/forensics/AnalysisReport';
import { MalwareSample } from '@/lib/types';
import { useAuth } from '@/contexts/auth-context';
import { useViewMode } from '@/contexts/view-mode-context';
import { apiFetchJson, apiUrl, ApiError, getClientViewIdsForRequests, isAbortError } from '@/lib/api';

type SampleListResponse = {
  items: MalwareSample[];
  nextCursor: string | null;
  total: number;
};

type AnalyzeResult = {
  prediction: 'MALWARE' | 'BENIGN';
  confidence: number;
  threatScore: number;
  imgProb: number | null;
  dnnProb: number | null;
  modelUsed: string;
  dnnAvailable: boolean;
  sha256: string | null;
  alertId?: string | null;
  incidentId?: string | null;
  alertSkippedReason?: string | null;
};

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

const DEV_REGISTRY_MODELS: RegistryModel[] = [
  { name: 'fl-meta-v1', type: 'fusion', accuracy: 0, fpRate: 0, size: '', trainedOn: '', description: 'Global fusion', active: true, flClientId: null, modelScope: 'global' },
  { name: 'fl-resnet-v1', type: 'image', accuracy: 0, fpRate: 0, size: '', trainedOn: '', description: 'Global ResNet', active: false, flClientId: null, modelScope: 'global' },
  { name: 'fl-dnn-v1', type: 'fv', accuracy: 0, fpRate: 0, size: '', trainedOn: '', description: 'Global DNN', active: false, flClientId: null, modelScope: 'global' },
];

export default function ForensicsPage() {
  const { user, loading: authLoading, isDevMode } = useAuth();
  const { viewScopeKey } = useViewMode();
  const [samples, setSamples] = useState<MalwareSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<MalwareSample | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [registryModels, setRegistryModels] = useState<RegistryModel[]>([]);
  const [selectedInferenceModel, setSelectedInferenceModel] = useState<string>('fl-meta-v1');
  const [modelsLoadError, setModelsLoadError] = useState<string | null>(null);

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [fvFile, setFvFile] = useState<File | null>(null);
  const [imgDragOver, setImgDragOver] = useState(false);
  const [fvDragOver, setFvDragOver] = useState(false);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const fvInputRef = useRef<HTMLInputElement>(null);

  const inputReq = useMemo(() => {
    const m = registryModels.find((x) => x.name === selectedInferenceModel);
    const t = (m?.type || '').toLowerCase();
    if (t === 'image') return { image: true, fv: false, label: 'Image (ResNet)' };
    if (t === 'fv') return { image: false, fv: true, label: 'Feature vector (DNN)' };
    if (t === 'fusion') return { image: true, fv: true, label: 'Fusion (image + / or FV)' };
    return { image: true, fv: true, label: 'Fusion (image + / or FV)' };
  }, [registryModels, selectedInferenceModel]);

  const showImage = inputReq.image;
  const showFV = inputReq.fv;

  const hasImage = !!imageFile;
  const hasFV = !!fvFile;
  const canSubmit = !analyzing && (
    (showImage && showFV && (hasImage || hasFV)) ||
    (showImage && !showFV && hasImage) ||
    (!showImage && showFV && hasFV)
  );

  async function runAnalysis() {
    setAnalyzing(true);
    setAnalyzeResult(null);
    setAnalyzeError(null);
    try {
      const formData = new FormData();
      if (showImage && imageFile) formData.append('file', imageFile);
      if (showFV && fvFile) formData.append('fv_file', fvFile);
      const modelParam = encodeURIComponent(selectedInferenceModel);
      const url = isDevMode
        ? apiUrl('/api/forensics/analyze') + `?dev=true&model=${modelParam}`
        : apiUrl('/api/forensics/analyze') + `?model=${modelParam}`;
      const headers: Record<string, string> = {};
      if (!isDevMode && user) {
        headers['Authorization'] = `Bearer ${await user.getIdToken()}`;
      }
      const cv = getClientViewIdsForRequests();
      if (cv && !isDevMode) {
        headers['X-Client-View-Ids'] = cv;
      }
      const res = await fetch(url, { method: 'POST', headers, body: formData });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail?.detail || j?.detail || `HTTP ${res.status}`);
      }
      const data: AnalyzeResult = await res.json();
      setAnalyzeResult(data);
    } catch (e) {
      setAnalyzeError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  }

  function clearInputs() {
    setImageFile(null);
    setFvFile(null);
    setAnalyzeResult(null);
    setAnalyzeError(null);
    if (imgInputRef.current) imgInputRef.current.value = '';
    if (fvInputRef.current) fvInputRef.current.value = '';
  }

  useEffect(() => {
    if (authLoading) return;
    const ac = new AbortController();
    async function loadModelsAndStatus() {
      setModelsLoadError(null);
      try {
        if (isDevMode) {
          const statusData = await apiFetchJson<{ activeModel: string }>('/api/fl/status', {
            devMode: true,
            signal: ac.signal,
          });
          let list = DEV_REGISTRY_MODELS;
          try {
            const modelsData = await apiFetchJson<{ models: RegistryModel[] }>('/api/fl/models', {
              devMode: true,
              signal: ac.signal,
            });
            if (modelsData.models?.length) list = modelsData.models;
          } catch {
            /* demo tenant may have empty registry */
          }
          setRegistryModels(list);
          setSelectedInferenceModel((prev) => {
            if (prev && list.some((x) => x.name === prev)) return prev;
            const am = statusData.activeModel;
            if (am && list.some((x) => x.name === am)) return am;
            return list[0]?.name ?? 'fl-meta-v1';
          });
          return;
        }
        if (!user) {
          setRegistryModels([]);
          return;
        }
        const token = await user.getIdToken();
        const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
        const cv = getClientViewIdsForRequests();
        if (cv) headers['X-Client-View-Ids'] = cv;
        const [statusData, modelsData] = await Promise.all([
          apiFetchJson<{ activeModel: string }>('/api/fl/status', { headers, signal: ac.signal }),
          apiFetchJson<{ models: RegistryModel[] }>('/api/fl/models', { headers, signal: ac.signal }),
        ]);
        let list = modelsData.models ?? [];
        if (!list.length) {
          list = DEV_REGISTRY_MODELS;
        }
        setRegistryModels(list);
        setSelectedInferenceModel((prev) => {
          if (prev && list.some((x) => x.name === prev)) return prev;
          const am = statusData.activeModel;
          if (am && list.some((x) => x.name === am)) return am;
          const fusion = list.find((x) => (x.type || '').toLowerCase() === 'fusion');
          return fusion?.name ?? list[0]?.name ?? prev;
        });
      } catch (e) {
        if (isAbortError(e)) return;
        setModelsLoadError(e instanceof ApiError ? e.message : 'Failed to load models');
        setRegistryModels(DEV_REGISTRY_MODELS);
        setSelectedInferenceModel('fl-meta-v1');
      }
    }
    void loadModelsAndStatus();
    return () => ac.abort();
  }, [authLoading, isDevMode, user, viewScopeKey]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();
    async function load() {
      setError(null);
      try {
        let data: SampleListResponse;
        if (isDevMode) {
          data = await apiFetchJson<SampleListResponse>('/api/forensics/samples', { devMode: true, signal: ac.signal });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<SampleListResponse>('/api/forensics/samples', { headers: { Authorization: `Bearer ${token}` }, signal: ac.signal });
        } else {
          return;
        }
        if (!cancelled) {
          setSamples(data.items);
          setSelectedSample((prev) => {
            if (prev && data.items.some((s) => s.id === prev.id)) return prev;
            return data.items[0] ?? null;
          });
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Failed to load samples');
      }
    }
    void load();
    return () => { cancelled = true; ac.abort(); };
  }, [authLoading, isDevMode, user, viewScopeKey]);

  return (
    <AuthGate>
      <div className="flex flex-col gap-4 h-full">
        {error && (
          <p className="text-sm font-mono text-severity-high px-1">{error}</p>
        )}

        <StorageBucketsPanel />
        <ClientArtifactsSection />

        <div className="border border-border-default bg-white/[0.02] p-4">
          {/* Header row: title */}
          <div className="flex items-center justify-between mb-4">
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              FL Model Inference
            </p>
          </div>

          <div className="mb-4 space-y-2">
            <label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground block">
              Model (from registry)
            </label>
            <select
              value={selectedInferenceModel}
              onChange={(e) => {
                setSelectedInferenceModel(e.target.value);
                setImageFile(null);
                setFvFile(null);
                setAnalyzeResult(null);
                setAnalyzeError(null);
                if (imgInputRef.current) imgInputRef.current.value = '';
                if (fvInputRef.current) fvInputRef.current.value = '';
              }}
              className="bg-bg-surface border border-border-default rounded px-3 py-2 font-mono text-sm text-white focus:outline-none focus:border-border-strong cursor-pointer appearance-none w-full max-w-md"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='white' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 12px center',
              }}
            >
              {registryModels.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                  {m.flClientId ? ` · ${m.flClientId}` : ''} ({m.type})
                  {m.active ? ' · active' : ''}
                </option>
              ))}
            </select>
            <p className="font-mono text-[10px] text-muted-foreground">
              Inputs: {inputReq.label}
            </p>
            {modelsLoadError && (
              <p className="font-mono text-[10px] text-amber-400">{modelsLoadError}</p>
            )}
          </div>

          {/* Upload Zones */}
          <div className={`grid gap-4 ${showImage && showFV ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}`}>

            {/* Image Upload */}
            {showImage && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
                  Image Branch — Bi-gram DCT PNG
                </p>
                <div
                  className={`border-2 border-dashed rounded p-5 text-center cursor-pointer transition-colors ${
                    imgDragOver ? 'border-accent bg-accent/5' :
                    imageFile ? 'border-green-500/50 bg-green-500/5' :
                    'border-border-default hover:border-border-strong'
                  }`}
                  onClick={() => imgInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setImgDragOver(true); }}
                  onDragLeave={() => setImgDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setImgDragOver(false);
                    const f = e.dataTransfer.files[0];
                    if (f) setImageFile(f);
                  }}
                >
                  <input
                    ref={imgInputRef}
                    type="file"
                    accept="image/png"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) setImageFile(f); }}
                  />
                  {imageFile ? (
                    <div>
                      <p className="font-mono text-sm text-green-400">{imageFile.name}</p>
                      <p className="font-mono text-[10px] text-muted-foreground mt-1">{(imageFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <p className="font-mono text-sm text-muted-foreground">
                      Drop <span className="text-foreground">*_bigram_dct.png</span> here or click
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* FV Upload */}
            {showFV && (
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
                  FV Branch — 320-dim Feature Vector
                </p>
                <div
                  className={`border-2 border-dashed rounded p-5 text-center cursor-pointer transition-colors ${
                    fvDragOver ? 'border-accent bg-accent/5' :
                    fvFile ? 'border-green-500/50 bg-green-500/5' :
                    'border-border-default hover:border-border-strong'
                  }`}
                  onClick={() => fvInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setFvDragOver(true); }}
                  onDragLeave={() => setFvDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setFvDragOver(false);
                    const f = e.dataTransfer.files[0];
                    if (f) setFvFile(f);
                  }}
                >
                  <input
                    ref={fvInputRef}
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) setFvFile(f); }}
                  />
                  {fvFile ? (
                    <div>
                      <p className="font-mono text-sm text-green-400">{fvFile.name}</p>
                      <p className="font-mono text-[10px] text-muted-foreground mt-1">{(fvFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <p className="font-mono text-sm text-muted-foreground">
                      Drop <span className="text-foreground">.json</span> with 320 floats or click
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 mt-4">
            <button
              type="button"
              disabled={!canSubmit}
              onClick={runAnalysis}
              className="px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider transition-colors disabled:cursor-not-allowed bg-white text-black hover:bg-white/90 disabled:opacity-30"
            >
              {analyzing ? 'Running inference...' : 'Run Inference'}
            </button>
            <button
              type="button"
              onClick={clearInputs}
              className="px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider border border-border-default text-muted-foreground hover:text-white hover:border-border-strong transition-colors"
            >
              Clear
            </button>
          </div>

          {analyzeError && (
            <p className="mt-3 text-sm font-mono text-red-400">{analyzeError}</p>
          )}

          {analyzeResult && (
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className={`border p-3 ${analyzeResult.prediction === 'MALWARE' ? 'border-red-500/50 bg-red-500/5' : 'border-green-500/50 bg-green-500/5'}`}>
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Prediction</p>
                <p className={`font-mono text-lg font-bold mt-1 ${analyzeResult.prediction === 'MALWARE' ? 'text-red-400' : 'text-green-400'}`}>
                  {analyzeResult.prediction}
                </p>
              </div>
              <div className="border border-border-default p-3">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Confidence</p>
                <p className="font-mono text-lg font-bold mt-1">{analyzeResult.confidence.toFixed(1)}%</p>
              </div>
              <div className="border border-border-default p-3">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Threat Score</p>
                <p className="font-mono text-lg font-bold mt-1">{analyzeResult.threatScore.toFixed(1)}</p>
              </div>
              <div className="border border-border-default p-3">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Model</p>
                <p className="font-mono text-xs font-bold mt-1 break-all">{analyzeResult.modelUsed}</p>
              </div>
              {analyzeResult.imgProb != null && (
                <div className="border border-border-default p-3 col-span-2">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">ResNet Prob</p>
                  <p className="font-mono text-sm mt-1">{(analyzeResult.imgProb * 100).toFixed(2)}%</p>
                </div>
              )}
              {analyzeResult.dnnProb != null && (
                <div className="border border-border-default p-3 col-span-2">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    DNN Prob {!analyzeResult.dnnAvailable && <span className="text-yellow-500">(no FV)</span>}
                  </p>
                  <p className="font-mono text-sm mt-1">{(analyzeResult.dnnProb * 100).toFixed(2)}%</p>
                </div>
              )}
              {analyzeResult.sha256 && (
                <div className="border border-border-default p-3 col-span-4">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">SHA256</p>
                  <p className="font-mono text-[10px] mt-1 break-all text-muted-foreground">{analyzeResult.sha256}</p>
                </div>
              )}
              {analyzeResult.alertId && (
                <div className="border border-green-500/40 bg-green-500/5 p-3 col-span-4">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Security alert</p>
                  <p className="font-mono text-sm text-green-400 mt-1">
                    Recorded <span className="text-white">{analyzeResult.alertId}</span>
                    {analyzeResult.incidentId ? ` · Incident ${analyzeResult.incidentId}` : ''} — visible on Alerts.
                  </p>
                </div>
              )}
              {analyzeResult.alertSkippedReason && (
                <div className="border border-border-default bg-white/[0.03] p-3 col-span-4">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Why no new alert</p>
                  <p className="font-mono text-xs text-muted-foreground mt-1 leading-relaxed">{analyzeResult.alertSkippedReason}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Existing samples list */}
        <div className="flex gap-6 flex-1 min-h-0">
          <div className="w-1/3 min-w-[320px] h-full">
            <SampleList
              samples={samples}
              selectedId={selectedSample?.id}
              onSelect={setSelectedSample}
            />
          </div>
          <div className="flex-1 h-full overflow-hidden">
            {selectedSample ? (
              <AnalysisReport sample={selectedSample} />
            ) : (
              <div className="text-text-muted text-sm p-6">No samples loaded.</div>
            )}
          </div>
        </div>
      </div>
    </AuthGate>
  );
}
