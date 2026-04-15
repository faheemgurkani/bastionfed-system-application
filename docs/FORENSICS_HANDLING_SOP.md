# Forensics Handling SOP

1. Upload a binary through `POST /api/forensics/samples`.
2. Confirm the sample enters `QUEUED` with an initial chain-of-custody entry.
3. Run the scanner transition with `POST /api/forensics/samples/{sample_id}/scan`.
4. Move the sample into quarantine or release it with:
   - `POST /api/forensics/samples/{sample_id}/quarantine`
   - `POST /api/forensics/samples/{sample_id}/release`
5. Expire retained content with `POST /api/forensics/samples/{sample_id}/expire`.
6. Use the signed download endpoint only while `retentionStatus != EXPIRED`.

This SOP records product states and evidence links. Malware detonation safety, legal review, isolation environment design, and final retention policy remain organizational controls.
