'use client';

import { MalwareSample } from '@/lib/types';
import { Search, Filter, Upload } from 'lucide-react';

interface SampleListProps {
  samples: MalwareSample[];
  selectedId?: string | undefined;
  onSelect: (sample: MalwareSample) => void;
}

export function SampleList({ samples, selectedId, onSelect }: SampleListProps) {
  return (
    <div className="flex flex-col h-full bg-bg-surface border border-border-default rounded-lg overflow-hidden">
      <div className="p-4 border-b border-border-default bg-bg-base flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <span className="font-display text-xs text-white uppercase tracking-wider">Malware Samples</span>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-white text-black text-xs font-medium rounded hover:bg-interactive-hover transition-colors">
            <Upload className="w-3 h-3" /> Upload
          </button>
        </div>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Search hashes, names..." 
              className="w-full bg-bg-overlay border border-border-default rounded pl-9 pr-3 py-1.5 text-sm text-white placeholder:text-text-muted focus:outline-none focus:border-white transition-colors"
            />
          </div>
          <button className="p-1.5 bg-bg-overlay border border-border-default rounded text-text-muted hover:text-white transition-colors">
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {samples.map((sample) => (
          <div 
            key={sample.id}
            onClick={() => onSelect(sample)}
            className={`p-4 border-b border-border-default cursor-pointer transition-colors ${
              selectedId != null && selectedId === sample.id
                ? 'bg-bg-overlay border-l-2 border-l-white'
                : 'bg-bg-surface hover:bg-bg-base border-l-2 border-l-transparent'
            }`}
          >
            <div className="flex justify-between items-start mb-2">
              <span className="text-sm font-medium text-white truncate pr-2">{sample.filename}</span>
              <span className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border whitespace-nowrap ${
                sample.status === 'ANALYZED' || sample.status === 'SCANNED' ? 'border-border-strong text-text-secondary' :
                sample.status === 'ANALYZING' || sample.status === 'QUEUED' ? 'border-white text-white' :
                sample.status === 'QUARANTINED' ? 'border-severity-critical text-severity-critical' :
                'border-border-default text-text-muted'
              }`}>
                {sample.status}
              </span>
            </div>
            
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center">
                <span className="font-mono text-[10px] text-text-muted truncate">MD5: {sample.md5.substring(0, 16)}...</span>
                <span className="font-mono text-[10px] text-text-secondary">{sample.size}</span>
              </div>
              <div className="flex justify-between items-center mt-1">
                <span className="text-[11px] text-text-secondary">{sample.type} · {sample.scanStatus ?? 'NOT_SCANNED'}</span>
                <span className="font-mono text-[10px] text-text-muted">{new Date(sample.uploadTime).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
