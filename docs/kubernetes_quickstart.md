# Kubernetes quickstart

## Local (kind/minikube)
1. `make build`
2. Load image to cluster (for kind: `kind load docker-image citeshield-api:local`)
3. `make k8s-deploy`
4. `make k8s-smoke`
5. `make k8s-clean`

This uses `deploy/k8s/overlays/local` with safe dev secrets.

## Production template
- Use `deploy/k8s/overlays/prod-template`.
- Create `citeshield-app-secrets` out-of-band using `kubectl create secret generic`.
- Do not apply placeholder secret templates directly in production.
