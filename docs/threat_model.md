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

## Tested attacks
- Tenant request bodies that claim another `tenant_id` are ignored.
- Tenant ingest requests that try to target another tenant are stored under the authenticated tenant.
- Query retrieval is filtered by authenticated tenant metadata in Qdrant.
- Cross-tenant evaluation cases are expected to abstain and return no citations.

## Prototype limitations
- Static API keys are acceptable only for local demos and tests.
- Production should use OIDC/CERN SSO, short-lived credentials, RBAC, and audited service identities.
- Production secrets should be managed with Vault, sealed secrets, or Kubernetes External Secrets rather than committed manifests.
- NetworkPolicy depends on a CNI that enforces Kubernetes network policies.
- This prototype does not claim protection against compromised cluster administrators, malicious model providers, prompt-injection-resistant data sanitisation, or browser-side compromise.
