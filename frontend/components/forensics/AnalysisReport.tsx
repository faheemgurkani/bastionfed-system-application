'use client';

import { MalwareSample } from '@/lib/types';
import { HexViewer } from './HexViewer';
import { ShieldAlert, Activity, FileCode, Network, Database, Cpu } from 'lucide-react';

interface AnalysisReportProps {
  sample: MalwareSample;
}

export function AnalysisReport({ sample }: AnalysisReportProps) {
  return (
    <div className="flex flex-col h-full bg-bg-surface border border-border-default rounded-lg overflow-hidden">
      <div className="p-6 border-b border-border-default bg-bg-base flex justify-between items-start">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-medium text-white">{sample.filename}</h2>
            {sample.threatScore > 80 && (
              <span className="flex items-center gap-1 border border-severity-critical bg-bg-overlay text-severity-critical text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded">
                <ShieldAlert className="w-3 h-3" /> Malicious
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 font-mono text-xs text-text-muted">
            <span>ID: {sample.id}</span>
            <span>Type: {sample.type}</span>
            <span>Size: {sample.size}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Threat Score</span>
          <span className={`text-2xl font-mono ${
            sample.threatScore > 80 ? 'text-severity-critical' :
            sample.threatScore > 50 ? 'text-severity-high' :
            'text-severity-low'
          }`}>
            {sample.threatScore}/100
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        {/* Hashes */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-bg-base border border-border-default p-4 rounded-md flex flex-col gap-1">
            <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">MD5 Hash</span>
            <span className="font-mono text-sm text-white break-all">{sample.md5}</span>
          </div>
          <div className="bg-bg-base border border-border-default p-4 rounded-md flex flex-col gap-1">
            <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">SHA-256 Hash</span>
            <span className="font-mono text-sm text-white break-all">{sample.sha256}</span>
          </div>
        </div>

        {/* Static Analysis */}
        <div>
          <h3 className="font-display text-sm text-white uppercase tracking-wider mb-4 flex items-center gap-2">
            <FileCode className="w-4 h-4" /> Static Analysis
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="border border-border-default rounded-md overflow-hidden">
              <div className="bg-bg-base border-b border-border-default p-2 px-3">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Imported Libraries</span>
              </div>
              <ul className="p-3 space-y-2">
                {sample.analysis.static.imports.map((imp, i) => (
                  <li key={i} className="font-mono text-xs text-text-secondary flex items-center gap-2 before:content-[''] before:w-1 before:h-1 before:bg-border-strong before:rounded-full">
                    {imp}
                  </li>
                ))}
              </ul>
            </div>
            <div className="border border-border-default rounded-md overflow-hidden">
              <div className="bg-bg-base border-b border-border-default p-2 px-3">
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Suspicious Strings</span>
              </div>
              <ul className="p-3 space-y-2">
                {sample.analysis.static.strings.map((str, i) => (
                  <li key={i} className="font-mono text-xs text-severity-high flex items-center gap-2 before:content-[''] before:w-1 before:h-1 before:bg-severity-high before:rounded-full">
                    {str}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Dynamic Analysis */}
        <div>
          <h3 className="font-display text-sm text-white uppercase tracking-wider mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" /> Dynamic Analysis (Sandbox)
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="border border-border-default rounded-md overflow-hidden bg-bg-base">
              <div className="border-b border-border-default p-2 px-3 flex items-center gap-2">
                <Network className="w-3 h-3 text-text-muted" />
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Network Activity</span>
              </div>
              <ul className="p-3 space-y-2">
                {sample.analysis.dynamic.network.map((net, i) => (
                  <li key={i} className="font-mono text-xs text-text-secondary truncate" title={net}>{net}</li>
                ))}
              </ul>
            </div>
            <div className="border border-border-default rounded-md overflow-hidden bg-bg-base">
              <div className="border-b border-border-default p-2 px-3 flex items-center gap-2">
                <Database className="w-3 h-3 text-text-muted" />
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">File System</span>
              </div>
              <ul className="p-3 space-y-2">
                {sample.analysis.dynamic.fileSystem.map((fs, i) => (
                  <li key={i} className="font-mono text-xs text-text-secondary truncate" title={fs}>{fs}</li>
                ))}
              </ul>
            </div>
            <div className="border border-border-default rounded-md overflow-hidden bg-bg-base">
              <div className="border-b border-border-default p-2 px-3 flex items-center gap-2">
                <Cpu className="w-3 h-3 text-text-muted" />
                <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">Processes</span>
              </div>
              <ul className="p-3 space-y-2">
                {sample.analysis.dynamic.processes.map((proc, i) => (
                  <li key={i} className="font-mono text-xs text-text-secondary truncate" title={proc}>{proc}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Hex Viewer */}
        <div>
          <h3 className="font-display text-sm text-white uppercase tracking-wider mb-4">Hex Dump (First 256 bytes)</h3>
          <HexViewer />
        </div>
      </div>
    </div>
  );
}
