'use client';

import { Lock } from 'lucide-react';
import { useAlerts } from '@/hooks/use-alerts';

export function NetworkTopology() {
  const alerts = useAlerts();

  const getDeviceAlerts = (ip: string) => {
    return alerts.filter(a => a.device.ip === ip && a.status === 'OPEN').length;
  };

  const mriAlerts = getDeviceAlerts('192.168.10.45');
  const pumpAlerts = getDeviceAlerts('192.168.4.22');
  const ventAlerts = getDeviceAlerts('192.168.4.50');
  const infusionAlerts = getDeviceAlerts('192.168.5.12');
  const pacsAlerts = getDeviceAlerts('10.0.0.100');
  const nurseAlerts = getDeviceAlerts('192.168.2.110');

  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-[480px]">
      <span className="font-display text-xs text-white uppercase tracking-wider mb-4">Network Topology</span>
      <div className="flex-1 relative overflow-hidden bg-bg-base border border-border-default rounded-md">
        <svg width="100%" height="100%" viewBox="0 0 800 480" className="absolute inset-0">
          {/* Edges */}
          <line x1="100" y1="240" x2="400" y2="240" stroke="var(--border-default)" strokeWidth="2" />
          <line x1="400" y1="240" x2="200" y2="100" stroke="var(--border-default)" strokeWidth="2" />
          <line x1="400" y1="240" x2="300" y2="380" stroke="var(--text-primary)" strokeWidth="2" strokeDasharray="4" />
          <line x1="400" y1="240" x2="550" y2="100" stroke="var(--border-default)" strokeWidth="2" />
          <line x1="400" y1="240" x2="620" y2="240" stroke="var(--border-default)" strokeWidth="2" />
          <line x1="400" y1="240" x2="550" y2="380" stroke="var(--border-default)" strokeWidth="2" />
          <line x1="300" y1="380" x2="180" y2="380" stroke="var(--text-primary)" strokeWidth="2" strokeDasharray="4" />

          {/* Nodes */}
          {/* Firewall */}
          <g transform="translate(100, 240)">
            <title>Hospital Firewall</title>
            <rect x="-20" y="-20" width="40" height="40" fill="var(--border-default)" stroke="var(--border-strong)" strokeWidth="2" />
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">Firewall</text>
          </g>

          {/* Aggregation Server */}
          <g transform="translate(400, 240)">
            <title>FL Aggregation Server</title>
            <polygon points="0,-25 18,-18 25,0 18,18 0,25 -18,18 -25,0 -18,-18" fill="var(--border-default)" stroke="var(--border-strong)" strokeWidth="2" />
            <text y="40" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">FL Server</text>
          </g>

          {/* MRI Scanner Unit A */}
          <g transform="translate(200, 100)">
            <title>{`MRI Scanner Unit A\nIP: 192.168.10.45\nAlerts: ${mriAlerts}`}</title>
            {mriAlerts > 0 && <circle r="24" fill="none" stroke="var(--text-primary)" strokeWidth="1" className="animate-pulse" />}
            <circle r="16" fill={mriAlerts > 0 ? "var(--text-primary)" : "var(--border-default)"} stroke={mriAlerts > 0 ? "var(--text-primary)" : "var(--border-strong)"} strokeWidth="2" />
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">MRI Unit A</text>
          </g>

          {/* Insulin Pump Hub */}
          <g transform="translate(300, 380)">
            <title>{`Insulin Pump Hub\nIP: 192.168.4.22\nAlerts: ${pumpAlerts}`}</title>
            {pumpAlerts > 0 && <circle r="24" fill="none" stroke="var(--text-primary)" strokeWidth="2" className="animate-ping" />}
            <circle r="16" fill={pumpAlerts > 0 ? "var(--bg-elevated)" : "var(--border-default)"} stroke={pumpAlerts > 0 ? "var(--text-primary)" : "var(--border-strong)"} strokeWidth="2" />
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">Pump Hub</text>
          </g>

          {/* Ventilator Array B3 */}
          <g transform="translate(550, 100)">
            <title>{`Ventilator Array B3\nIP: 192.168.4.50\nAlerts: ${ventAlerts}`}</title>
            {ventAlerts > 0 && <circle r="24" fill="none" stroke="var(--text-primary)" strokeWidth="1" className="animate-pulse" />}
            <circle r="16" fill={ventAlerts > 0 ? "var(--text-primary)" : "var(--border-default)"} stroke={ventAlerts > 0 ? "var(--text-primary)" : "var(--border-strong)"} strokeWidth="2" />
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">Ventilator B3</text>
          </g>

          {/* Infusion System */}
          <g transform="translate(620, 240)">
            <title>{`Infusion System\nIP: 192.168.5.12\nAlerts: ${infusionAlerts}`}</title>
            {infusionAlerts > 0 && <circle r="24" fill="none" stroke="var(--text-primary)" strokeWidth="1" className="animate-pulse" />}
            <circle r="16" fill={infusionAlerts > 0 ? "var(--text-primary)" : "var(--border-default)"} stroke={infusionAlerts > 0 ? "var(--text-primary)" : "var(--border-strong)"} strokeWidth="2" />
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">Infusion Sys</text>
          </g>

          {/* PACS Server */}
          <g transform="translate(550, 380)">
            <title>{`PACS Server\nIP: 10.0.0.100\nAlerts: ${pacsAlerts}`}</title>
            {pacsAlerts > 0 && <circle r="24" fill="none" stroke="var(--text-primary)" strokeWidth="1" className="animate-pulse" />}
            <circle r="16" fill={pacsAlerts > 0 ? "var(--text-primary)" : "var(--border-default)"} stroke={pacsAlerts > 0 ? "var(--text-primary)" : "var(--border-strong)"} strokeWidth="2" />
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">PACS Server</text>
          </g>

          {/* Nurse Station 4F - Isolated */}
          <g transform="translate(180, 380)">
            <title>{`Nurse Station 4F\nIP: 192.168.2.110\nStatus: Isolated\nAlerts: ${nurseAlerts}`}</title>
            <circle r="16" fill="var(--bg-base)" stroke="var(--border-strong)" strokeWidth="2" strokeDasharray="4" />
            <foreignObject x="-8" y="-8" width="16" height="16">
              <Lock className="w-4 h-4 text-text-muted" />
            </foreignObject>
            <text y="35" textAnchor="middle" fill="var(--text-muted)" className="font-mono text-[12px]">Nurse Stn 4F</text>
          </g>
        </svg>
      </div>
    </div>
  );
}
