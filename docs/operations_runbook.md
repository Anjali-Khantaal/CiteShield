# Operations runbook

## Local operations (prototype)
- Setup: `cp .env.example .env && make setup`
- Start: `make up`
- Smoke test: `python scripts/smoke_test.py`
- Offline eval: `make eval` (uses `EMBEDDING_BACKEND=hash`)
- Local synthetic benchmark: `make benchmark`
- Stop: `make down`

## Kubernetes checks
- Build image: `make build`
- Load image into kind: `make kind-load`
- Deploy local overlay: `make k8s-deploy`
- Deploy local overlay with Prometheus Operator ServiceMonitor: `make k8s-deploy-monitoring`
- Smoke test service path (`/health`, `/metrics`, `/ingest`, `/query`) via port-forward: `make k8s-smoke`

## Incident hints
- High `rag_retrieval_errors_total`: verify API↔Qdrant connectivity and DNS resolution.
- High latency: inspect embedding backend (`sentence_transformers` vs `hash`), CPU limits, and HPA behavior.
- Nonzero `rag_cross_tenant_eval_failures_total`: inspect tenant filters and rerun `make test` plus `make eval`.
- If HPA does not scale, confirm `metrics-server` is installed and healthy.

## Security hygiene
- Never log or commit real API keys.
- Never commit `.env` with real values.
- Create production Kubernetes secrets out-of-band.
