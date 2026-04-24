# Operations runbook

## Local operations (prototype)
- Start: `make up`
- Smoke test: `python scripts/smoke_test.py`
- Offline eval: `make eval` (uses `EMBEDDING_BACKEND=hash`)
- Local synthetic benchmark: `python scripts/run_benchmark.py`
- Stop: `make down`

## Kubernetes checks
- Deploy local overlay: `make k8s-deploy`
- Smoke test service path (`/health`, `/metrics`, `/ingest`, `/query`) via port-forward: `make k8s-smoke`

## Incident hints
- High `rag_retrieval_errors_total`: verify API↔Qdrant connectivity and DNS resolution.
- High latency: inspect embedding backend (`sentence_transformers` vs `hash`), CPU limits, and HPA behavior.
- If HPA does not scale, confirm `metrics-server` is installed and healthy.

## Security hygiene
- Never log or commit real API keys.
- Never commit `.env` with real values.
- Create production Kubernetes secrets out-of-band.
