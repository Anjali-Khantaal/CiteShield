# Local quickstart

This path is designed for deterministic local validation without private keys or paid APIs.

## Setup
```bash
cp .env.example .env
make setup
```

Set these values in `.env` for offline-safe operation:

```env
EMBEDDING_BACKEND=hash
GENERATOR_BACKEND=extractive
```

When using Docker Compose with the Qdrant service, leave `QDRANT_LOCAL_PATH` blank in `.env`. If `QDRANT_LOCAL_PATH` is set, the API uses embedded local Qdrant storage and ignores `QDRANT_HOST`.

## Run
```bash
make up
python scripts/smoke_test.py
make eval
make benchmark
make down
```

## Direct API and frontend path

Use this path when Docker is unavailable or when you want a fast screenshot/demo loop.

Terminal 1:

```bash
EMBEDDING_BACKEND=hash \
GENERATOR_BACKEND=extractive \
QDRANT_LOCAL_PATH=artifacts/qdrant_local_demo \
LIFECYCLE_TRACKING_PATH=artifacts/lifecycle_runs.jsonl \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`, select a tenant key, check status, ingest or query content, and use the superuser key to review the document inventory.

## Query examples

```bash
curl -sS -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tenant-a-dev-key' \
  -d '{"question":"What is the VPN rule?","top_k":3}'

curl -sS -X POST http://127.0.0.1:8000/agent/query \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tenant-a-dev-key' \
  -d '{"question":"How quickly must a Launchpad access incident be reported?","top_k":3,"include_diagnostics":true}'
```

## Logs and traces

- Direct API logs print in the `uvicorn` terminal as structured JSON request logs.
- Docker API logs are available with `docker compose -f deploy/docker/compose.yaml logs -f api`.
- Prometheus-format metrics are available at `http://127.0.0.1:8000/metrics`.
- Query lifecycle traces are written to `artifacts/lifecycle_runs.jsonl` unless `LIFECYCLE_TRACKING_PATH` overrides it.
- Optional MLflow emission requires `pip install -r requirements-mlflow.txt` and `MLFLOW_TRACKING_URI`; JSONL tracing still works without MLflow.

## Expected signals
- `python scripts/smoke_test.py` prints `Smoke test passed`.
- `make eval` writes `artifacts/evaluation_results.csv` and `artifacts/evaluation_summary.json`.
- `make benchmark` writes `artifacts/benchmark_summary.json`.
- `/health` returns API, Qdrant, and generator status.
- `/metrics` exposes HTTP, RAG latency, citation, abstention, Qdrant, and evaluation metrics.

## Common failures
- If `/health` is degraded, check that Qdrant is running and `QDRANT_HOST` points to `qdrant` inside Docker Compose or `127.0.0.1` for direct local runs.
- If Docker Compose starts both API and Qdrant but the Qdrant service looks unused, check whether `QDRANT_LOCAL_PATH` is set. A non-empty local path switches the API to embedded Qdrant mode.
- If the generator is not configured, use `GENERATOR_BACKEND=extractive` or provide the required provider key for Gemini/OpenAI-compatible backends.
- If setup fails on a restricted network, use an existing virtual environment with the versions pinned in `requirements.txt`.
