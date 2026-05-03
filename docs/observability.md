# Observability

## Start stack
```bash
docker compose -f observability/docker-compose.observability.yaml up -d
```

- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`
- Grafana login: `${GRAFANA_ADMIN_USER:-admin}` / `${GRAFANA_ADMIN_PASSWORD:-admin}`

Grafana is provisioned automatically with:
- Prometheus datasource (`observability/grafana/provisioning/datasources/prometheus.yaml`)
- Dashboard provider (`observability/grafana/provisioning/dashboards/dashboard-provider.yaml`)
- Dashboard JSON (`observability/grafana/dashboards/citeshield-dashboard.json`)

Prometheus includes `host.docker.internal` host-gateway mapping for Linux compatibility.

## Metrics scope
- request count + HTTP latency
- retrieval and generation latency
- Qdrant operation latency
- ingest/retrieval errors
- abstentions/citations
- latest citation count and query `top_k`
- cross-tenant evaluation failure counter
- indexed chunk gauge
- evaluation summary gauges
- multimodal-derived chunks are included in the same request, query, citation, and indexed chunk metrics

No raw questions, API keys, or document text are included in metric labels.

## Primary metric names

```text
rag_requests_total
rag_request_latency_seconds
rag_ingest_total
rag_retrieval_errors_total
rag_retrieval_latency_seconds
rag_generation_latency_seconds
rag_qdrant_latency_seconds
rag_answer_abstentions_total
rag_citation_count
rag_citations_total
rag_query_top_k
rag_cross_tenant_eval_failures_total
rag_indexed_chunks
rag_evaluation_retrieval_hit_rate
rag_evaluation_citation_hit_rate
rag_evaluation_abstention_rate_negative
```

## Request logs

Each request emits a structured JSON log with:

```json
{
  "request_id": "generated-or-client-provided-id",
  "tenant_id": "tenant_a",
  "route": "/query",
  "retrieval_ms": 42.0,
  "generation_ms": 391.0,
  "citation_count": 2,
  "abstained": false,
  "status_code": 200
}
```

API keys, raw questions, and document text are intentionally excluded.

## Evidence capture

Recommended evidence files live under `docs/assets/`. Capture them from a running local stack or cluster:

```bash
curl -fsS http://127.0.0.1:8000/health > docs/assets/health-output.txt
curl -fsS http://127.0.0.1:8000/metrics > docs/assets/metrics-output.txt
kubectl get pods -A > docs/assets/kubectl-pods.txt
```

Screenshots of Prometheus targets and the Grafana dashboard can be added to the same directory after the observability stack is running.

## Kubernetes ServiceMonitor

For clusters with Prometheus Operator installed, use:

```bash
kubectl get crd servicemonitors.monitoring.coreos.com
make k8s-deploy-monitoring
```

The monitoring overlay renders the normal local Kubernetes stack plus `deploy/k8s/servicemonitor.yaml`. It is separate from the default overlay so clusters without Prometheus Operator can still deploy the service without CRD errors.
