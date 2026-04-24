#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="rag-app"
SERVICE="citeshield-api"

kubectl -n "${NAMESPACE}" rollout status deploy/citeshield-api --timeout=180s
kubectl -n "${NAMESPACE}" get svc "${SERVICE}" >/dev/null

POD=$(kubectl -n "${NAMESPACE}" get pod -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')
kubectl -n "${NAMESPACE}" exec "${POD}" -- python - <<'PY'
import urllib.request
urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10).read()
urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=10).read()
PY

echo "Kubernetes smoke test passed"
