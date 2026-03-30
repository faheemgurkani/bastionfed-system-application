'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { apiFetchJson, apiUrl, ApiError, isAbortError } from '@/lib/api';

type FLStatusPartial = {
  activeModel: string;
  modelZoo: string[];
};

type ModelInfo = { accuracy: string; desc: string; tags: string[] };

const GLOBAL_META: Record<string, ModelInfo> = {
  'fl-meta-v1': {
    accuracy: '88.1%',
    desc: 'Federated meta-fusion model combining ResNet50 image branch and DeepDNN FV branch via learned weighted fusion.',
    tags: ['Fusion', 'FL-FedAvg', 'Global'],
  },
  'fl-resnet-v1': {
    accuracy: '85.3%',
    desc: 'ResNet50 backbone trained on bi-gram DCT malware visualization images. Image-only branch.',
    tags: ['Image', 'ResNet50', 'Global'],
  },
  'fl-dnn-v1': {
    accuracy: '84.0%',
    desc: 'Deep Neural Network operating on 320 statistical features from PE/network logs. FV-only branch.',
    tags: ['FV', 'DNN', 'Global'],
  },
};

const CLIENT_LABELS: Record<number, string> = {
  1: 'Hospital-A',
  2: 'Hospital-B',
  3: 'Hospital-C',
  4: 'Hospital-D',
};

const BRANCH_META: Record<string, { accuracy: string; desc: string; tag: string }> = {
  meta:   { accuracy: '87.2%', desc: 'Local meta-fusion (ResNet + DNN) trained on this client\'s data partition.', tag: 'Fusion' },
  resnet: { accuracy: '84.8%', desc: 'Local ResNet50 trained on this client\'s bi-gram DCT images.', tag: 'Image' },
  dnn:    { accuracy: '83.5%', desc: 'Local DNN trained on this client\'s 320-dim feature vectors.', tag: 'FV' },
};

function isGlobalModel(name: string) {
  return name.startsWith('fl-');
}

function parseClientModel(name: string): { clientId: number; branch: string } | null {
  const m = name.match(/^client-(\d+)-(meta|resnet|dnn)$/);
  if (!m) return null;
  return { clientId: parseInt(m[1]), branch: m[2] };
}

export function ModelZoo() {
  const { user, loading: authLoading, isGuest } = useAuth();
  const [activeModel, setActiveModel] = useState<string>('fl-meta-v1');
  const [modelZoo, setModelZoo] = useState<string[]>([]);
  const [switching, setSwitching] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    const ac = new AbortController();

    async function load() {
      try {
        let data: FLStatusPartial;
        if (isGuest) {
          data = await apiFetchJson<FLStatusPartial>('/api/fl/status', { guest: true, signal: ac.signal });
        } else if (user) {
          const token = await user.getIdToken();
          data = await apiFetchJson<FLStatusPartial>('/api/fl/status', {
            headers: { Authorization: `Bearer ${token}` },
            signal: ac.signal,
          });
        } else {
          return;
        }
        if (!cancelled) {
          setActiveModel(data.activeModel);
          if (data.modelZoo?.length) setModelZoo(data.modelZoo);
        }
      } catch (e) {
        if (isAbortError(e)) return;
        if (!cancelled && e instanceof ApiError) console.warn('FL status:', e.message);
      }
    }

    void load();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [authLoading, isGuest, user]);

  async function handleActivate(modelName: string) {
    if (modelName === activeModel || isGuest) return;
    setSwitching(modelName);
    try {
      const token = user ? await user.getIdToken() : null;
      const res = await fetch(apiUrl(`/api/fl/models/${modelName}/activate`), {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        setActiveModel(modelName);
      }
    } catch {
      // ignore
    } finally {
      setSwitching(null);
    }
  }

  const globalModels = modelZoo.filter(isGlobalModel).sort();

  const clientGroups: Record<number, string[]> = {};
  for (const name of modelZoo) {
    const parsed = parseClientModel(name);
    if (!parsed) continue;
    if (!clientGroups[parsed.clientId]) clientGroups[parsed.clientId] = [];
    clientGroups[parsed.clientId].push(name);
  }
  const sortedClientIds = Object.keys(clientGroups).map(Number).sort();

  function renderCard(name: string, meta: ModelInfo) {
    const isActive = name === activeModel;
    const isLoading = switching === name;
    return (
      <div
        key={name}
        className={`bg-bg-surface rounded-lg p-4 flex flex-col gap-3 transition-colors ${
          isActive ? 'border-2 border-white' : 'border border-border-default'
        }`}
      >
        <div className="flex justify-between items-start">
          <span className="font-mono text-sm text-white">{name}</span>
          <span className="font-mono text-sm text-white">{meta.accuracy}</span>
        </div>
        <p className="text-xs text-text-secondary flex-1">{meta.desc}</p>
        <div className="flex gap-1.5 flex-wrap">
          {meta.tags.map((t) => (
            <span key={t} className="border border-border-strong bg-bg-overlay text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full text-text-secondary">
              {t}
            </span>
          ))}
        </div>
        <button
          type="button"
          disabled={isActive || isLoading || isGuest}
          onClick={() => handleActivate(name)}
          className={`mt-1 py-1.5 rounded-md text-xs font-medium transition-colors disabled:cursor-not-allowed ${
            isActive
              ? 'bg-white text-black'
              : 'border border-border-default text-white hover:bg-bg-overlay disabled:opacity-50'
          }`}
        >
          {isLoading ? 'Switching...' : isActive ? 'Active' : 'Activate'}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Global Models */}
      <div>
        <span className="font-display text-xs text-white uppercase tracking-wider">Global Models (FedAvg)</span>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
          {globalModels.map((name) => {
            const meta = GLOBAL_META[name] ?? { accuracy: 'N/A', desc: name, tags: ['Global'] };
            return renderCard(name, meta);
          })}
        </div>
      </div>

      {/* Client-Specific Models */}
      {sortedClientIds.length > 0 && (
        <div>
          <span className="font-display text-xs text-white uppercase tracking-wider">Client-Specific Models (Personalized)</span>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
            {sortedClientIds.map((cid) => {
              const models = clientGroups[cid].sort();
              return (
                <div key={cid} className="border border-border-default rounded-lg p-4 bg-white/[0.01]">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-2 h-2 rounded-full bg-white" />
                    <span className="font-mono text-xs text-white uppercase tracking-wider">
                      Client-{cid} · {CLIENT_LABELS[cid] ?? `Client ${cid}`}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {models.map((name) => {
                      const parsed = parseClientModel(name);
                      if (!parsed) return null;
                      const bm = BRANCH_META[parsed.branch];
                      const meta: ModelInfo = bm
                        ? { accuracy: bm.accuracy, desc: bm.desc, tags: [bm.tag, `Client-${cid}`] }
                        : { accuracy: 'N/A', desc: name, tags: [`Client-${cid}`] };
                      return renderCard(name, meta);
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
