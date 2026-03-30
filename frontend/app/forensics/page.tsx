'use client';

import { useState, useEffect, useRef } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { SampleList } from '@/components/forensics/SampleList';
import { AnalysisReport } from '@/components/forensics/AnalysisReport';
import { MalwareSample } from '@/lib/types';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, apiUrl, ApiError, isAbortError } from '@/lib/api';

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
};

type InferenceMode = 'image' | 'fv' | 'both';

const MODE_LABELS: Record<InferenceMode, string> = {
  image: 'Image Only (ResNet)',
  fv: 'Feature Vector Only (DNN)',
  both: 'Both Modalities (Meta-Fusion)',
};

export default function ForensicsPage() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [samples, setSamples] = useState<MalwareSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<MalwareSample | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [activeModel, setActiveModel] = useState<string>('fl-meta-v1');

  const [mode, setMode] = useState<InferenceMode>('both');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [fvFile, setFvFile] = useState<File | null>(null);
  const [imgDragOver, setImgDragOver] = useState(false);
  const [fvDragOver, setFvDragOver] = useState(false);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const fvInputRef = useRef<HTMLInputElement>(null);

  const showImage = mode === 'image' || mode === 'both';
  const showFV = mode === 'fv' || mode === 'both';

  const hasImage = !!imageFile;
  const hasFV = !!fvFile;
  const canSubmit = !analyzing && (
    (mode === 'image' && hasImage) ||
    (mode === 'fv' && hasFV) ||
    (mode === 'both' && (hasImage || hasFV))
  );

  async function runAnalysis() {
    setAnalyzing(true);
    setAnalyzeResult(null);
    setAnalyzeError(null);
    try {
      const formData = new FormData();
      if (showImage && imageFile) formData.append('file', imageFile);
      if (showFV && fvFile) formData.append('fv_file', fvFile);
      const url = isGuest
        ? apiUrl('/api/forensics/analyze') + '?guest=true'
        : apiUrl('/api/forensics/analyze');
      const headers: Record<string, string> = {};
      if (!isGuest && user) {
        headers['Authorization'] = `Bearer ${await user.getIdToken()}`;
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

  function handleModeChange(newMode: InferenceMode) {
    setMode(newMode);
    clearInputs();
  }

  useEffect(() => {
    if (authLoading) return;
    const ac = new AbortController();
    async function fetchModel() {
      try {
        const data = isGuest
          ? await apiFetchJson<{ activeModel: string }>('/api/fl/status', { guest: true, signal: ac.signal })
          : user
            ? await apiFetchJson<{ activeModel: string }>('/api/fl/status', {
                headers: { Authorization: `Bearer ${await user.getIdToken()}` },
                signal: ac.signal,
              })
            : null;
        if (data) {
          setActiveModel(data.activeModel);
          const m = data.activeModel;
          if (m.includes('resnet')) setMode('image');
          else if (m.includes('dnn')) setMode('fv');
          else setMode('both');
        }
      } catch (e) {
        if (!isAbortError(e)) console.warn('Failed to fetch active model', e);
      }
    }
    void fetchModel();
    return () => ac.abort();
  }, [authLoading, isGuest, user]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();
    async function load() {
      setError(null);
      try {
        let data: SampleListResponse;
        if (isGuest) {
          data = await apiFetchJson<SampleListResponse>('/api/forensics/samples', { guest: true, signal: ac.signal });
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
  }, [authLoading, isGuest, user]);

  return (
    <AuthGate>
      <div className="flex flex-col gap-4 h-full">
        {error && (
          <p className="text-sm font-mono text-severity-high px-1">{error}</p>
        )}

        <div className="border border-white/10 bg-white/[0.02] p-4">
          {/* Header row: title + active model badge */}
          <div className="flex items-center justify-between mb-4">
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              FL Model Inference
            </p>
            <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 border border-white/20 bg-white/5 text-white">
              Active: {activeModel}
            </span>
          </div>

          {/* Inference Mode Dropdown */}
          <div className="mb-4">
            <label className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground block mb-2">
              Inference Mode
            </label>
            <select
              value={mode}
              onChange={(e) => handleModeChange(e.target.value as InferenceMode)}
              className="bg-bg-surface border border-white/20 rounded px-3 py-2 font-mono text-sm text-white focus:outline-none focus:border-white/40 cursor-pointer appearance-none w-full max-w-xs"
              style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='white' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center' }}
            >
              <option value="image">{MODE_LABELS.image}</option>
              <option value="fv">{MODE_LABELS.fv}</option>
              <option value="both">{MODE_LABELS.both}</option>
            </select>
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
                    'border-white/20 hover:border-white/40'
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
                    'border-white/20 hover:border-white/40'
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
              className="px-4 py-2 rounded-md font-mono text-xs uppercase tracking-wider border border-white/20 text-muted-foreground hover:text-white hover:border-white/40 transition-colors"
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
              <div className="border border-white/10 p-3">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Confidence</p>
                <p className="font-mono text-lg font-bold mt-1">{analyzeResult.confidence.toFixed(1)}%</p>
              </div>
              <div className="border border-white/10 p-3">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Threat Score</p>
                <p className="font-mono text-lg font-bold mt-1">{analyzeResult.threatScore.toFixed(1)}</p>
              </div>
              <div className="border border-white/10 p-3">
                <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Model</p>
                <p className="font-mono text-xs font-bold mt-1 break-all">{analyzeResult.modelUsed}</p>
              </div>
              {analyzeResult.imgProb != null && (
                <div className="border border-white/10 p-3 col-span-2">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">ResNet Prob</p>
                  <p className="font-mono text-sm mt-1">{(analyzeResult.imgProb * 100).toFixed(2)}%</p>
                </div>
              )}
              {analyzeResult.dnnProb != null && (
                <div className="border border-white/10 p-3 col-span-2">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    DNN Prob {!analyzeResult.dnnAvailable && <span className="text-yellow-500">(no FV)</span>}
                  </p>
                  <p className="font-mono text-sm mt-1">{(analyzeResult.dnnProb * 100).toFixed(2)}%</p>
                </div>
              )}
              {analyzeResult.sha256 && (
                <div className="border border-white/10 p-3 col-span-4">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">SHA256</p>
                  <p className="font-mono text-[10px] mt-1 break-all text-muted-foreground">{analyzeResult.sha256}</p>
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
