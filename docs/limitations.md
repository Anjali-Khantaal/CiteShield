# Limitations

- This is a **prototype**, not a production deployment.
- Auth is static API-key based (no OIDC/IAM integration yet).
- No service mesh/mTLS by default.
- Default local performance is optimized for reproducibility, not scale.
- Production operations still require hardening: backup/restore, secret manager integration, policy enforcement, and SLO-driven scaling.
