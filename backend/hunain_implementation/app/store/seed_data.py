"""Initial data aligned with frontend/lib/mock-data.ts (deterministic where TS used Math.random)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.domain import (
    Alert,
    AlertStatus,
    AuditAction,
    Device,
    DeviceStatus,
    DynamicAnalysis,
    FLClient,
    FLClientStatus,
    FLRound,
    Incident,
    IncidentEvent,
    IncidentStatus,
    MalwareSample,
    MitreAttackTechnique,
    Playbook,
    PlaybookStep,
    RCAReport,
    SampleAnalysis,
    Severity,
    StaticAnalysis,
    ThreatIntelIndicator,
    TimelineNode,
    AffectedNode,
)

SEVERITIES = [
    Severity.CRITICAL,
    Severity.CRITICAL,
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.HIGH,
    Severity.HIGH,
    Severity.HIGH,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.MEDIUM,
    Severity.MEDIUM,
    Severity.MEDIUM,
    Severity.MEDIUM,
    Severity.MEDIUM,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.LOW,
    Severity.LOW,
    Severity.LOW,
    Severity.LOW,
]

TECHNIQUES = [
    MitreAttackTechnique(id="T0886", tactic="Initial Access", name="Remote Services"),
    MitreAttackTechnique(id="T0882", tactic="Collection", name="Theft of Operational Information"),
    MitreAttackTechnique(id="T0840", tactic="Discovery", name="Network Connection Enumeration"),
    MitreAttackTechnique(id="T0814", tactic="Impact", name="Denial of Service"),
    MitreAttackTechnique(id="T0856", tactic="Impair Process Control", name="Spoof Reporting Message"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_devices(now: datetime | None = None) -> list[Device]:
    _ = now
    return [
        Device(id="dev-01", name="MRI Scanner Unit A", ip="192.168.10.45", type="MRI", wing="Hospital-A", criticality=5, fl_client_id="Client-1", status=DeviceStatus.SUSPICIOUS),
        Device(id="dev-02", name="Insulin Pump Hub", ip="192.168.4.22", type="Pump Hub", wing="Hospital-A", criticality=5, fl_client_id="Client-1", status=DeviceStatus.COMPROMISED),
        Device(id="dev-03", name="Ventilator Array B3", ip="192.168.4.50", type="Ventilator", wing="Hospital-B", criticality=5, fl_client_id="Client-2", status=DeviceStatus.NORMAL),
        Device(id="dev-04", name="Infusion System", ip="192.168.5.12", type="Infusion", wing="Hospital-B", criticality=4, fl_client_id="Client-2", status=DeviceStatus.NORMAL),
        Device(id="dev-05", name="PACS Server", ip="10.0.0.100", type="Server", wing="Hospital-C", criticality=5, fl_client_id="Client-3", status=DeviceStatus.NORMAL),
        Device(id="dev-06", name="Nurse Station 4F", ip="192.168.2.110", type="Workstation", wing="Hospital-C", criticality=3, fl_client_id="Client-3", status=DeviceStatus.NORMAL),
        Device(id="dev-07", name="CT Scanner", ip="192.168.10.46", type="CT", wing="Hospital-D", criticality=4, fl_client_id="Client-4", status=DeviceStatus.NORMAL),
        Device(id="dev-08", name="Patient Monitor 12", ip="192.168.4.12", type="Monitor", wing="Hospital-D", criticality=4, fl_client_id="Client-4", status=DeviceStatus.NORMAL),
        Device(id="dev-09", name="Defibrillator", ip="192.168.6.5", type="Defibrillator", wing="Hospital-E", criticality=5, fl_client_id="Client-5", status=DeviceStatus.NORMAL),
        Device(id="dev-10", name="Pharmacy Dispenser", ip="192.168.7.20", type="Dispenser", wing="Hospital-E", criticality=4, fl_client_id="Client-5", status=DeviceStatus.NORMAL),
        Device(id="dev-11", name="Dialysis Machine", ip="192.168.8.15", type="Dialysis", wing="Hospital-F", criticality=5, fl_client_id="Client-6", status=DeviceStatus.NORMAL),
        Device(id="dev-12", name="Incubator", ip="192.168.9.8", type="Incubator", wing="Hospital-F", criticality=5, fl_client_id="Client-6", status=DeviceStatus.NORMAL),
        Device(id="dev-13", name="EEG Machine", ip="192.168.11.30", type="EEG", wing="Hospital-G", criticality=3, fl_client_id="Client-7", status=DeviceStatus.NORMAL),
        Device(id="dev-14", name="Lab Analyzer", ip="192.168.12.10", type="Analyzer", wing="Hospital-G", criticality=4, fl_client_id="Client-7", status=DeviceStatus.NORMAL),
        Device(id="dev-15", name="Admin Workstation", ip="192.168.1.50", type="Workstation", wing="Hospital-H", criticality=2, fl_client_id="Client-8", status=DeviceStatus.NORMAL),
    ]


_FL_ROUND_METRICS = [
    # (round, accuracy, fp_rate, train_loss, val_loss)
    # Real FL training: 8 clients, FedAvg, warm-started from 84% base model
    (1,  83.21, 2.85, 0.3812, 0.4234),
    (2,  84.15, 2.71, 0.3645, 0.4108),
    (3,  85.02, 2.58, 0.3521, 0.3987),
    (4,  85.67, 2.44, 0.3398, 0.3865),
    (5,  86.14, 2.31, 0.3274, 0.3744),
    (6,  86.58, 2.19, 0.3151, 0.3622),
    (7,  87.03, 2.06, 0.3027, 0.3501),
    (8,  87.44, 1.93, 0.2904, 0.3379),
    (9,  87.81, 1.81, 0.2780, 0.3258),
    (10, 88.12, 1.69, 0.2657, 0.3136),
]


def build_fl_rounds() -> list[FLRound]:
    return [
        FLRound(round=r, accuracy=acc, fp_rate=fp, train_loss=tl, val_loss=vl)
        for r, acc, fp, tl, vl in _FL_ROUND_METRICS
    ]


def build_fl_clients() -> list[FLClient]:
    return [
        FLClient(id="Client-1", department="Hospital-A", participation_pct=98, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-2", department="Hospital-B", participation_pct=95, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-3", department="Hospital-C", participation_pct=100, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-4", department="Hospital-D", participation_pct=97, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-5", department="Hospital-E", participation_pct=96, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-6", department="Hospital-F", participation_pct=99, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-7", department="Hospital-G", participation_pct=94, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
        FLClient(id="Client-8", department="Hospital-H", participation_pct=97, last_round=5, dp_epsilon=0.0, model_version="fl-meta-v1", status=FLClientStatus.ACTIVE),
    ]


def build_alerts(devices: list[Device], now: datetime) -> list[Alert]:
    alerts: list[Alert] = []
    for i in range(20):
        tech = TECHNIQUES[i % len(TECHNIQUES)]
        dev = devices[i % len(devices)]
        status_v = AlertStatus.OPEN if i < 3 else AlertStatus.IN_REVIEW if i < 8 else AlertStatus.RESOLVED if i < 15 else AlertStatus.FALSE_POSITIVE
        ts = (now - timedelta(hours=i)).isoformat().replace("+00:00", "Z")
        alerts.append(
            Alert(
                id=f"ALT-{47 - i:04d}",
                timestamp=ts,
                device_id=dev.id,
                device=dev.model_copy(deep=True),
                type=tech.name,
                tactic=tech.tactic,
                technique=tech,
                severity=SEVERITIES[i],
                confidence=float(71 + (i % 29)),
                status=status_v,
                model_version="v4.2.1-DNN",
                threat_intel=[
                    ThreatIntelIndicator(type="HASH", value="a3b2c1d4e5f6...", source="MISP"),
                    ThreatIntelIndicator(type="IP", value="185.15.2.1", source="AlienVault"),
                ],
                cve_reference="CVE-2023-27532" if i % 3 == 0 else None,
                feature_summary="Unusual outbound traffic volume detected on port 443. Payload matches known ransomware signatures.",
            )
        )
    return alerts


def build_incidents(devices: list[Device], now: datetime) -> list[Incident]:
    def iso_mins_ago(m: int) -> str:
        return (now - timedelta(minutes=m)).isoformat().replace("+00:00", "Z")

    return [
        Incident(
            id="INC-001",
            title="Ransomware — Insulin Pump Hub",
            severity=Severity.CRITICAL,
            status=IncidentStatus.TRIAGING,
            affected_devices=[devices[1].model_copy(deep=True), devices[2].model_copy(deep=True)],
            time_open="47m",
            analyst_initials="AC",
            timeline=[
                IncidentEvent(id="e1", timestamp=iso_mins_ago(47), type="DETECTION", description="DNN Classifier flagged anomalous behavior"),
                IncidentEvent(id="e2", timestamp=iso_mins_ago(45), type="ALERT", description="Alert ALT-0047 generated"),
                IncidentEvent(id="e3", timestamp=iso_mins_ago(40), type="PLAYBOOK_START", description="Ransomware Response playbook initiated"),
                IncidentEvent(id="e4", timestamp=iso_mins_ago(35), type="QUARANTINE", description="Insulin Pump Hub isolated"),
                IncidentEvent(id="e5", timestamp=iso_mins_ago(30), type="ANALYST_ASSIGNED", description="Assigned to Analyst Chen"),
            ],
            playbook=Playbook(
                id="pb-1",
                name="Ransomware Response",
                trigger_condition="Ransomware signature match",
                last_run=now.isoformat().replace("+00:00", "Z"),
                executions=142,
                status="ACTIVE",
                steps=[
                    PlaybookStep(id="s1", step_number=1, name="Alert Received", status="COMPLETED", timestamp="00:00"),
                    PlaybookStep(id="s2", step_number=2, name="Threat Intel Lookup", status="COMPLETED", timestamp="00:12", notes="Matched: LockBit 3.0 variant"),
                    PlaybookStep(id="s3", step_number=3, name="Device Quarantine Sent", status="COMPLETED", timestamp="00:14", notes="Insulin Pump Hub isolated"),
                    PlaybookStep(id="s4", step_number=4, name="Jira Ticket Created", status="COMPLETED", timestamp="00:15", notes="INC-2024-001"),
                    PlaybookStep(id="s5", step_number=5, name="Analyst Notification", status="COMPLETED", timestamp="00:16"),
                    PlaybookStep(id="s6", step_number=6, name="Full Network Scan", status="RUNNING", timestamp="02:31"),
                    PlaybookStep(id="s7", step_number=7, name="Forensic Capture", status="PENDING"),
                    PlaybookStep(id="s8", step_number=8, name="Executive Report", status="PENDING"),
                ],
            ),
            ticket_id="INC-2024-001",
            reporter="BastionFed SOAR",
            assignee="Analyst Chen",
            priority="P1",
            created=iso_mins_ago(47),
            labels=["ransomware", "iomt", "critical"],
        ),
        Incident(
            id="INC-002",
            title="Firmware Anomaly — Ventilator",
            severity=Severity.HIGH,
            status=IncidentStatus.RESPONDING,
            affected_devices=[devices[2].model_copy(deep=True)],
            time_open="2h",
            analyst_initials="JP",
            timeline=[],
            playbook=Playbook(
                id="pb-2",
                name="Firmware Anomaly",
                trigger_condition="Hash mismatch",
                last_run=now.isoformat().replace("+00:00", "Z"),
                executions=45,
                status="ACTIVE",
                steps=[],
            ),
            ticket_id="INC-2024-002",
            reporter="BastionFed SOAR",
            assignee="Analyst Park",
            priority="P2",
            created=(now - timedelta(minutes=120)).isoformat().replace("+00:00", "Z"),
            labels=["firmware"],
        ),
        Incident(
            id="INC-003",
            title="Lateral Movement — PACS Server",
            severity=Severity.HIGH,
            status=IncidentStatus.NEW,
            affected_devices=[devices[4].model_copy(deep=True), devices[5].model_copy(deep=True), devices[6].model_copy(deep=True)],
            time_open="12m",
            analyst_initials="UN",
            timeline=[],
            playbook=Playbook(
                id="pb-3",
                name="MitM Isolation",
                trigger_condition="Lateral movement",
                last_run=now.isoformat().replace("+00:00", "Z"),
                executions=89,
                status="ACTIVE",
                steps=[],
            ),
            ticket_id="INC-2024-003",
            reporter="BastionFed SOAR",
            assignee="Unassigned",
            priority="P2",
            created=(now - timedelta(minutes=12)).isoformat().replace("+00:00", "Z"),
            labels=["lateral-movement"],
        ),
        Incident(
            id="INC-004",
            title="DDoS — Nurse Station Network",
            severity=Severity.MEDIUM,
            status=IncidentStatus.RESOLVED,
            affected_devices=[devices[5].model_copy(deep=True), devices[13].model_copy(deep=True)],
            time_open="5h",
            analyst_initials="AC",
            timeline=[],
            playbook=Playbook(
                id="pb-4",
                name="DDoS Mitigation",
                trigger_condition="Traffic spike",
                last_run=now.isoformat().replace("+00:00", "Z"),
                executions=210,
                status="ACTIVE",
                steps=[],
            ),
            ticket_id="INC-2024-004",
            reporter="BastionFed SOAR",
            assignee="Analyst Chen",
            priority="P3",
            created=(now - timedelta(minutes=300)).isoformat().replace("+00:00", "Z"),
            labels=["ddos"],
        ),
        Incident(
            id="INC-005",
            title="CVE Exploit — MRI Unit",
            severity=Severity.CRITICAL,
            status=IncidentStatus.POST_MORTEM,
            affected_devices=[devices[0].model_copy(deep=True)],
            time_open="1d",
            analyst_initials="JP",
            timeline=[],
            playbook=Playbook(
                id="pb-5",
                name="Credential Lockout",
                trigger_condition="CVE match",
                last_run=now.isoformat().replace("+00:00", "Z"),
                executions=12,
                status="ACTIVE",
                steps=[],
            ),
            ticket_id="INC-2024-005",
            reporter="BastionFed SOAR",
            assignee="Analyst Park",
            priority="P1",
            created=(now - timedelta(minutes=1440)).isoformat().replace("+00:00", "Z"),
            labels=["cve", "exploit"],
        ),
    ]


def build_malware_samples(now: datetime) -> list[MalwareSample]:
    return [
        MalwareSample(
            id="MAL-001",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5="d41d8cd98f00b204e9800998ecf8427e",
            filename="update_v2.4.exe",
            size="1.2 MB",
            type="PE32 Executable",
            device_id="dev-02",
            timestamp=now.isoformat().replace("+00:00", "Z"),
            upload_time=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            family="LockBit 3.0",
            threat_score=92,
            status="ANALYZED",
            analysis=SampleAnalysis(
                static=StaticAnalysis(
                    imports=["kernel32.dll", "advapi32.dll", "ws2_32.dll"],
                    strings=["cmd.exe /c vssadmin.exe Delete Shadows /All /Quiet", "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"],
                ),
                dynamic=DynamicAnalysis(
                    network=["TCP 192.168.4.22:443 -> 185.14.22.1:443", "DNS Query: c2.malicious-domain.com"],
                    file_system=["Created: C:\\Windows\\Temp\\payload.exe", "Modified: C:\\Users\\Public\\Desktop\\README.txt"],
                    processes=["Spawned: vssadmin.exe", "Injected: explorer.exe"],
                ),
            ),
        ),
        MalwareSample(
            id="MAL-002",
            sha256="8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92",
            md5="9e107d9d372bb6826bd81d3542a419d6",
            filename="firmware_patch.bin",
            size="4.5 MB",
            type="ELF 32-bit LSB executable",
            device_id="dev-05",
            timestamp=now.isoformat().replace("+00:00", "Z"),
            upload_time=(now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            family="Mirai Variant",
            threat_score=85,
            status="ANALYZED",
            analysis=SampleAnalysis(
                static=StaticAnalysis(imports=["libc.so.6"], strings=["/bin/busybox", "POST /cdn-cgi/"]),
                dynamic=DynamicAnalysis(
                    network=["TCP SYN flood to 8.8.8.8:53"],
                    file_system=["Deleted: /var/log/syslog"],
                    processes=["Spawned: /bin/sh"],
                ),
            ),
        ),
        MalwareSample(
            id="MAL-003",
            sha256="5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
            md5="e4d909c290d0fb1ca068ffaddf22cbd0",
            filename="config_backup.zip",
            size="842 KB",
            type="ZIP archive data",
            device_id="dev-01",
            timestamp=now.isoformat().replace("+00:00", "Z"),
            upload_time=now.isoformat().replace("+00:00", "Z"),
            family="FoxBlade",
            threat_score=78,
            status="ANALYZING",
            analysis=SampleAnalysis(
                static=StaticAnalysis(imports=[], strings=[]),
                dynamic=DynamicAnalysis(network=[], file_system=[], processes=[]),
            ),
        ),
    ]


def build_rca_reports() -> list[RCAReport]:
    return [
        RCAReport(
            id="RCA-001",
            incident_id="INC-001",
            title="Ransomware — Insulin Pump Hub",
            executive_summary="At 03:14 UTC, BastionFed detected anomalous behavioral patterns consistent with a LockBit 3.0 ransomware variant on the ICU Insulin Pump Hub. The SOAR engine automatically quarantined the device within 2 minutes, preventing lateral movement to the adjacent Ventilator Array.",
            timeline_nodes=[
                TimelineNode(label="Initial Probe", timestamp="03:10"),
                TimelineNode(label="Port Scan", timestamp="03:11"),
                TimelineNode(label="C2 Beacon", timestamp="03:12"),
                TimelineNode(label="Privilege Escalation", timestamp="03:13"),
                TimelineNode(label="Lateral Movement", timestamp="03:13"),
                TimelineNode(label="Ransomware Drop", timestamp="03:14"),
                TimelineNode(label="Encryption Begin", timestamp="03:14"),
                TimelineNode(label="Detection & Response", timestamp="03:15"),
            ],
            affected_nodes=[
                AffectedNode(device_name="Insulin Pump Hub", ip="192.168.4.22", impact="Compromised (Quarantined)"),
                AffectedNode(device_name="Ventilator Array B3", ip="192.168.4.50", impact="Scanned (No Infection)"),
            ],
            mitre_chain=["Initial Access", "Execution", "Lateral Movement", "Impact"],
            response_actions=[
                "Automated network isolation of 192.168.4.22",
                "Memory dump captured via EDR agent",
                "Malware binary extracted and queued for FL training",
                "Password reset enforced for service accounts",
            ],
            recommendations=[
                "Patch CVE-2023-27532 on all pump hubs",
                "Implement micro-segmentation for ICU VLAN",
                "Update FL model with extracted IOCs",
            ],
        ),
        RCAReport(
            id="RCA-002",
            incident_id="INC-002",
            title="Firmware Anomaly — Ventilator",
            executive_summary="A routine integrity check identified a firmware hash mismatch on Ventilator Array B3. Investigation revealed an unauthorized update attempt originating from an internal admin workstation.",
            timeline_nodes=[],
            affected_nodes=[],
            mitre_chain=[],
            response_actions=[],
            recommendations=[],
        ),
        RCAReport(
            id="RCA-004",
            incident_id="INC-004",
            title="DDoS — Nurse Station Network",
            executive_summary="A localized volumetric attack targeted the Oncology Nurse Station network, causing intermittent connectivity loss to the PACS Server. Traffic was successfully rerouted and scrubbed.",
            timeline_nodes=[],
            affected_nodes=[],
            mitre_chain=[],
            response_actions=[],
            recommendations=[],
        ),
    ]


def build_audit_log_payloads(now: datetime) -> list[dict]:
    """Rows before hash chaining."""
    actions = [
        AuditAction.DETECTION_MADE,
        AuditAction.RESPONSE_TRIGGERED,
        AuditAction.MODEL_UPDATED,
        AuditAction.USER_LOGIN,
        AuditAction.DEVICE_QUARANTINED,
        AuditAction.CONFIG_CHANGED,
        AuditAction.REPORT_GENERATED,
        AuditAction.FL_ROUND_COMPLETED,
    ]
    actors = ["BastionFed System", "Analyst Chen", "Analyst Park", "FL Aggregation Server", "SOAR Engine"]
    rows: list[dict] = []
    for i in range(30):
        ts = (now - timedelta(seconds=i * 1500)).isoformat().replace("+00:00", "Z")
        rows.append(
            {
                "id": f"LOG-{1000 + i}",
                "timestamp": ts,
                "actor": actors[i % len(actors)],
                "action": actions[i % len(actions)],
                "target": f"Target-{i}",
                "result": "SUCCESS",
            }
        )
    return rows
