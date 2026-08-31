# Security Policy

## Supported versions

Security fixes are applied to the **`main`** branch. Tagged releases (when published) receive backports at the maintainers' discretion.

| Version | Supported |
|---------|-----------|
| `main`  | Yes       |

## Reporting a vulnerability

**Do not** open a public GitHub issue for security-sensitive findings (auth bypass, tenant isolation breaks, malware handling flaws, secret exposure, etc.).

Instead:

1. Use **[GitHub Private Security Advisories](https://github.com/faheemgurkani/bastionfed-system-application/security/advisories/new)** for this repository, **or**
2. Email the maintainers with subject **`[BastionFed Security]`** and include:
   - Description and impact
   - Steps to reproduce
   - Affected paths (frontend, unified backend, data plane)
   - Suggested fix (if any)

We aim to acknowledge reports within **5 business days** and share a remediation timeline when confirmed.

## Out of scope

The following are generally **not** treated as product vulnerabilities in this repository:

- Misconfiguration of demo mode (`DEMO_MODE=1`) in a production deployment
- Missing hardening when `BASTIONFED_STRICT_DATA_PLANE` is not enabled in production
- Issues in third-party services (Firebase, Supabase, Upstash, Groq) outside this codebase
- Social engineering or physical access to operator workstations

Document operational expectations in [docs/DEPLOYMENT_HARDENING_CHECKLIST.md](./docs/DEPLOYMENT_HARDENING_CHECKLIST.md) and [docs/BLUE_TEAM_APPLICATION_SPEC.md](./docs/BLUE_TEAM_APPLICATION_SPEC.md).

## Secrets and sensitive data

**Never commit:**

| Item | Location |
|------|----------|
| Firebase / API keys | `frontend/.env.local` |
| Backend secrets | `backend/.env` |
| Service role keys | Supabase, Upstash, Groq env vars |
| Malware binaries / patient-like data | Use gitignored `backend/data/`, not the repo |
| SQLite with real user data | `backend/data/runtime/` |

If secrets were committed:

1. Rotate them immediately in the provider console
2. Remove from git history or use `git rm --cached` and force-push only after rotation (coordinate with the team)
3. See [CONTRIBUTING.md](./CONTRIBUTING.md) § Secrets

## Secure development

- Run production-like stacks with [docs/DEPLOYMENT_HARDENING_CHECKLIST.md](./docs/DEPLOYMENT_HARDENING_CHECKLIST.md)
- Follow [docs/FORENSICS_HANDLING_SOP.md](./docs/FORENSICS_HANDLING_SOP.md) for sample handling
- Keep `PyJWT[crypto]` installed in backend deployments (Firebase JWT verification)
- Review tenant scoping before changing auth or store layers

## Disclosure

We prefer coordinated disclosure. Public credit is given when reporters agree and the issue is resolved.
