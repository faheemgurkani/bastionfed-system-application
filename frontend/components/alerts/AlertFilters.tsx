"use client";

import { useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Filter, Calendar as CalendarIcon, ChevronDown } from "lucide-react";

const ATTACK_TACTICS = ["All Tactics", "Initial Access", "Collection", "Discovery", "Impact", "Impair Process Control"] as const;
const DATE_RANGES = ["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days"] as const;
const SORT_OPTIONS = ["Severity (High → Low)", "Severity (Low → High)", "Date (Newest)", "Date (Oldest)"] as const;

interface AlertFiltersProps {
  activeSeverity: string;
  onChangeSeverity: (value: string) => void;
  totalCount: number;
  visibleCount: number;
  activeTactic?: string;
  onChangeTactic?: (value: string) => void;
  activeDateRange?: string;
  onChangeDateRange?: (value: string) => void;
  sortBy?: string;
  onChangeSort?: (value: string) => void;
}

export function AlertFilters({
  activeSeverity,
  onChangeSeverity,
  totalCount,
  visibleCount,
  activeTactic: controlledTactic,
  onChangeTactic,
  activeDateRange: controlledDateRange,
  onChangeDateRange,
  sortBy: controlledSortBy,
  onChangeSort,
}: AlertFiltersProps) {
  const severities = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

  const [tactic, setTactic] = useState("All Tactics");
  const [dateRange, setDateRange] = useState("All Time");
  const [sortBy, setSortBy] = useState("Severity (High → Low)");

  const activeTactic = controlledTactic ?? tactic;
  const activeDateRange = controlledDateRange ?? dateRange;
  const activeSortBy = controlledSortBy ?? sortBy;

  const handleTacticSelect = (value: string) => {
    setTactic(value);
    onChangeTactic?.(value);
  };
  const handleDateRangeSelect = (value: string) => {
    setDateRange(value);
    onChangeDateRange?.(value);
  };
  const handleSortSelect = (value: string) => {
    setSortBy(value);
    onChangeSort?.(value);
  };

  const triggerClass =
    "flex items-center gap-2 px-3 py-1.5 border border-border-default rounded-md text-sm text-white hover:bg-bg-overlay transition-colors outline-none data-[state=open]:bg-bg-overlay data-[state=open]:border-white/50";

  const LiveIndicator = () => (
    <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
    </span>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {severities.map((sev) => (
            <button
              key={sev}
              onClick={() => onChangeSeverity(sev)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-mono uppercase tracking-wider transition-colors border ${
                activeSeverity === sev
                  ? "bg-white text-black border-white"
                  : "bg-transparent text-white border-border-default hover:bg-bg-overlay"
              }`}
            >
              {sev === "ALL" && <LiveIndicator />}
              {sev}
              {sev === "ALL" && <span className="text-[10px] normal-case font-normal opacity-90">(Live)</span>}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className={triggerClass}>
                <Filter className="w-4 h-4" />
                <span>{activeTactic}</span>
                <ChevronDown className="w-4 h-4 text-text-muted" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="min-w-[200px] bg-bg-surface border border-border-default rounded-md shadow-lg py-1 z-50"
                sideOffset={4}
                align="end"
              >
                {ATTACK_TACTICS.map((tactic) => (
                  <DropdownMenu.Item
                    key={tactic}
                    onSelect={() => handleTacticSelect(tactic)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-bg-overlay cursor-pointer outline-none data-[highlighted]:bg-bg-overlay"
                  >
                    {tactic === "All Tactics" && <LiveIndicator />}
                    {tactic}
                    {tactic === "All Tactics" && <span className="text-[10px] text-green-400 font-mono">(Live)</span>}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className={triggerClass}>
                <CalendarIcon className="w-4 h-4" />
                <span>{activeDateRange}</span>
                <ChevronDown className="w-4 h-4 text-text-muted" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="min-w-[180px] bg-bg-surface border border-border-default rounded-md shadow-lg py-1 z-50"
                sideOffset={4}
                align="end"
              >
                {DATE_RANGES.map((range) => (
                  <DropdownMenu.Item
                    key={range}
                    onSelect={() => handleDateRangeSelect(range)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-bg-overlay cursor-pointer outline-none data-[highlighted]:bg-bg-overlay"
                  >
                    {range === "All Time" && <LiveIndicator />}
                    {range}
                    {range === "All Time" && <span className="text-[10px] text-green-400 font-mono">(Live)</span>}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className={triggerClass}>
                <span>Sort: {activeSortBy}</span>
                <ChevronDown className="w-4 h-4 text-text-muted" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                className="min-w-[220px] bg-bg-surface border border-border-default rounded-md shadow-lg py-1 z-50"
                sideOffset={4}
                align="end"
              >
                {SORT_OPTIONS.map((option) => (
                  <DropdownMenu.Item
                    key={option}
                    onSelect={() => handleSortSelect(option)}
                    className="px-3 py-2 text-sm text-white hover:bg-bg-overlay cursor-pointer outline-none data-[highlighted]:bg-bg-overlay"
                  >
                    {option}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </div>

      <div className="flex items-center">
        <span className="font-mono text-xs text-text-muted">
          Showing {visibleCount} of {totalCount} alerts
        </span>
      </div>
    </div>
  );
}
