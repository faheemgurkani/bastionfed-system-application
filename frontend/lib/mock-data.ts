import {
  Alert,
  AuditLog,
  BotMessage,
  Device,
  FLClient,
  FLRound,
  Incident,
  MalwareSample,
  RCAReport,
} from './types';

export const MOCK_DEVICES: Device[] = [
  { id: 'dev-01', name: 'MRI Scanner Unit A', ip: '192.168.10.45', type: 'MRI', wing: 'Radiology', criticality: 5, flClientId: 'Radiology-FL-02', status: 'SUSPICIOUS' },
  { id: 'dev-02', name: 'Insulin Pump Hub', ip: '192.168.4.22', type: 'Pump Hub', wing: 'ICU', criticality: 5, flClientId: 'ICU-FL-03', status: 'COMPROMISED' },
  { id: 'dev-03', name: 'Ventilator Array B3', ip: '192.168.4.50', type: 'Ventilator', wing: 'ICU', criticality: 5, flClientId: 'ICU-FL-03', status: 'NORMAL' },
  { id: 'dev-04', name: 'Infusion System', ip: '192.168.5.12', type: 'Infusion', wing: 'Surgery', criticality: 4, flClientId: 'Surgery-FL-04', status: 'NORMAL' },
  { id: 'dev-05', name: 'PACS Server', ip: '10.0.0.100', type: 'Server', wing: 'Data Center', criticality: 5, flClientId: 'Imaging-FL-14', status: 'NORMAL' },
  { id: 'dev-06', name: 'Nurse Station 4F', ip: '192.168.2.110', type: 'Workstation', wing: 'Oncology', criticality: 3, flClientId: 'Oncology-FL-07', status: 'NORMAL' },
  { id: 'dev-07', name: 'CT Scanner', ip: '192.168.10.46', type: 'CT', wing: 'Radiology', criticality: 4, flClientId: 'Radiology-FL-02', status: 'NORMAL' },
  { id: 'dev-08', name: 'Patient Monitor 12', ip: '192.168.4.12', type: 'Monitor', wing: 'ICU', criticality: 4, flClientId: 'ICU-FL-03', status: 'NORMAL' },
  { id: 'dev-09', name: 'Defibrillator', ip: '192.168.6.5', type: 'Defibrillator', wing: 'ER', criticality: 5, flClientId: 'ER-FL-05', status: 'NORMAL' },
  { id: 'dev-10', name: 'Pharmacy Dispenser', ip: '192.168.7.20', type: 'Dispenser', wing: 'Pharmacy', criticality: 4, flClientId: 'Pharmacy-FL-06', status: 'NORMAL' },
  { id: 'dev-11', name: 'Dialysis Machine', ip: '192.168.8.15', type: 'Dialysis', wing: 'Nephrology', criticality: 5, flClientId: 'Nephrology-FL-08', status: 'NORMAL' },
  { id: 'dev-12', name: 'Incubator', ip: '192.168.9.8', type: 'Incubator', wing: 'PICU', criticality: 5, flClientId: 'PICU-FL-13', status: 'NORMAL' },
  { id: 'dev-13', name: 'EEG Machine', ip: '192.168.11.30', type: 'EEG', wing: 'Neurology', criticality: 3, flClientId: 'Neurology-FL-10', status: 'NORMAL' },
  { id: 'dev-14', name: 'Admin Workstation', ip: '192.168.1.50', type: 'Workstation', wing: 'Admin', criticality: 2, flClientId: 'Admin-FL-15', status: 'NORMAL' },
  { id: 'dev-15', name: 'Lab Analyzer', ip: '192.168.12.10', type: 'Analyzer', wing: 'Lab', criticality: 4, flClientId: 'Lab-FL-12', status: 'NORMAL' },
];

export const MOCK_ALERTS: Alert[] = Array.from({ length: 20 }).map((_, i) => {
  const severities: ('CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW')[] = ['CRITICAL', 'CRITICAL', 'CRITICAL', 'HIGH', 'HIGH', 'HIGH', 'HIGH', 'HIGH', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'MEDIUM', 'LOW', 'LOW', 'LOW', 'LOW', 'LOW'];
  const tactics = ['Initial Access', 'Collection', 'Discovery', 'Impact', 'Impair Process Control'];
  const techniques = [
    { id: 'T0886', tactic: 'Initial Access', name: 'Remote Services' },
    { id: 'T0882', tactic: 'Collection', name: 'Theft of Operational Information' },
    { id: 'T0840', tactic: 'Discovery', name: 'Network Connection Enumeration' },
    { id: 'T0814', tactic: 'Impact', name: 'Denial of Service' },
    { id: 'T0856', tactic: 'Impair Process Control', name: 'Spoof Reporting Message' }
  ];
  
  const tech = techniques[i % techniques.length]!;
  const dev = MOCK_DEVICES[i % MOCK_DEVICES.length]!;
  
  return {
    id: `ALT-00${47 - i}`,
    timestamp: new Date(Date.now() - i * 3600000).toISOString(),
    deviceId: dev.id,
    device: dev,
    type: tech.name,
    tactic: tech.tactic,
    technique: tech,
    severity: severities[i]!,
    confidence: 71 + (i % 29),
    status: i < 3 ? 'OPEN' : i < 8 ? 'IN_REVIEW' : i < 15 ? 'RESOLVED' : 'FALSE_POSITIVE',
    modelVersion: 'v4.2.1-DNN',
    threatIntel: [
      { type: 'HASH', value: 'a3b2c1d4e5f6...', source: 'MISP' },
      { type: 'IP', value: '185.15.2.1', source: 'AlienVault' }
    ],
    cveReference: i % 3 === 0 ? 'CVE-2023-27532' : undefined,
    featureSummary: 'Unusual outbound traffic volume detected on port 443. Payload matches known ransomware signatures.'
  };
});

export const MOCK_FL_ROUNDS: FLRound[] = Array.from({ length: 50 }).map((_, i) => ({
  round: i + 1,
  accuracy: 88 + (i * (8 / 50)) + (Math.random() * 1 - 0.5),
  fpRate: 3 - (i * (1.8 / 50)) + (Math.random() * 0.2 - 0.1),
  trainLoss: 0.8 - (i * (0.68 / 50)) + (Math.random() * 0.05 - 0.025),
  valLoss: 0.85 - (i * (0.67 / 50)) + (Math.random() * 0.05 - 0.025),
}));

export const MOCK_FL_CLIENTS: FLClient[] = [
  { id: 'Cardiology-FL-01', department: 'Cardiology', participationPct: 98, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Radiology-FL-02', department: 'Radiology', participationPct: 95, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'POISONING_SUSPECT' },
  { id: 'ICU-FL-03', department: 'ICU', participationPct: 82, lastRound: 46, dpEpsilon: 0.3, modelVersion: 'v4.2.0', status: 'DEGRADED' },
  { id: 'Surgery-FL-04', department: 'Surgery', participationPct: 99, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'ER-FL-05', department: 'ER', participationPct: 97, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Pharmacy-FL-06', department: 'Pharmacy', participationPct: 100, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Oncology-FL-07', department: 'Oncology', participationPct: 96, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Nephrology-FL-08', department: 'Nephrology', participationPct: 94, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Pediatrics-FL-09', department: 'Pediatrics', participationPct: 98, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Neurology-FL-10', department: 'Neurology', participationPct: 95, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Orthopedics-FL-11', department: 'Orthopedics', participationPct: 99, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Lab-FL-12', department: 'Lab', participationPct: 97, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'PICU-FL-13', department: 'PICU', participationPct: 96, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Imaging-FL-14', department: 'Imaging', participationPct: 98, lastRound: 47, dpEpsilon: 0.3, modelVersion: 'v4.2.1', status: 'ACTIVE' },
  { id: 'Admin-FL-15', department: 'Admin', participationPct: 45, lastRound: 12, dpEpsilon: 0.3, modelVersion: 'v4.1.0', status: 'OFFLINE' },
];

export const MOCK_INCIDENTS: Incident[] = [
  {
    id: 'INC-001',
    title: 'Ransomware — Insulin Pump Hub',
    severity: 'CRITICAL',
    status: 'TRIAGING',
    affectedDevices: [MOCK_DEVICES[1]!, MOCK_DEVICES[2]!],
    timeOpen: '47m',
    analystInitials: 'AC',
    timeline: [
      { id: 'e1', timestamp: new Date(Date.now() - 47 * 60000).toISOString(), type: 'DETECTION', description: 'DNN Classifier flagged anomalous behavior' },
      { id: 'e2', timestamp: new Date(Date.now() - 45 * 60000).toISOString(), type: 'ALERT', description: 'Alert ALT-0047 generated' },
      { id: 'e3', timestamp: new Date(Date.now() - 40 * 60000).toISOString(), type: 'PLAYBOOK_START', description: 'Ransomware Response playbook initiated' },
      { id: 'e4', timestamp: new Date(Date.now() - 35 * 60000).toISOString(), type: 'QUARANTINE', description: 'Insulin Pump Hub isolated' },
      { id: 'e5', timestamp: new Date(Date.now() - 30 * 60000).toISOString(), type: 'ANALYST_ASSIGNED', description: 'Assigned to Analyst Chen' },
    ],
    playbook: {
      id: 'pb-1',
      name: 'Ransomware Response',
      triggerCondition: 'Ransomware signature match',
      lastRun: new Date().toISOString(),
      executions: 142,
      status: 'ACTIVE',
      steps: [
        { id: 's1', stepNumber: 1, name: 'Alert Received', status: 'COMPLETED', timestamp: '00:00' },
        { id: 's2', stepNumber: 2, name: 'Threat Intel Lookup', status: 'COMPLETED', timestamp: '00:12', notes: 'Matched: LockBit 3.0 variant' },
        { id: 's3', stepNumber: 3, name: 'Device Quarantine Sent', status: 'COMPLETED', timestamp: '00:14', notes: 'Insulin Pump Hub isolated' },
        { id: 's4', stepNumber: 4, name: 'Jira Ticket Created', status: 'COMPLETED', timestamp: '00:15', notes: 'INC-2024-001' },
        { id: 's5', stepNumber: 5, name: 'Analyst Notification', status: 'COMPLETED', timestamp: '00:16' },
        { id: 's6', stepNumber: 6, name: 'Full Network Scan', status: 'RUNNING', timestamp: '02:31' },
        { id: 's7', stepNumber: 7, name: 'Forensic Capture', status: 'PENDING' },
        { id: 's8', stepNumber: 8, name: 'Executive Report', status: 'PENDING' },
      ]
    },
    ticketId: 'INC-2024-001',
    reporter: 'BastionFed SOAR',
    assignee: 'Analyst Chen',
    priority: 'P1',
    created: new Date(Date.now() - 47 * 60000).toISOString(),
    labels: ['ransomware', 'iomt', 'critical']
  },
  {
    id: 'INC-002',
    title: 'Firmware Anomaly — Ventilator',
    severity: 'HIGH',
    status: 'RESPONDING',
    affectedDevices: [MOCK_DEVICES[2]!],
    timeOpen: '2h',
    analystInitials: 'JP',
    timeline: [],
    playbook: { id: 'pb-2', name: 'Firmware Anomaly', triggerCondition: 'Hash mismatch', lastRun: new Date().toISOString(), executions: 45, status: 'ACTIVE', steps: [] },
    ticketId: 'INC-2024-002', reporter: 'BastionFed SOAR', assignee: 'Analyst Park', priority: 'P2', created: new Date(Date.now() - 120 * 60000).toISOString(), labels: ['firmware']
  },
  {
    id: 'INC-003',
    title: 'Lateral Movement — PACS Server',
    severity: 'HIGH',
    status: 'NEW',
    affectedDevices: [MOCK_DEVICES[4]!, MOCK_DEVICES[5]!, MOCK_DEVICES[6]!],
    timeOpen: '12m',
    analystInitials: 'UN',
    timeline: [],
    playbook: { id: 'pb-3', name: 'MitM Isolation', triggerCondition: 'Lateral movement', lastRun: new Date().toISOString(), executions: 89, status: 'ACTIVE', steps: [] },
    ticketId: 'INC-2024-003', reporter: 'BastionFed SOAR', assignee: 'Unassigned', priority: 'P2', created: new Date(Date.now() - 12 * 60000).toISOString(), labels: ['lateral-movement']
  },
  {
    id: 'INC-004',
    title: 'DDoS — Nurse Station Network',
    severity: 'MEDIUM',
    status: 'RESOLVED',
    affectedDevices: [MOCK_DEVICES[5]!, MOCK_DEVICES[13]!],
    timeOpen: '5h',
    analystInitials: 'AC',
    timeline: [],
    playbook: { id: 'pb-4', name: 'DDoS Mitigation', triggerCondition: 'Traffic spike', lastRun: new Date().toISOString(), executions: 210, status: 'ACTIVE', steps: [] },
    ticketId: 'INC-2024-004', reporter: 'BastionFed SOAR', assignee: 'Analyst Chen', priority: 'P3', created: new Date(Date.now() - 300 * 60000).toISOString(), labels: ['ddos']
  },
  {
    id: 'INC-005',
    title: 'CVE Exploit — MRI Unit',
    severity: 'CRITICAL',
    status: 'POST_MORTEM',
    affectedDevices: [MOCK_DEVICES[0]!],
    timeOpen: '1d',
    analystInitials: 'JP',
    timeline: [],
    playbook: { id: 'pb-5', name: 'Credential Lockout', triggerCondition: 'CVE match', lastRun: new Date().toISOString(), executions: 12, status: 'ACTIVE', steps: [] },
    ticketId: 'INC-2024-005', reporter: 'BastionFed SOAR', assignee: 'Analyst Park', priority: 'P1', created: new Date(Date.now() - 1440 * 60000).toISOString(), labels: ['cve', 'exploit']
  }
];

export const MOCK_MALWARE_SAMPLES: MalwareSample[] = [
  { 
    id: 'MAL-001', 
    sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 
    md5: 'd41d8cd98f00b204e9800998ecf8427e',
    filename: 'update_v2.4.exe',
    size: '1.2 MB',
    type: 'PE32 Executable',
    deviceId: 'dev-02', 
    timestamp: new Date().toISOString(), 
    uploadTime: new Date(Date.now() - 3600000).toISOString(),
    family: 'LockBit 3.0', 
    threatScore: 92, 
    status: 'ANALYZED',
    analysis: {
      static: {
        imports: ['kernel32.dll', 'advapi32.dll', 'ws2_32.dll'],
        strings: ['cmd.exe /c vssadmin.exe Delete Shadows /All /Quiet', 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run']
      },
      dynamic: {
        network: ['TCP 192.168.4.22:443 -> 185.14.22.1:443', 'DNS Query: c2.malicious-domain.com'],
        fileSystem: ['Created: C:\\Windows\\Temp\\payload.exe', 'Modified: C:\\Users\\Public\\Desktop\\README.txt'],
        processes: ['Spawned: vssadmin.exe', 'Injected: explorer.exe']
      }
    }
  },
  { 
    id: 'MAL-002', 
    sha256: '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 
    md5: '9e107d9d372bb6826bd81d3542a419d6',
    filename: 'firmware_patch.bin',
    size: '4.5 MB',
    type: 'ELF 32-bit LSB executable',
    deviceId: 'dev-05', 
    timestamp: new Date().toISOString(), 
    uploadTime: new Date(Date.now() - 86400000).toISOString(),
    family: 'Mirai Variant', 
    threatScore: 85, 
    status: 'ANALYZED',
    analysis: {
      static: {
        imports: ['libc.so.6'],
        strings: ['/bin/busybox', 'POST /cdn-cgi/']
      },
      dynamic: {
        network: ['TCP SYN flood to 8.8.8.8:53'],
        fileSystem: ['Deleted: /var/log/syslog'],
        processes: ['Spawned: /bin/sh']
      }
    }
  },
  { 
    id: 'MAL-003', 
    sha256: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8', 
    md5: 'e4d909c290d0fb1ca068ffaddf22cbd0',
    filename: 'config_backup.zip',
    size: '842 KB',
    type: 'ZIP archive data',
    deviceId: 'dev-01', 
    timestamp: new Date().toISOString(), 
    uploadTime: new Date().toISOString(),
    family: 'FoxBlade', 
    threatScore: 78, 
    status: 'ANALYZING',
    analysis: {
      static: { imports: [], strings: [] },
      dynamic: { network: [], fileSystem: [], processes: [] }
    }
  }
];

export const MOCK_AUDIT_LOGS: AuditLog[] = Array.from({ length: 30 }).map((_, i) => {
  const actions: ('DETECTION_MADE' | 'RESPONSE_TRIGGERED' | 'MODEL_UPDATED' | 'USER_LOGIN' | 'DEVICE_QUARANTINED' | 'CONFIG_CHANGED' | 'REPORT_GENERATED' | 'FL_ROUND_COMPLETED')[] = ['DETECTION_MADE', 'RESPONSE_TRIGGERED', 'MODEL_UPDATED', 'USER_LOGIN', 'DEVICE_QUARANTINED', 'CONFIG_CHANGED', 'REPORT_GENERATED', 'FL_ROUND_COMPLETED'];
  const actors = ['BastionFed System', 'Analyst Chen', 'Analyst Park', 'FL Aggregation Server', 'SOAR Engine'];
  return {
    id: `LOG-${1000 + i}`,
    timestamp: new Date(Date.now() - i * 1500000).toISOString(),
    actor: actors[i % actors.length]!,
    action: actions[i % actions.length]!,
    target: `Target-${i}`,
    result: 'SUCCESS',
    hash: Math.random().toString(16).substring(2, 10)
  };
});

export const MOCK_CONVERSATIONS = [
  { id: 'conv-1', preview: 'Ransomware detection on Insulin Pump Hub', timestamp: new Date(Date.now() - 3600000).toISOString() },
  { id: 'conv-2', preview: 'ATT&CK T0814 explanation', timestamp: new Date(Date.now() - 86400000).toISOString() },
  { id: 'conv-3', preview: 'FL model accuracy trend', timestamp: new Date(Date.now() - 172800000).toISOString() },
  { id: 'conv-4', preview: 'Summarize today\'s incidents', timestamp: new Date(Date.now() - 259200000).toISOString() },
  { id: 'conv-5', preview: 'Remediation for MRI Unit', timestamp: new Date(Date.now() - 345600000).toISOString() },
];

export const MOCK_RCA_REPORTS: RCAReport[] = [
  {
    id: 'RCA-001',
    incidentId: 'INC-001',
    title: 'Ransomware — Insulin Pump Hub',
    executiveSummary: 'At 03:14 UTC, BastionFed detected anomalous behavioral patterns consistent with a LockBit 3.0 ransomware variant on the ICU Insulin Pump Hub. The SOAR engine automatically quarantined the device within 2 minutes, preventing lateral movement to the adjacent Ventilator Array.',
    timelineNodes: [
      { label: 'Initial Probe', timestamp: '03:10' },
      { label: 'Port Scan', timestamp: '03:11' },
      { label: 'C2 Beacon', timestamp: '03:12' },
      { label: 'Privilege Escalation', timestamp: '03:13' },
      { label: 'Lateral Movement', timestamp: '03:13' },
      { label: 'Ransomware Drop', timestamp: '03:14' },
      { label: 'Encryption Begin', timestamp: '03:14' },
      { label: 'Detection & Response', timestamp: '03:15' },
    ],
    affectedNodes: [
      { deviceName: 'Insulin Pump Hub', ip: '192.168.4.22', impact: 'Compromised (Quarantined)' },
      { deviceName: 'Ventilator Array B3', ip: '192.168.4.50', impact: 'Scanned (No Infection)' }
    ],
    mitreChain: ['Initial Access', 'Execution', 'Lateral Movement', 'Impact'],
    responseActions: [
      'Automated network isolation of 192.168.4.22',
      'Memory dump captured via EDR agent',
      'Malware binary extracted and queued for FL training',
      'Password reset enforced for service accounts'
    ],
    recommendations: [
      'Patch CVE-2023-27532 on all pump hubs',
      'Implement micro-segmentation for ICU VLAN',
      'Update FL model with extracted IOCs'
    ]
  },
  {
    id: 'RCA-002',
    incidentId: 'INC-002',
    title: 'Firmware Anomaly — Ventilator',
    executiveSummary: 'A routine integrity check identified a firmware hash mismatch on Ventilator Array B3. Investigation revealed an unauthorized update attempt originating from an internal admin workstation.',
    timelineNodes: [], affectedNodes: [], mitreChain: [], responseActions: [], recommendations: []
  },
  {
    id: 'RCA-004',
    incidentId: 'INC-004',
    title: 'DDoS — Nurse Station Network',
    executiveSummary: 'A localized volumetric attack targeted the Oncology Nurse Station network, causing intermittent connectivity loss to the PACS Server. Traffic was successfully rerouted and scrubbed.',
    timelineNodes: [], affectedNodes: [], mitreChain: [], responseActions: [], recommendations: []
  }
];
