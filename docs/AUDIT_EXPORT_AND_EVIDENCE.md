# Audit Export And Evidence

Use `GET /api/audit/export?format=jsonl` for NDJSON exports or `format=csv` for analyst-friendly spreadsheet review.

Recommended evidence bundle:

1. Export audit logs for the incident window.
2. Export connector configuration history from the audit stream.
3. Capture forensics sample state, scanner verdict, and chain-of-custody entries.
4. Attach dashboard screenshots only as supporting evidence, not source of truth.
5. Store the export in your organization-approved evidence repository with its own retention and legal-hold controls.

`audit_log` is the product source of truth for tenant activity. WORM storage, SIEM retention, and legal hold remain deployment responsibilities.
