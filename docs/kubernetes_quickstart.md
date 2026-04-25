# Kubernetes quickstart

## Local (kind/minikube)
1. `make build`
2. Load image to cluster (for kind: `kind load docker-image citeshield-api:local`)
3. `make k8s-deploy`
4. `make k8s-smoke`
5. `make k8s-clean`

This uses `deploy/k8s/overlays/local` with:
- safe dev secrets
- `EMBEDDING_BACKEND=hash` for offline-safe smoke tests

## Production template
- Use `deploy/k8s/overlays/prod-template`.
- Create `citeshield-app-secrets` out-of-band using `kubectl create secret generic`.
- Base/prod can use `EMBEDDING_BACKEND=sentence_transformers`.
- Do not apply placeholder secret templates directly in production.

## Operational notes
- HPA requires cluster resource metrics (typically `metrics-server`).
- API NetworkPolicy includes DNS egress so service discovery works.
