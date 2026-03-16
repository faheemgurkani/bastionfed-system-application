'use client';

import { useMemo, useState } from 'react';

type Model = {
  name: string;
  accuracy: string;
  desc: string;
  tags: string[];
};

const MODELS: Model[] = [
  {
    name: 'v4.2.1-DNN',
    accuracy: '94.2%',
    desc: 'Deep Neural Network optimized for ransomware behavioral patterns.',
    tags: ['Ransomware', 'High-Conf'],
  },
  {
    name: 'v4.1.0-GNN',
    accuracy: '91.8%',
    desc: 'Graph Neural Network for lateral movement and topology anomalies.',
    tags: ['Lateral Mvmt', 'Topology'],
  },
  {
    name: 'v4.0.5-HYB',
    accuracy: '89.5%',
    desc: 'Legacy ensemble hybrid model. Kept for fallback and baseline comparison.',
    tags: ['Fallback', 'Stable'],
  },
];

export function ModelZoo() {
  const [activeModelName, setActiveModelName] = useState(MODELS[0]?.name ?? '');

  const models = useMemo(
    () => MODELS.map((m) => ({ ...m, active: m.name === activeModelName })),
    [activeModelName],
  );

  return (
    <div className="flex flex-col gap-4">
      <span className="font-display text-xs text-white uppercase tracking-wider">Model Zoo</span>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {models.map((m) => (
          <div
            key={m.name}
            className={`bg-bg-surface rounded-lg p-5 flex flex-col gap-4 transition-colors ${
              m.active ? 'border-2 border-white' : 'border border-border-default'
            }`}
          >
            <div className="flex justify-between items-start">
              <span className="font-display text-lg text-white">{m.name}</span>
              <span className="font-mono text-lg text-white">{m.accuracy}</span>
            </div>
            
            <p className="text-sm text-text-secondary flex-1">{m.desc}</p>
            
            <div className="flex gap-2 flex-wrap">
              {m.tags.map(t => (
                <span key={t} className="border border-border-strong bg-bg-overlay text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-full text-text-secondary">
                  {t}
                </span>
              ))}
            </div>
            
            <button
              type="button"
              onClick={() => setActiveModelName(m.name)}
              className={`mt-2 py-2 rounded-md text-sm font-medium transition-colors ${
                m.active
                  ? 'bg-white text-black'
                  : 'border border-border-default text-white hover:bg-bg-overlay'
              }`}
            >
              {m.active ? 'Active Model' : 'Switch to Active'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
