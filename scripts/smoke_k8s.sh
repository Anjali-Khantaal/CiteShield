#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${CITESHIELD_K8S_NAMESPACE:-rag-app}"
SERVICE="${CITESHIELD_K8S_SERVICE:-citeshield-api}"
TENANT_KEY="${CITESHIELD_TENANT_API_KEY:-${TENANT_A_API_KEY:-tenant-a-dev-key}}"
LOCAL_PORT="${CITESHIELD_LOCAL_PORT:-18000}"

kubectl -n "${NAMESPACE}" rollout status deploy/citeshield-api --timeout=180s
kubectl -n "${NAMESPACE}" get svc "${SERVICE}" >/dev/null

kubectl -n "${NAMESPACE}" port-forward svc/${SERVICE} "${LOCAL_PORT}:80" >/tmp/citeshield-port-forward.log 2>&1 &
PF_PID=$!
cleanup() {
  kill "${PF_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT
sleep 3

BASE_URL="http://127.0.0.1:${LOCAL_PORT}"

curl -fsS "${BASE_URL}/health" >/dev/null
curl -fsS "${BASE_URL}/metrics" >/dev/null
curl -fsS -X POST "${BASE_URL}/ingest" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${TENANT_KEY}" \
  --data '{"source":"smoke-k8s.md","text":"Employees must use VPN for internal dashboards."}' >/dev/null
curl -fsS -X POST "${BASE_URL}/query" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${TENANT_KEY}" \
  --data '{"question":"What is the VPN rule?","top_k":3}' >/dev/null

echo "Kubernetes smoke test passed"
