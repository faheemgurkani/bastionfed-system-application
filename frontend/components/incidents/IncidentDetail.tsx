'use client';

import { Incident } from '@/lib/types';
import { ArrowLeft, Search, Bell, Play, Lock, User, CheckCircle, Loader2, Circle, Download, FileText } from 'lucide-react';
import { useState } from 'react';

interface IncidentDetailProps {
  incident: Incident;
  onBack: () => void;
}

export function IncidentDetail({ incident, onBack }: IncidentDetailProps) {
  const [activeTab, setActiveTab] = useState('overview');

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'playbook', label: 'Playbook' },
    { id: 'evidence', label: 'Evidence' },
    { id: 'ticket', label: 'Ticket' },
  ];

  const getTimelineIcon = (type: string) => {
    switch (type) {
      case 'DETECTION': return <Search className="w-4 h-4 text-white" />;
      case 'ALERT': return <Bell className="w-4 h-4 text-white" />;
      case 'PLAYBOOK_START': return <Play className="w-4 h-4 text-white" />;
      case 'QUARANTINE': return <Lock className="w-4 h-4 text-white" />;
      case 'ANALYST_ASSIGNED': return <User className="w-4 h-4 text-white" />;
      case 'RESOLVED': return <CheckCircle className="w-4 h-4 text-white" />;
      default: return <Circle className="w-4 h-4 text-white" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-bg-surface border border-border-default rounded-lg overflow-hidden">
      <div className="h-16 border-b border-border-default flex items-center px-6 bg-bg-base gap-4">
        <button onClick={onBack} className="text-text-muted hover:text-white transition-colors p-2 -ml-2">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex flex-col">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm text-text-muted">{incident.id}</span>
            <span className="font-display text-sm text-white uppercase tracking-wider">{incident.title}</span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="border border-border-strong bg-bg-overlay text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-full text-white">
            {incident.status.replace('_', ' ')}
          </span>
          <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-full border ${
            incident.severity === 'CRITICAL' ? 'border-severity-critical text-severity-critical' :
            incident.severity === 'HIGH' ? 'border-severity-high text-severity-high' :
            incident.severity === 'MEDIUM' ? 'border-severity-medium text-severity-medium' :
            'border-severity-low text-severity-low'
          }`}>
            {incident.severity}
          </span>
        </div>
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
        {activeTab === 'overview' && (
          <div className="space-y-8 max-w-4xl">
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-3">Summary</span>
              <p className="text-sm text-text-secondary leading-relaxed">
                Incident {incident.id} was automatically created following a {incident.severity} severity alert. 
                The FL Aggregation Server detected anomalous behavioral patterns consistent with known threat signatures. 
                Immediate containment actions have been initiated via the {incident.playbook.name} playbook.
              </p>
            </div>
            
            <div>
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-3">Affected Devices</span>
              <div className="border border-border-default rounded-md overflow-hidden">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-bg-base border-b border-border-default">
                      <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">Device Name</th>
                      <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">IP Address</th>
                      <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">Type</th>
                      <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {incident.affectedDevices.map((dev, i) => (
                      <tr key={i} className="border-b border-border-default last:border-0 bg-bg-surface">
                        <td className="p-3 text-sm text-white font-medium">{dev.name}</td>
                        <td className="p-3 font-mono text-sm text-text-secondary">{dev.ip}</td>
                        <td className="p-3 text-sm text-text-secondary">{dev.type}</td>
                        <td className="p-3">
                          <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                            dev.status === 'COMPROMISED' ? 'border-severity-critical text-severity-critical' :
                            dev.status === 'SUSPICIOUS' ? 'border-severity-high text-severity-high' :
                            'border-border-strong text-text-muted'
                          }`}>
                            {dev.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">Detection Source</span>
                <span className="font-mono text-sm text-white">FL Aggregation Server (Round 47)</span>
              </div>
              <div className="bg-bg-base border border-border-default p-4 rounded-md">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">Time Open</span>
                <span className="font-mono text-sm text-white">{incident.timeOpen}</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="max-w-3xl">
            <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-border-strong before:to-transparent">
              {incident.timeline.map((event, i) => (
                <div key={event.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                  <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white bg-bg-base text-white shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                    {getTimelineIcon(event.type)}
                  </div>
                  <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-bg-base p-4 rounded border border-border-default">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">{event.type.replace('_', ' ')}</span>
                      <span className="font-mono text-[10px] text-text-muted">{new Date(event.timestamp).toLocaleTimeString([], { hour12: false })}</span>
                    </div>
                    <div className="text-sm text-white">{event.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'playbook' && (
          <div className="max-w-3xl space-y-6">
            <div className="flex items-center justify-between bg-bg-base border border-border-default p-4 rounded-md">
              <div className="flex flex-col gap-1">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Active Playbook</span>
                <span className="font-mono text-lg text-white">{incident.playbook.name}</span>
              </div>
              <button className="px-4 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-interactive-hover transition-colors">
                Halt Playbook
              </button>
            </div>
            
            <div className="space-y-3">
              {incident.playbook.steps.map((step) => (
                <div key={step.id} className={`flex items-start gap-4 p-4 rounded-md border ${
                  step.status === 'COMPLETED' ? 'bg-bg-base border-border-default' :
                  step.status === 'RUNNING' ? 'bg-bg-overlay border-white' :
                  'bg-bg-base border-border-default opacity-50'
                }`}>
                  <div className="mt-0.5">
                    {step.status === 'COMPLETED' ? <CheckCircle className="w-5 h-5 text-white" /> :
                     step.status === 'RUNNING' ? <Loader2 className="w-5 h-5 text-white animate-spin" /> :
                     <Circle className="w-5 h-5 text-text-muted" />}
                  </div>
                  <div className="flex-1 flex flex-col gap-1">
                    <div className="flex justify-between items-center">
                      <span className={`text-sm font-medium ${step.status === 'PENDING' ? 'text-text-secondary' : 'text-white'}`}>
                        {step.stepNumber}. {step.name}
                      </span>
                      {step.timestamp && <span className="font-mono text-[11px] text-text-muted">{step.timestamp}</span>}
                    </div>
                    {step.notes && <span className="text-xs text-text-secondary font-mono">{step.notes}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'evidence' && (
          <div className="max-w-4xl space-y-4">
            <span className="font-display text-[10px] text-text-muted uppercase tracking-wider block mb-2">Collected Artifacts</span>
            
            {[
              { name: 'PCAP Dump', size: '45.2 MB', date: '2024-03-14 03:15 UTC' },
              { name: 'System Log', size: '2.1 MB', date: '2024-03-14 03:16 UTC' },
              { name: 'Memory Dump', size: '1.4 GB', date: '2024-03-14 03:20 UTC' },
              { name: 'Malware Binary', size: '842 KB', date: '2024-03-14 03:22 UTC' },
            ].map((artifact, i) => (
              <div key={i} className="flex items-center justify-between bg-bg-base border border-border-default p-4 rounded-md hover:bg-bg-overlay transition-colors">
                <div className="flex items-center gap-4">
                  <FileText className="w-5 h-5 text-text-muted" />
                  <div className="flex flex-col">
                    <span className="text-sm text-white font-medium">{artifact.name}</span>
                    <span className="font-mono text-[10px] text-text-muted">{artifact.date}</span>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <span className="font-mono text-xs text-text-secondary">{artifact.size}</span>
                  <button className="flex items-center gap-2 px-3 py-1.5 border border-border-default rounded text-xs text-white hover:bg-white hover:text-black transition-colors">
                    <Download className="w-3 h-3" /> Download
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'ticket' && (
          <div className="max-w-2xl">
            <div className="bg-bg-base border border-border-default rounded-md overflow-hidden">
              <div className="p-4 border-b border-border-default bg-bg-surface flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-white">{incident.ticketId}</span>
                  <span className="border border-border-strong bg-bg-overlay text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded text-text-secondary">
                    {incident.status}
                  </span>
                </div>
                <button className="text-xs text-white border border-border-default px-3 py-1.5 rounded hover:bg-bg-overlay transition-colors">
                  Open in Jira
                </button>
              </div>
              <div className="p-6 space-y-6">
                <div className="grid grid-cols-2 gap-y-6 gap-x-8">
                  <div className="flex flex-col gap-1">
                    <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Reporter</span>
                    <span className="text-sm text-white">{incident.reporter}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Assignee</span>
                    <span className="text-sm text-white flex items-center gap-2">
                      <div className="w-5 h-5 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[8px] font-bold text-white">
                        {incident.analystInitials}
                      </div>
                      {incident.assignee}
                    </span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Priority</span>
                    <span className="font-mono text-sm text-white">{incident.priority}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Created</span>
                    <span className="font-mono text-sm text-white">{new Date(incident.created).toLocaleString()}</span>
                  </div>
                </div>
                
                <div className="flex flex-col gap-2 pt-4 border-t border-border-default">
                  <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Labels</span>
                  <div className="flex gap-2 flex-wrap">
                    {incident.labels.map(label => (
                      <span key={label} className="border border-border-strong bg-bg-overlay text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded-full text-text-secondary">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
