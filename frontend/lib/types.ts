export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type AlertStatus = 'OPEN' | 'IN_REVIEW' | 'RESOLVED' | 'FALSE_POSITIVE';
export type FLClientStatus = 'ACTIVE' | 'DEGRADED' | 'OFFLINE' | 'POISONING_SUSPECT';
export type IncidentStatus = 'NEW' | 'TRIAGING' | 'RESPONDING' | 'RESOLVED' | 'POST_MORTEM';
export type PlaybookStepStatus = 'COMPLETED' | 'RUNNING' | 'PENDING';

export interface Device {
  id: string;
  name: string;
  ip: string;
  type: string;
  wing: string;
  criticality: number; // 1-5
  flClientId: string;
  status: 'NORMAL' | 'SUSPICIOUS' | 'COMPROMISED' | 'ISOLATED';
}

export interface MitreAttackTechnique {
  id: string;
  tactic: string;
  name: string;
}

export interface ThreatIntelIndicator {
  type: 'HASH' | 'IP' | 'DOMAIN';
  value: string;
  source: string;
}

export interface Alert {
  id: string;
  timestamp: string;
  deviceId: string;
  device: Device;
  type: string;
  tactic: string;
  technique: MitreAttackTechnique;
  severity: Severity;
  confidence: number;
  status: AlertStatus;
  modelVersion: string;
  threatIntel: ThreatIntelIndicator[];
  cveReference?: string | undefined;
  featureSummary: string;
}

export interface FLRound {
  round: number;
  accuracy: number;
  fpRate: number;
  trainLoss: number;
  valLoss: number;
}

export interface FLClient {
  id: string;
  department: string;
  participationPct: number;
  lastRound: number;
  dpEpsilon: number;
  modelVersion: string;
  status: FLClientStatus;
}

export interface IncidentEvent {
  id: string;
  timestamp: string;
  type: 'DETECTION' | 'ALERT' | 'PLAYBOOK_START' | 'QUARANTINE' | 'ANALYST_ASSIGNED' | 'RESOLVED';
  description: string;
}

export interface PlaybookStep {
  id: string;
  stepNumber: number;
  name: string;
  status: PlaybookStepStatus;
  timestamp?: string;
  notes?: string;
}

export interface Playbook {
  id: string;
  name: string;
  triggerCondition: string;
  lastRun: string;
  executions: number;
  status: 'ACTIVE' | 'DRAFT' | 'DEPRECATED';
  steps: PlaybookStep[];
}

export interface Incident {
  id: string;
  title: string;
  severity: Severity;
  status: IncidentStatus;
  affectedDevices: Device[];
  timeOpen: string;
  analystInitials: string;
  timeline: IncidentEvent[];
  playbook: Playbook;
  ticketId: string;
  reporter: string;
  assignee: string;
  priority: string;
  created: string;
  labels: string[];
}

export interface MalwareSample {
  id: string;
  sha256: string;
  md5: string;
  filename: string;
  size: string;
  type: string;
  deviceId: string;
  timestamp: string;
  uploadTime: string;
  family: string;
  threatScore: number;
  status: 'COMPLETED' | 'IN_PROGRESS' | 'PENDING' | 'ANALYZED' | 'ANALYZING';
  analysis: {
    static: {
      imports: string[];
      strings: string[];
    };
    dynamic: {
      network: string[];
      fileSystem: string[];
      processes: string[];
    };
  };
}

export interface RCAReport {
  id: string;
  incidentId: string;
  title: string;
  executiveSummary: string;
  timelineNodes: { label: string; timestamp: string }[];
  affectedNodes: { deviceName: string; ip: string; impact: string }[];
  mitreChain: string[];
  responseActions: string[];
  recommendations: string[];
}

export interface AuditLog {
  id: string;
  timestamp: string;
  actor: string;
  action: 'DETECTION_MADE' | 'RESPONSE_TRIGGERED' | 'MODEL_UPDATED' | 'USER_LOGIN' | 'DEVICE_QUARANTINED' | 'CONFIG_CHANGED' | 'REPORT_GENERATED' | 'FL_ROUND_COMPLETED';
  target: string;
  result: string;
  hash: string;
}

export interface BotMessage {
  id: string;
  role: 'USER' | 'BOT';
  content: string;
  timestamp: string;
}

/** Firestore user profile document at users/{uid} */
export interface UserProfile {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  createdAt: import('firebase/firestore').FieldValue;
  lastLoginAt: import('firebase/firestore').FieldValue;
}
