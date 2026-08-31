# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where releases are tagged.

## [Unreleased]

### Added

- Root governance docs: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`
- `README.md`, `docs/README.md`, `docs/LOCAL_TESTING.md`, `frontend/.env.example`

### Changed

- Documentation consolidated around unified `backend/` entrypoint
- `.gitignore` expanded for local ML artefacts, demo data, and Python caches

### Removed

- Redundant Faheem gap-remediation and manual test plan docs (superseded by unified testing guide)

## [0.1.0] - 2026-04-16

### Added

- Unified FastAPI backend with tenant-scoped data plane (Postgres, Redis, Storage)
- Next.js SOC frontend: alerts, incidents, FL health, forensics, audit, BastionBot
- Firebase Auth integration and BastionBot Groq ask-mode

[Unreleased]: https://github.com/faheemgurkani/bastionfed-system-application/compare/v0.1.0...main
[0.1.0]: https://github.com/faheemgurkani/bastionfed-system-application/releases/tag/v0.1.0
