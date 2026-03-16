import { Loader2 } from "lucide-react";

export function RoundStatusBanner() {
  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-6 flex items-center justify-between">
      <div className="flex flex-col gap-3">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-5xl text-white tracking-tight">
            ROUND 47
          </span>
          <span className="font-mono text-xl text-text-muted">/ 100</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
            Status:
          </span>
          <div className="flex items-center gap-2 border border-border-strong bg-bg-overlay px-3 py-1.5 rounded-full">
            <Loader2 className="w-4 h-4 text-white animate-spin" />
            <span className="font-mono text-xs text-white uppercase tracking-wider">
              AGGREGATING
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-start gap-8">
        <div className="flex flex-col items-end gap-2">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
            12 / 15 CLIENTS ACTIVE
          </span>
          <div className="flex gap-1 mt-2">
            {Array.from({ length: 15 }).map((_, i) => {
              const isActive = i < 12;
              const isLastActive = i === 11;
              return (
                <div
                  key={i}
                  className="relative flex items-center justify-center"
                >
                  {isLastActive && (
                    <span className="animate-ping absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-2.5 w-2.5 rounded-full bg-white opacity-75" />
                  )}
                  <div
                    className={`relative w-2.5 h-2.5 rounded-full ${isActive ? "bg-white" : "bg-border-strong"}`}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1">
          <span className="font-display text-[10px] text-text-muted uppercase tracking-wider">
            NEXT ROUND IN
          </span>
          <span className="font-mono text-lg text-white">4:32</span>
        </div>
      </div>
    </div>
  );
}
