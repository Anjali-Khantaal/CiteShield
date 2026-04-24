# Observability

## Local stack
Run:

```bash
docker compose -f observability/docker-compose.observability.yaml up -d
```

Prometheus: `http://127.0.0.1:9090`
Grafana: `http://127.0.0.1:3000`

## Metrics
- request count and HTTP latency
- retrieval/generation latency
- Qdrant operation latency
- ingest count
- retrieval error count
- abstention count
- citation count
- indexed chunk gauge
- evaluation summary gauges

Metrics avoid high-cardinality labels and never include API keys/questions/document text.
