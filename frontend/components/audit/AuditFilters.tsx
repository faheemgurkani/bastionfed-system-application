'use client';

import { Search, Calendar, Filter, Download } from 'lucide-react';

export function AuditFilters() {
  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col gap-4">
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder="Search logs by user, action, IP, or resource..." 
            className="w-full bg-bg-base border border-border-default rounded-md pl-9 pr-4 py-2 text-sm text-white placeholder:text-text-muted focus:outline-none focus:border-white transition-colors"
          />
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-bg-base border border-border-default rounded-md text-sm text-white hover:bg-bg-overlay transition-colors">
          <Calendar className="w-4 h-4 text-text-muted" /> Last 24 Hours
        </button>
        <button className="flex items-center gap-2 px-4 py-2 bg-bg-base border border-border-default rounded-md text-sm text-white hover:bg-bg-overlay transition-colors">
          <Filter className="w-4 h-4 text-text-muted" /> More Filters
        </button>
      </div>
      
      <div className="flex gap-2">
        <span className="font-display text-[10px] text-text-muted uppercase tracking-wider self-center mr-2">Quick Filters:</span>
        {['Authentication', 'Configuration Changes', 'Data Access', 'System Events', 'Failed Actions'].map((filter) => (
          <button 
            key={filter}
            className="px-3 py-1 border border-border-default rounded-full text-xs text-text-secondary hover:text-white hover:border-white transition-colors"
          >
            {filter}
          </button>
        ))}
      </div>
    </div>
  );
}
