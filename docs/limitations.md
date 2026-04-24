# Limitations

- This is a **prototype**, not a production deployment.
- Auth is static API-key based (no OIDC/IAM integration yet).
- No service mesh/mTLS by default.
- Local overlay uses hash embeddings for reliability; this favors reproducibility over semantic quality.
- HPA requires metrics pipeline support (e.g., `metrics-server`) and may not scale in minimal clusters.
- Production operations still require hardening: backup/restore, secret manager integration, policy enforcement, and SLO-driven scaling.
