# Operations runbook

## Local ops
- Start stack: `make up`
- Health check: `python scripts/smoke_test.py`
- Stop stack: `make down`

## API checks
- `/health` for readiness.
- `/metrics` for Prometheus metrics.

## Incident hints
- High `rag_retrieval_errors_total`: check Qdrant reachability.
- High latency histograms: inspect embedding/model backend and container CPU throttling.
