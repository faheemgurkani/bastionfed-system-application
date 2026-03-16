export function PlaybookLibrary() {
  const playbooks = [
    { name: 'Ransomware Response', trigger: 'Ransomware signature match', lastRun: '2h ago', executions: 142, status: 'ACTIVE' },
    { name: 'MitM Isolation', trigger: 'Lateral movement', lastRun: '1d ago', executions: 89, status: 'ACTIVE' },
    { name: 'Firmware Anomaly', trigger: 'Hash mismatch', lastRun: '5h ago', executions: 45, status: 'ACTIVE' },
    { name: 'Credential Lockout', trigger: 'CVE match', lastRun: '3d ago', executions: 12, status: 'ACTIVE' },
    { name: 'DDoS Mitigation', trigger: 'Traffic spike', lastRun: '1w ago', executions: 210, status: 'ACTIVE' },
  ];

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-full">
      <div className="flex justify-between items-center mb-4">
        <span className="font-display text-xs text-white uppercase tracking-wider">Playbook Library</span>
        <button className="text-xs text-black bg-white px-3 py-1.5 rounded hover:bg-interactive-hover transition-colors font-medium">
          New Playbook
        </button>
      </div>
      
      <div className="flex-1 overflow-auto no-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border-default">
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Name</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Trigger Condition</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Last Run</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Executions</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider">Status</th>
              <th className="pb-2 font-display text-[10px] text-text-muted uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {playbooks.map((pb, i) => (
              <tr key={i} className="border-b border-border-default last:border-0 hover:bg-bg-overlay transition-colors">
                <td className="py-3 text-[13px] text-white font-medium">{pb.name}</td>
                <td className="py-3 text-[12px] text-text-secondary">{pb.trigger}</td>
                <td className="py-3 text-[11px] text-text-muted font-mono">{pb.lastRun}</td>
                <td className="py-3 text-[12px] text-white font-mono">{pb.executions}</td>
                <td className="py-3">
                  <span className="border border-border-strong bg-bg-overlay text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded text-text-secondary">
                    {pb.status}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button className="text-[10px] font-mono uppercase tracking-wider text-text-muted hover:text-white transition-colors">Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
