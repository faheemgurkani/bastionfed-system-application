"use client";

import React, { useEffect, useState } from "react";
import type { Alert } from "@/lib/types";
import { confidencePercent } from "@/lib/alertDisplay";
import { MoreHorizontal, ChevronDown, ChevronRight } from "lucide-react";
import { AlertDetailDrawer } from "./AlertDetailDrawer";

interface AlertTableProps {
  alerts: Alert[];
  focusedAlertId?: string | null;
}

export function AlertTable({ alerts, focusedAlertId = null }: AlertTableProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  useEffect(() => {
    if (!focusedAlertId) return;
    const focusedAlert = alerts.find((alert) => alert.id === focusedAlertId) ?? null;
    if (focusedAlert) {
      setSelectedAlert(focusedAlert);
      setExpandedRow(focusedAlert.id);
    }
  }, [alerts, focusedAlertId]);

  const toggleRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedRow(expandedRow === id ? null : id);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "text-severity-critical border-severity-critical";
      case "HIGH":
        return "text-severity-high border-severity-high";
      case "MEDIUM":
        return "text-severity-medium border-severity-medium";
      case "LOW":
        return "text-severity-low border-severity-low";
      default:
        return "text-white border-border-default";
    }
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case "OPEN":
        return "border border-white text-white";
      case "IN_REVIEW":
        return "border border-border-strong text-text-secondary";
      case "RESOLVED":
        return "border border-transparent text-text-muted";
      case "FALSE_POSITIVE":
        return "border border-transparent text-text-muted line-through";
      default:
        return "";
    }
  };

  return (
    <>
      <div className="overflow-auto flex-1">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border-default bg-bg-base">
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider w-8"></th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                #
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                Timestamp
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                Device
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                Alert Type
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                ATT&CK Tactic
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                Severity
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                Confidence
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider">
                Status
              </th>
              <th className="p-3 font-display text-[10px] text-text-muted uppercase tracking-wider text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert, i) => {
              const confPct = confidencePercent(alert.confidence);
              return (
              <React.Fragment key={alert.id}>
                <tr
                  className={`border-b border-border-default cursor-pointer transition-colors ${i % 2 === 0 ? "bg-bg-surface" : "bg-bg-elevated"} hover:bg-bg-overlay`}
                  onClick={() => setSelectedAlert(alert)}
                >
                  <td className="p-3" onClick={(e) => toggleRow(alert.id, e)}>
                    {expandedRow === alert.id ? (
                      <ChevronDown className="w-4 h-4 text-text-muted" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-text-muted" />
                    )}
                  </td>
                  <td className="p-3 font-mono text-[12px] text-text-muted">
                    {alert.id}
                  </td>
                  <td className="p-3 font-mono text-[12px] text-text-secondary">
                    {new Date(alert.timestamp).toLocaleString([], {
                      dateStyle: "short",
                      timeStyle: "short",
                      hour12: false,
                    })}
                  </td>
                  <td className="p-3 text-[13px] font-medium text-white">
                    {alert.device?.name ?? '—'}
                  </td>
                  <td className="p-3 text-[13px] text-text-secondary">
                    {alert.type}
                  </td>
                  <td className="p-3 text-[13px] text-text-secondary">
                    {alert.tactic}
                  </td>
                  <td className="p-3">
                    <span
                      className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${getSeverityColor(alert.severity)}`}
                    >
                      {alert.severity}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[12px] text-white">
                        {Math.round(confPct * 100) / 100}%
                      </span>
                      <div className="w-16 h-1 bg-bg-subtle rounded-full overflow-hidden">
                        <div
                          className="h-full bg-white"
                          style={{ width: `${Math.min(100, confPct)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="p-3">
                    <span
                      className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full ${getStatusStyle(alert.status)}`}
                    >
                      {alert.status?.replace("_", " ") ?? '—'}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      className="text-text-muted hover:text-white transition-colors p-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
                {expandedRow === alert.id && (
                  <tr className="bg-bg-base border-b border-border-default">
                    <td colSpan={10} className="p-4 pl-12">
                      <div className="grid grid-cols-3 gap-6">
                        <div className="flex flex-col gap-1">
                          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
                            Detection Model
                          </span>
                          <span className="font-mono text-[12px] text-white">
                            {alert.modelVersion}
                          </span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
                            FL Client Source
                          </span>
                          <span className="font-mono text-[12px] text-white">
                            {alert.device.flClientId}
                          </span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
                            Feature Summary
                          </span>
                          <span className="text-[12px] text-text-secondary">
                            {alert.featureSummary}
                          </span>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
            })}
          </tbody>
        </table>
      </div>

      {selectedAlert && (
        <AlertDetailDrawer
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}
    </>
  );
}
