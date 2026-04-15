# Deployment Hardening Checklist

- Enable `BASTIONFED_STRICT_DATA_PLANE=1` in non-demo environments.
- Verify `DATABASE_URL` / `SUPABASE_DATABASE_URL`, Storage, and Redis all pass `/health/ready`.
- Document backup ownership, restore testing cadence, and target RTO/RPO outside the application.
- Review IAM for Firebase, Supabase service role usage, and connector secret custody.
- Restrict demo mode to explicit demo environments; production tenants should start empty.
- Review tenant enforcement before any future RLS rollout.
- Export and archive audit evidence on the cadence required by your organization.
- Treat FL/per-client drift screens as research/demo unless external telemetry has been integrated and validated.
