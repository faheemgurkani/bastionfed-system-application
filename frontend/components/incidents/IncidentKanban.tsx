"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  closestCorners,
  DndContext,
  DragEndEvent,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Incident, IncidentStatus } from "@/lib/types";

interface IncidentKanbanProps {
  incidents: Incident[];
  onSelectIncident: (incident: Incident) => void;
  onMoveIncident: (incidentId: string, status: IncidentStatus) => Promise<void> | void;
  loading?: boolean;
}

const columns: IncidentStatus[] = ["NEW", "TRIAGING", "RESPONDING", "RESOLVED", "POST_MORTEM"];

function severityClass(severity: string) {
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
}

function IncidentCard({
  incident,
  onSelectIncident,
}: {
  incident: Incident;
  onSelectIncident: (incident: Incident) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: incident.id,
  });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      {...attributes}
      {...listeners}
      onClick={() => onSelectIncident(incident)}
      className={`bg-bg-base border border-border-default rounded-md p-3 cursor-grab active:cursor-grabbing hover:scale-[1.01] hover:bg-bg-overlay/30 transition-all flex flex-col gap-3 ${
        isDragging ? "opacity-40" : ""
      }`}
    >
      <div className="flex justify-between items-start">
        <span className="font-mono text-[10px] text-text-muted">{incident.id}</span>
        <span
          className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full border ${severityClass(
            incident.severity
          )}`}
        >
          {incident.severity}
        </span>
      </div>
      <span className="text-sm font-medium text-white leading-tight break-words [overflow-wrap:anywhere] line-clamp-2">
        {incident.title}
      </span>
      <div className="flex justify-between items-end mt-1">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-text-secondary">
            {incident.affectedDevices.length} device
            {incident.affectedDevices.length !== 1 ? "s" : ""}
          </span>
          <span className="font-mono text-[10px] text-text-muted">{incident.timeOpen}</span>
        </div>
        <div className="w-6 h-6 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[9px] font-bold text-white">
          {incident.analystInitials}
        </div>
      </div>
    </div>
  );
}

function ColumnDropZone({
  column,
  incidents,
  loading,
  onSelectIncident,
}: {
  column: IncidentStatus;
  incidents: Incident[];
  loading?: boolean;
  onSelectIncident: (incident: Incident) => void;
}) {
  const { isOver, setNodeRef } = useDroppable({ id: `col:${column}` });

  return (
    <div
      ref={setNodeRef}
      className={`flex-none w-[calc((100%-4rem)/5)] min-w-[240px] bg-bg-surface border rounded-lg flex flex-col transition-colors ${
        isOver ? "border-white/70 bg-bg-overlay/30" : "border-border-default"
      }`}
    >
      <div className="p-3 border-b border-border-default flex items-center justify-between bg-bg-base rounded-t-lg">
        <span className="font-display text-xs text-white uppercase tracking-wider">
          {column.replace("_", "-")}
        </span>
        <span className="w-5 h-5 rounded-full bg-bg-overlay border border-border-strong flex items-center justify-center text-[10px] font-mono text-text-muted">
          {incidents.length}
        </span>
      </div>
      <SortableContext items={incidents.map((inc) => inc.id)} strategy={verticalListSortingStrategy}>
        <div className="p-3 flex flex-col gap-3 overflow-y-auto flex-1 min-h-[100px]">
          {loading ? (
            <div className="text-text-secondary text-sm font-mono p-2">Loading…</div>
          ) : incidents.length === 0 ? (
            <div className="text-text-secondary text-sm font-mono p-2">Drop here</div>
          ) : (
            incidents.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                onSelectIncident={onSelectIncident}
              />
            ))
          )}
        </div>
      </SortableContext>
    </div>
  );
}

export function IncidentKanban({
  incidents,
  onSelectIncident,
  onMoveIncident,
  loading,
}: IncidentKanbanProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

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

  const byId = new Map(incidents.map((incident) => [incident.id, incident]));
  const activeIncident = activeIncidentId ? byId.get(activeIncidentId) ?? null : null;

  function getColumnFromDropId(rawId: string | null): IncidentStatus | null {
    if (!rawId) return null;
    if (rawId.startsWith("col:")) return rawId.slice(4) as IncidentStatus;
    const incident = byId.get(rawId);
    return (incident?.status as IncidentStatus | undefined) ?? null;
  }

  async function onDragEnd(event: DragEndEvent) {
    const incidentId = String(event.active.id);
    const overId = event.over ? String(event.over.id) : null;
    setActiveIncidentId(null);
    const targetStatus = getColumnFromDropId(overId);
    const source = byId.get(incidentId);
    if (!source || !targetStatus || source.status === targetStatus) return;
    await onMoveIncident(incidentId, targetStatus);
  }

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
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={(event) => setActiveIncidentId(String(event.active.id))}
        onDragEnd={onDragEnd}
        onDragCancel={() => setActiveIncidentId(null)}
      >
        <div
          ref={scrollRef}
          className="flex gap-4 flex-1 overflow-x-auto no-scrollbar pb-2"
        >
          {columns.map((col) => (
            <ColumnDropZone
              key={col}
              column={col}
              incidents={incidents.filter((inc) => inc.status === col)}
              loading={Boolean(loading)}
              onSelectIncident={onSelectIncident}
            />
          ))}
        </div>
        <DragOverlay>
          {activeIncident ? (
            <div className="w-[240px] rounded-md border border-white/40 bg-bg-base p-3 opacity-95 shadow-2xl overflow-hidden">
              <div className="flex justify-between items-start">
                <span className="font-mono text-[10px] text-text-muted">{activeIncident.id}</span>
                <span
                  className={`text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full border ${severityClass(
                    activeIncident.severity
                  )}`}
                >
                  {activeIncident.severity}
                </span>
              </div>
              <span className="mt-2 block text-sm font-medium text-white leading-tight break-words [overflow-wrap:anywhere] line-clamp-2">
                {activeIncident.title}
              </span>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
