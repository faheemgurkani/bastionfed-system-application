'use client';

import { Alert } from '@/lib/types';
import { X, ShieldAlert, Activity, Search } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { useAlertsContext } from '@/contexts/alerts-context';
import { apiFetchJson, ApiError } from '@/lib/api';
import { confidencePercent } from '@/lib/alertDisplay';

interface AlertDetailDrawerProps {
  alert: Alert;
  onClose: () => void;
}

export function AlertDetailDrawer({ alert, onClose }: AlertDetailDrawerProps) {
  const { user, isDevMode } = useAuth();
  const { replaceAlert } = useAlertsContext();
  const [activeTab, setActiveTab] = useState('summary');
  const [localAlert, setLocalAlert] = useState(alert);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setLocalAlert(alert);
    setActionError(null);
  }, [alert]);

  const applyUpdate = (next: Alert) => {
    setLocalAlert(next);
    replaceAlert(next);
  };

  async function patchStatus(status: Alert['status']) {
    setActionError(null);
    if (isDevMode || !user) {
      setActionError('Sign in to change alert status.');
      return;
    }
    setBusy(true);
    try {
      const token = await user.getIdToken();
      const updated = await apiFetchJson<Alert>(`/api/alerts/${encodeURIComponent(localAlert.id)}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      applyUpdate(updated);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Request failed');
    } finally {
      setBusy(false);
    }
  }

  async function quarantineDevice() {
    setActionError(null);
    if (isDevMode || !user) {
      setActionError('Sign in to quarantine devices.');
      return;
    }
    setBusy(true);
    try {
      const token = await user.getIdToken();
      await apiFetchJson(`/api/devices/${encodeURIComponent(localAlert.deviceId)}/quarantine`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      applyUpdate({
        ...localAlert,
        device: { ...localAlert.device, status: 'ISOLATED' },
      });
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Quarantine failed');
    } finally {
      setBusy(false);
    }
  }

  const alertDisplay = localAlert;
  const confPct = confidencePercent(alertDisplay.confidence);

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
          <span className="font-mono text-sm text-text-muted">{alertDisplay.id}</span>
          <span className="font-display text-sm text-white uppercase tracking-wider">{alertDisplay.type}</span>
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
                <span className="font-mono text-2xl text-white">{Math.round(confPct * 100) / 100}%</span>
              </div>
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Severity</span>
                <span className="font-mono text-lg text-white">{alertDisplay.severity}</span>
              </div>
            </div>
            
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">Feature Summary</span>
              <p className="text-sm text-text-secondary leading-relaxed bg-bg-base border border-border-default p-4 rounded-md">
                {alertDisplay.featureSummary}
              </p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Model Version</span>
                <span className="font-mono text-sm text-white">{alertDisplay.modelVersion}</span>
              </div>
              <div>
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Timestamp</span>
                <span className="font-mono text-sm text-white">{new Date(alertDisplay.timestamp).toLocaleString()}</span>
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
                  <span className="text-sm text-white font-medium">{alertDisplay.device.name}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">IP Address</span>
                  <span className="font-mono text-sm text-white">{alertDisplay.device.ip}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Type</span>
                  <span className="text-sm text-text-secondary">{alertDisplay.device.type}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Hospital Wing</span>
                  <span className="text-sm text-text-secondary">{alertDisplay.device.wing}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">FL Client ID</span>
                  <span className="font-mono text-sm text-white">{alertDisplay.device.flClientId}</span>
                </div>
                <div>
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-1">Criticality</span>
                  <div className="flex gap-1 mt-1">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <div key={i} className={`w-3 h-3 rounded-full ${i < alertDisplay.device.criticality ? 'bg-white' : 'bg-border-strong'}`} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'threat' && (
          <div className="space-y-6">
            {alertDisplay.cveReference && (
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">CVE Reference</span>
                <span className="font-mono text-sm text-white bg-bg-overlay px-2 py-1 rounded border border-border-strong">{alertDisplay.cveReference}</span>
              </div>
            )}
            
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-3">Indicators of Compromise (IoC)</span>
              <div className="space-y-3">
                {alertDisplay.threatIntel.map((intel, i) => (
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
                  const isActive = tactic === alertDisplay.tactic;
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
                            Detected: {alertDisplay.technique.id} - {alertDisplay.technique.name}
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
            {actionError && (
              <p className="text-sm font-mono text-severity-high bg-bg-base border border-border-default rounded p-3">{actionError}</p>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => void quarantineDevice()}
              className="w-full py-3 bg-white text-black font-medium rounded-md hover:bg-interactive-hover transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <ShieldAlert className="w-4 h-4" />
              Quarantine Device
            </button>
            <button
              type="button"
              disabled
              className="w-full py-3 bg-bg-base border border-border-default text-text-muted font-medium rounded-md cursor-not-allowed flex items-center justify-center gap-2"
              title="Use FastAPI POST /api/network/block-ip when implemented"
            >
              <Activity className="w-4 h-4" />
              Block Source IP
            </button>
            <button
              type="button"
              disabled
              className="w-full py-3 bg-bg-base border border-border-default text-text-muted font-medium rounded-md cursor-not-allowed flex items-center justify-center gap-2"
              title="Use FastAPI POST /api/alerts/{id}/escalate when implemented"
            >
              <Search className="w-4 h-4" />
              Escalate to Incident
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void patchStatus('IN_REVIEW')}
              className="w-full py-3 bg-bg-base border border-border-default text-white font-medium rounded-md hover:bg-bg-overlay transition-colors disabled:opacity-50"
            >
              Mark In Review
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void patchStatus('FALSE_POSITIVE')}
              className="w-full py-3 bg-bg-base border border-border-default text-white font-medium rounded-md hover:bg-bg-overlay transition-colors disabled:opacity-50"
            >
              Mark False Positive
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void patchStatus('RESOLVED')}
              className="w-full py-3 bg-bg-base border border-border-default text-text-muted font-medium rounded-md hover:text-white hover:bg-bg-overlay transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              Close Alert
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
