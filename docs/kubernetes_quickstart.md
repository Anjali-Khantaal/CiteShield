# Kubernetes quickstart

## Local (kind/minikube)
1. `make build`
2. Load image to cluster (for kind: `make kind-load`)
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

Example secret creation:

```bash
kubectl -n rag-app create secret generic citeshield-app-secrets \
  --from-literal=TENANT_A_API_KEY='<set-tenant-a-key>' \
  --from-literal=TENANT_B_API_KEY='<set-tenant-b-key>' \
  --from-literal=SUPERUSER_API_KEY='<set-superuser-key>'
```

## Monitoring operator option

If the cluster has the Prometheus Operator CRDs installed, deploy the monitoring overlay:

```bash
make k8s-deploy-monitoring
```

This overlay includes everything from `deploy/k8s/overlays/local` plus `deploy/k8s/servicemonitor.yaml`.

Use the default `make k8s-deploy` path for plain kind/minikube clusters without Prometheus Operator CRDs. Use `make k8s-deploy-monitoring` only when this command succeeds:

```bash
kubectl get crd servicemonitors.monitoring.coreos.com
```

Clean up the monitoring overlay with:

```bash
make k8s-clean-monitoring
```

## Proof commands

Use these after deployment to capture reviewer-facing evidence:

```bash
kubectl get pods -A
kubectl get svc -A
kubectl -n rag-app rollout status deploy/citeshield-api
kubectl -n vector-db rollout status deploy/citeshield-qdrant
make k8s-smoke
```

## Operational notes
- HPA requires cluster resource metrics (typically `metrics-server`).
- API NetworkPolicy includes DNS egress so service discovery works.
- Qdrant ingress is restricted to API pods in `rag-app`.
- API ingress is allowed from `rag-app` clients and the `monitoring` namespace.
