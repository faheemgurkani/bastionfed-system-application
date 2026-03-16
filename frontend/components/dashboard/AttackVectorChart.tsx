'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const data = [
  { name: 'Ransomware', count: 12 },
  { name: 'Firmware Injection', count: 8 },
  { name: 'MitM Attack', count: 6 },
  { name: 'DDoS', count: 4 },
  { name: 'Data Exfiltration', count: 3 },
];

export function AttackVectorChart() {
  return (
    <div className="bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col h-[280px]">
      <span className="font-display text-xs text-white uppercase tracking-wider mb-4">Attack Vectors</span>
      <div className="flex-1 w-full min-h-[220px]">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 20, left: 40, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--bg-overlay)" />
            <XAxis type="number" hide />
            <YAxis 
              dataKey="name" 
              type="category" 
              axisLine={false} 
              tickLine={false} 
              tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-jetbrains-mono)' }} 
              width={120}
            />
            <Tooltip 
              cursor={{ fill: 'var(--bg-elevated)' }}
              contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-default)', borderRadius: '8px' }}
              itemStyle={{ color: 'var(--text-primary)', fontFamily: 'var(--font-jetbrains-mono)', fontSize: '12px' }}
              labelStyle={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}
            />
            <Bar dataKey="count" fill="var(--text-primary)" radius={[0, 4, 4, 0]} barSize={24} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
