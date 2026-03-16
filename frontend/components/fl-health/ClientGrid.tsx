"use client";

import { useEffect, useState } from "react";
import type { FLClient } from "@/lib/types";
import { useFLClients } from "@/contexts/fl-clients-context";
import { TriangleAlert, X } from "lucide-react";

const STATUS_ORDER: Record<string, number> = {
  POISONING_SUSPECT: 0,
  ACTIVE: 1,
  DEGRADED: 2,
  OFFLINE: 3,
};

export function ClientGrid() {
  const clients = useFLClients();
  const [detailClient, setDetailClient] = useState<FLClient | null>(null);

  const sortedClients = [...clients].sort(
    (a, b) => (STATUS_ORDER[a.status] ?? 4) - (STATUS_ORDER[b.status] ?? 4),
  );

  const closeDetail = () => setDetailClient(null);

  // Allow closing the detail pop-up with Escape
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDetailClient(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-full relative">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display text-xs text-white uppercase tracking-wider">
          FL Client Grid
        </span>
        <div className="flex items-center gap-4 flex-wrap justify-end">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-white flex-shrink-0" />
            <span className="text-[9px] font-mono text-text-muted uppercase">
              Active
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full border border-border-strong border-dashed flex-shrink-0" />
            <span className="text-[9px] font-mono text-text-muted uppercase">
              Degraded
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-bg-base opacity-50 border border-border-default flex-shrink-0" />
            <span className="text-[9px] font-mono text-text-muted uppercase">
              Offline
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2 flex-shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
            </span>
            <span className="text-[9px] font-mono text-text-muted uppercase">
              Poisoning suspect
            </span>
          </div>
        </div>
      </div>
      <div
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 flex-1 min-h-[440px] auto-rows-fr"
        style={{ gridAutoRows: "minmax(120px, 1fr)" }}
      >
        {sortedClients.map((client) => {
          const isOffline = client.status === "OFFLINE";
          const isDegraded = client.status === "DEGRADED";
          const isSuspect = client.status === "POISONING_SUSPECT";

          return (
            <button
              type="button"
              key={client.id}
              onClick={() => setDetailClient(client)}
              className={`p-4 rounded-md flex flex-col gap-2.5 relative text-left transition-all cursor-pointer outline-none hover:scale-[1.02] active:scale-[0.99] ${
                isSuspect
                  ? "border-2 border-red-400 bg-bg-elevated hover:bg-bg-overlay/50"
                  : isDegraded
                    ? "border border-border-strong border-dashed bg-bg-base hover:bg-bg-overlay/30"
                    : isOffline
                      ? "border border-border-default bg-bg-base opacity-50 hover:opacity-70"
                      : "border border-border-default bg-bg-elevated hover:bg-bg-overlay/50"
              }`}
            >
              <div className="flex justify-between items-start gap-2 min-w-0">
                <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
                  {!isOffline &&
                    (isSuspect ? (
                      <span className="relative flex h-2 w-2 flex-shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                      </span>
                    ) : (
                      <div
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          isDegraded
                            ? "border border-border-strong border-dashed"
                            : "bg-white"
                        }`}
                      />
                    ))}
                  <span
                    className={`font-mono text-[11px] truncate ${isOffline ? "text-text-muted" : "text-white"}`}
                    title={client.id}
                  >
                    {client.id}
                  </span>
                </div>
                {isSuspect && (
                  <TriangleAlert className="w-4 h-4 text-red-400 flex-shrink-0" />
                )}
              </div>

              <div className="grid grid-cols-2 gap-x-2 gap-y-1 mt-2">
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-muted uppercase">
                    Part. %
                  </span>
                  <span className="font-mono text-[11px] text-text-secondary">
                    {client.participationPct}%
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-muted uppercase">
                    Last Rnd
                  </span>
                  <span className="font-mono text-[11px] text-text-secondary">
                    {client.lastRound}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-muted uppercase">
                    DP ε
                  </span>
                  <span className="font-mono text-[11px] text-text-secondary">
                    {client.dpEpsilon}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-muted uppercase">
                    Model
                  </span>
                  <span className="font-mono text-[11px] text-text-secondary">
                    {client.modelVersion}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {detailClient && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
          onClick={closeDetail}
        >
          <div
            className="relative max-w-xl w-full bg-bg-surface border border-border-default rounded-lg p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={closeDetail}
              className="absolute top-3 right-3 text-text-muted hover:text-white transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="flex items-center gap-3 min-w-0">
                {detailClient.status === "POISONING_SUSPECT" ? (
                  <span className="relative flex h-3 w-3 flex-shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
                  </span>
                ) : detailClient.status === "DEGRADED" ? (
                  <div className="w-3 h-3 rounded-full bg-border-strong flex-shrink-0" />
                ) : detailClient.status === "OFFLINE" ? (
                  <div className="w-3 h-3 rounded-full bg-bg-base opacity-50 border border-border-default flex-shrink-0" />
                ) : (
                  <div className="w-3 h-3 rounded-full bg-white flex-shrink-0" />
                )}

                <div className="min-w-0">
                  <h3 className="font-mono text-sm text-white truncate" title={detailClient.id}>
                    {detailClient.id}
                  </h3>
                  <p className="text-[11px] text-text-muted">
                    {detailClient.department}
                  </p>
                </div>
              </div>

              {detailClient.status === "POISONING_SUSPECT" && (
                <div className="flex items-center gap-1 rounded-full border border-red-400 px-2 py-0.5">
                  <TriangleAlert className="w-3 h-3 text-red-400" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-red-400">
                    Poisoning suspect
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="space-y-1">
                <span className="text-[10px] text-text-muted uppercase">
                  Participation %
                </span>
                <p className="font-mono text-sm text-white">
                  {detailClient.participationPct}%
                </p>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-text-muted uppercase">
                  Last Round
                </span>
                <p className="font-mono text-sm text-white">
                  {detailClient.lastRound}
                </p>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-text-muted uppercase">
                  DP ε
                </span>
                <p className="font-mono text-sm text-white">
                  {detailClient.dpEpsilon}
                </p>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-text-muted uppercase">
                  Model Version
                </span>
                <p className="font-mono text-sm text-white">
                  {detailClient.modelVersion}
                </p>
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] text-text-muted uppercase">
                Status
              </span>
              <p className="font-mono text-xs text-text-secondary">
                {detailClient.status === "ACTIVE" && "Active – contributing normally"}
                {detailClient.status === "DEGRADED" &&
                  "Degraded – partially contributing or underperforming"}
                {detailClient.status === "OFFLINE" &&
                  "Offline – currently not participating in federation"}
                {detailClient.status === "POISONING_SUSPECT" &&
                  "Flagged for possible model poisoning – investigate this client’s updates"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
