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
- indexed chunk gauge
- evaluation summary gauges

No raw questions, API keys, or document text are included in metric labels.
