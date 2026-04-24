# Threat model

## Assets
- Tenant documents and retrieval outputs.
- API keys for tenant/superuser access.

## Risks
- Cross-tenant data exposure through retrieval filters.
- Secret leakage in logs or Git.
- Overly-permissive network paths in Kubernetes.

## Controls
- Server-side tenant resolution by API key.
- No API keys or raw docs/questions in structured logs.
- Kubernetes NetworkPolicies restricting API↔Qdrant and metrics scraping.
- Secret templates committed; real values created manually.
