export function DriftTable() {
  const drifts = [
    { model: 'DNN Classifier', lastEvent: '2h ago', score: 0.05, status: 'STABLE' },
    { model: 'GNN Anomaly Detector', lastEvent: '1d ago', score: 0.12, status: 'MONITORING' },
    { model: 'Ensemble Hybrid', lastEvent: '5m ago', score: 0.34, status: 'DRIFT_DETECTED' },
    { model: 'Behavioral Baseline', lastEvent: '4d ago', score: 0.02, status: 'STABLE' },
    { model: 'Traffic Analyzer', lastEvent: '12h ago', score: 0.08, status: 'STABLE' },
  ];

  const getScoreStyle = (score: number) => {
    if (score < 0.1) return 'text-text-muted';
    if (score <= 0.3) return 'text-text-secondary';
    return 'text-white font-bold';
  };

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex-1 flex flex-col">
      <span className="font-display text-xs text-white uppercase tracking-wider mb-4">Drift Detection</span>
      <div className="flex-1 overflow-auto no-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border-default">
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Model</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Last Event</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Score</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {drifts.map((d, i) => (
              <tr key={i} className="border-b border-border-default last:border-0 hover:bg-bg-overlay transition-colors">
                <td className="py-2 text-[12px] text-white">{d.model}</td>
                <td className="py-2 text-[11px] text-text-secondary font-mono">{d.lastEvent}</td>
                <td className={`py-2 text-[12px] font-mono ${getScoreStyle(d.score)}`}>{d.score.toFixed(2)}</td>
                <td className="py-2 text-right">
                  <button className="text-[10px] font-mono uppercase tracking-wider text-text-muted hover:text-white transition-colors">View</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
