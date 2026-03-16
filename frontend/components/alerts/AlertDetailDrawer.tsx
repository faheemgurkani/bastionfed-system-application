'use client';

import { Alert } from '@/lib/types';
import { X, ShieldAlert, Activity, Search, FileText, PlayCircle } from 'lucide-react';
import { useState } from 'react';

interface AlertDetailDrawerProps {
  alert: Alert;
  onClose: () => void;
}

export function AlertDetailDrawer({ alert, onClose }: AlertDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState('summary');

  const tabs = [
    { id: 'summary', label: 'Summary' },
    { id: 'device', label: 'Device' },
    { id: 'threat', label: 'Threat Intel' },
    { id: 'attack', label: 'ATT&CK' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'actions', label: 'Actions' },
  ];

  return (
    <div className="fixed inset-y-0 right-0 w-[560px] bg-bg-surface border-l border-border-default shadow-2xl z-50 flex flex-col transform transition-transform duration-300">
      <div className="h-16 border-b border-border-default flex items-center justify-between px-6 bg-bg-base">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-text-muted">{alert.id}</span>
          <span className="font-display text-sm text-white uppercase tracking-wider">{alert.type}</span>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-white transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex border-b border-border-default bg-bg-base px-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab.id
                ? 'border-white text-white'
                : 'border-transparent text-text-secondary hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'summary' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Confidence</span>
                <span className="font-mono text-2xl text-white">{alert.confidence}%</span>
              </div>
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Severity</span>
                <span className="font-mono text-lg text-white">{alert.severity}</span>
              </div>
            </div>
            
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">Feature Summary</span>
              <p className="text-sm text-text-secondary leading-relaxed bg-bg-base border border-border-default p-4 rounded-md">
                {alert.featureSummary}
              </p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Model Version</span>
                <span className="font-mono text-sm text-white">{alert.modelVersion}</span>
              </div>
              <div>
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Timestamp</span>
                <span className="font-mono text-sm text-white">{new Date(alert.timestamp).toLocaleString()}</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'device' && (
          <div className="space-y-6">
            <div className="bg-bg-base border border-border-default p-4 rounded-md space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Device Name</span>
                  <span className="text-sm text-white font-medium">{alert.device.name}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">IP Address</span>
                  <span className="font-mono text-sm text-white">{alert.device.ip}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Type</span>
                  <span className="text-sm text-text-secondary">{alert.device.type}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Hospital Wing</span>
                  <span className="text-sm text-text-secondary">{alert.device.wing}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">FL Client ID</span>
                  <span className="font-mono text-sm text-white">{alert.device.flClientId}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Criticality</span>
                  <div className="flex gap-1 mt-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <div key={i} className={`w-3 h-3 rounded-full ${i < alert.device.criticality ? 'bg-white' : 'bg-border-strong'}`} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'threat' && (
          <div className="space-y-6">
            {alert.cveReference && (
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">CVE Reference</span>
                <span className="font-mono text-sm text-white bg-bg-overlay px-2 py-1 rounded border border-border-strong">{alert.cveReference}</span>
              </div>
            )}
            
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-3">Indicators of Compromise (IoC)</span>
              <div className="space-y-3">
                {alert.threatIntel.map((intel, i) => (
                  <div key={i} className="bg-bg-base border border-border-default p-3 rounded-md flex justify-between items-center">
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-[10px] text-text-muted">{intel.type}</span>
                      <span className="font-mono text-sm text-white">{intel.value}</span>
                    </div>
                    <span className="text-xs text-text-secondary border border-border-strong px-2 py-1 rounded bg-bg-overlay">{intel.source}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'attack' && (
          <div className="space-y-6">
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-3">Tactic Chain</span>
              <div className="flex flex-col gap-2">
                {['Initial Access', 'Execution', 'Persistence', 'Lateral Movement', 'Exfiltration', 'Impact'].map((tactic, i) => {
                  const isActive = tactic === alert.tactic;
                  return (
                    <div key={tactic} className="flex items-center gap-3">
                      <div className="w-6 flex justify-center">
                        {i > 0 && <div className="w-0.5 h-4 bg-border-strong -mt-6 absolute" />}
                        <div className={`w-2 h-2 rounded-full z-10 ${isActive ? 'bg-white' : 'bg-border-strong'}`} />
                      </div>
                      <div className={`flex-1 p-3 rounded-md border ${isActive ? 'bg-bg-overlay border-white' : 'bg-bg-base border-border-default'}`}>
                        <span className={`text-sm ${isActive ? 'text-white font-medium' : 'text-text-secondary'}`}>{tactic}</span>
                        {isActive && (
                          <div className="mt-2 text-xs text-text-muted font-mono">
                            Detected: {alert.technique.id} - {alert.technique.name}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'actions' && (
          <div className="space-y-4">
            <button className="w-full py-3 bg-white text-black font-medium rounded-md hover:bg-interactive-hover transition-colors flex items-center justify-center gap-2">
              <ShieldAlert className="w-4 h-4" />
              Quarantine Device
            </button>
            <button className="w-full py-3 bg-bg-base border border-border-default text-white font-medium rounded-md hover:bg-bg-overlay transition-colors flex items-center justify-center gap-2">
              <Activity className="w-4 h-4" />
              Block Source IP
            </button>
            <button className="w-full py-3 bg-bg-base border border-border-default text-white font-medium rounded-md hover:bg-bg-overlay transition-colors flex items-center justify-center gap-2">
              <Search className="w-4 h-4" />
              Escalate to Incident
            </button>
            <button className="w-full py-3 bg-bg-base border border-border-default text-text-muted font-medium rounded-md hover:text-white hover:bg-bg-overlay transition-colors flex items-center justify-center gap-2">
              Close Alert
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
