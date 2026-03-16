"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { MOCK_INCIDENTS } from "@/lib/mock-data";
import { Incident } from "@/lib/types";

interface IncidentKanbanProps {
  onSelectIncident: (incident: Incident) => void;
}

export function IncidentKanban({ onSelectIncident }: IncidentKanbanProps) {
  const columns = ["NEW", "TRIAGING", "RESPONDING", "RESOLVED", "POST_MORTEM"];
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateArrows = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 1);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateArrows();
    el.addEventListener("scroll", updateArrows, { passive: true });
    const ro = new ResizeObserver(updateArrows);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateArrows);
      ro.disconnect();
    };
  }, [updateArrows]);

  const handleScroll = (dir: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    const colWidth = el.clientWidth / columns.length + 16;
    el.scrollBy({
      left: dir === "left" ? -colWidth : colWidth,
      behavior: "smooth",
    });
  };

  const getSeverityStyle = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "border-severity-critical text-severity-critical";
      case "HIGH":
        return "border-severity-high text-severity-high";
      case "MEDIUM":
        return "border-severity-medium text-severity-medium";
      case "LOW":
        return "border-severity-low text-severity-low";
      default:
        return "border-border-default text-white";
    }
  };

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Top bar with navigation arrows */}
      <div className="flex items-center justify-end gap-0 flex-shrink-0">
        <button
          onClick={() => handleScroll("left")}
          aria-label="Scroll left"
          className={`w-9 h-9 border border-border-strong flex items-center justify-center transition-all ${
            canScrollLeft
              ? "text-white hover:bg-bg-overlay cursor-pointer"
              : "text-text-muted opacity-40 cursor-default"
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <button
          onClick={() => handleScroll("right")}
          aria-label="Scroll right"
          className={`w-9 h-9 border border-border-strong flex items-center justify-center transition-all ${
            canScrollRight
              ? "text-white hover:bg-bg-overlay cursor-pointer"
              : "text-text-muted opacity-40 cursor-default"
          }`}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Scrollable kanban */}
      <div
        ref={scrollRef}
        className="flex gap-4 flex-1 overflow-x-auto no-scrollbar pb-2"
      >
        {columns.map((col) => {
          const columnIncidents = MOCK_INCIDENTS.filter(
            (inc) => inc.status === col,
          );

          return (
            <div
              key={col}
              className="flex-none w-[calc((100%-4rem)/5)] min-w-[240px] bg-bg-surface border border-border-default rounded-lg flex flex-col"
            >
              <div className="p-3 border-b border-border-default flex items-center justify-between bg-bg-base rounded-t-lg">
                <span className="font-display text-xs text-white uppercase tracking-wider">
                  {col.replace("_", "-")}
                </span>
                <span className="w-5 h-5 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[10px] font-mono text-text-muted">
                  {columnIncidents.length}
                </span>
              </div>

              <div className="p-3 flex flex-col gap-3 overflow-y-auto flex-1">
                {columnIncidents.map((inc) => (
                  <div
                    key={inc.id}
                    onClick={() => onSelectIncident(inc)}
                    className="bg-bg-base border border-border-default rounded-md p-3 cursor-pointer hover:scale-[1.02] active:scale-[0.99] hover:bg-bg-overlay/30 transition-all flex flex-col gap-3"
                  >
                    <div className="flex justify-between items-start">
                      <span className="font-mono text-[10px] text-text-muted">
                        {inc.id}
                      </span>
                      <span
                        className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full border ${getSeverityStyle(inc.severity)}`}
                      >
                        {inc.severity}
                      </span>
                    </div>

                    <span className="text-sm font-medium text-white leading-tight">
                      {inc.title}
                    </span>

                    <div className="flex justify-between items-end mt-1">
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] text-text-secondary">
                          {inc.affectedDevices.length} device
                          {inc.affectedDevices.length !== 1 ? "s" : ""}
                        </span>
                        <span className="font-mono text-[10px] text-text-muted">
                          {inc.timeOpen}
                        </span>
                      </div>
                      <div className="w-6 h-6 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[9px] font-bold text-white">
                        {inc.analystInitials}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
