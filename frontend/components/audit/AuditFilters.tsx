'use client';

import { Search, Calendar } from 'lucide-react';

interface AuditFiltersProps {
  searchQuery: string;
  setSearchQuery: (val: string) => void;
  activeFilter: string | null;
  setActiveFilter: (val: string | null) => void;
  last24h: boolean;
  setLast24h: (val: boolean) => void;
  hasRecentLogs: boolean;
}

export function AuditFilters({
  searchQuery, setSearchQuery,
  activeFilter, setActiveFilter,
  last24h, setLast24h,
  hasRecentLogs
}: AuditFiltersProps) {
  
  const LiveIndicator = () => (
    <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
    </span>
  );

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col gap-4">
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search logs by user, action, IP, or resource..." 
            className="w-full bg-bg-base border border-border-default rounded-md pl-9 pr-4 py-2 text-sm text-white placeholder:text-text-muted focus:outline-none focus:border-white transition-colors"
          />
        </div>
        <button 
          onClick={() => setLast24h(!last24h)}
          disabled={!hasRecentLogs && !last24h}
          className={`flex items-center gap-2 px-4 py-2 border rounded-md text-sm transition-colors ${
            last24h ? 'bg-white text-black border-white' : 
            !hasRecentLogs ? 'bg-bg-base border-border-default text-text-muted opacity-50 cursor-not-allowed' :
            'bg-bg-base border-border-default text-white hover:bg-bg-overlay'
          }`}
        >
          <Calendar className={`w-4 h-4 ${last24h ? 'text-black' : 'text-text-muted'}`} /> 
          Last 24 Hours
        </button>
      </div>
      
      <div className="flex gap-2">
        <span className="font-display text-[10px] text-text-muted uppercase tracking-wider self-center mr-2">Quick Filters:</span>
        <button 
          onClick={() => setActiveFilter(null)}
          className={`px-3 py-1 border rounded-full text-xs transition-colors flex items-center gap-1.5 ${
            activeFilter === null 
              ? 'bg-white border-white text-black' 
              : 'bg-transparent border-border-default text-text-secondary hover:text-white hover:border-white'
          }`}
        >
          {activeFilter === null && <LiveIndicator />}
          All
        </button>
        {['Authentication', 'Configuration Changes', 'Data Access', 'System Events', 'Failed Actions'].map((filter) => (
          <button 
            key={filter}
            onClick={() => setActiveFilter(activeFilter === filter ? null : filter)}
            className={`px-3 py-1 border rounded-full text-xs transition-colors ${
              activeFilter === filter 
                ? 'bg-white border-white text-black' 
                : 'bg-transparent border-border-default text-text-secondary hover:text-white hover:border-white'
            }`}
          >
            {filter}
          </button>
        ))}
      </div>
    </div>
  );
}
