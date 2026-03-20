"use client";

import { AuthGate } from "@/components/auth/AuthGate";
import { AlertTable } from "@/components/alerts/AlertTable";
import { AlertFilters } from "@/components/alerts/AlertFilters";
import { useAlertsContext } from "@/contexts/alerts-context";
import { useState, useMemo } from "react";
import type { Alert } from "@/lib/types";

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

function filterAndSortAlerts(
  alerts: Alert[],
  severity: string,
  tactic: string,
  dateRange: string,
  sortBy: string
): Alert[] {
  const now = Date.now();
  const ms = { hour: 3600e3, day: 86400e3 };
  const dateCutoffs: Record<string, number> = {
    "Last 24 Hours": now - 24 * ms.hour,
    "Last 7 Days": now - 7 * ms.day,
    "Last 30 Days": now - 30 * ms.day,
  };

  let result = [...alerts];

  // Severity filter
  if (severity !== "ALL") {
    result = result.filter((a) => a.severity === severity);
  }

  // Tactic filter
  if (tactic !== "All Tactics") {
    result = result.filter((a) => a.tactic === tactic);
  }

  // Date range filter
  if (dateRange !== "All Time") {
    const cutoff = dateCutoffs[dateRange];
    if (cutoff) {
      result = result.filter((d) => new Date(d.timestamp).getTime() >= cutoff);
    }
  }

  // Sort
  if (sortBy === "Severity (High → Low)") {
    result.sort((a, b) => (SEVERITY_ORDER[b.severity] ?? 0) - (SEVERITY_ORDER[a.severity] ?? 0));
  } else if (sortBy === "Severity (Low → High)") {
    result.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 0) - (SEVERITY_ORDER[b.severity] ?? 0));
  } else if (sortBy === "Date (Newest)") {
    result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  } else if (sortBy === "Date (Oldest)") {
    result.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }

  return result;
}

export default function AlertsPage() {
  const { alerts, alertsLoading, alertsError } = useAlertsContext();
  const [activeSeverity, setActiveSeverity] = useState<string>("ALL");
  const [activeTactic, setActiveTactic] = useState<string>("All Tactics");
  const [activeDateRange, setActiveDateRange] = useState<string>("All Time");
  const [sortBy, setSortBy] = useState<string>("Severity (High → Low)");

  const filteredAlerts = useMemo(
    () =>
      filterAndSortAlerts(alerts, activeSeverity, activeTactic, activeDateRange, sortBy),
    [alerts, activeSeverity, activeTactic, activeDateRange, sortBy]
  );

  return (
    <AuthGate>
      <div className="flex flex-col gap-6 h-full">
        {alertsLoading && (
          <p className="text-sm font-mono text-text-muted">Loading alerts…</p>
        )}
        {alertsError && (
          <p className="text-sm font-mono text-severity-high">Alerts: {alertsError}</p>
        )}
        <AlertFilters
          activeSeverity={activeSeverity}
          onChangeSeverity={setActiveSeverity}
          totalCount={alerts.length}
          visibleCount={filteredAlerts.length}
          activeTactic={activeTactic}
          onChangeTactic={setActiveTactic}
          activeDateRange={activeDateRange}
          onChangeDateRange={setActiveDateRange}
          sortBy={sortBy}
          onChangeSort={setSortBy}
        />
        <div className="flex-1 bg-bg-surface border border-border-default rounded-lg overflow-hidden flex flex-col">
          <AlertTable alerts={filteredAlerts} />
        </div>
      </div>
    </AuthGate>
  );
}
