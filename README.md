# CiteShield

CiteShield is a multi-tenant RAG prototype focused on **ML platform operations**: reproducible deployment, tenant isolation, observability, evaluation, and Kubernetes workflows.

## Why this project matters
This repo emphasizes platform engineering (ops, deployment, monitoring, lifecycle evidence) rather than chatbot feature breadth.

## What this demonstrates

- Multi-tenant RAG service design with tenant-scoped retrieval and citation-grounded answers.
- ML platform operations: health checks, smoke tests, metrics, lifecycle/evaluation tracking, and benchmarking.
- Kubernetes deployment using Kustomize overlays, resource requests/limits, PVC-backed Qdrant storage, HPA, and NetworkPolicy.
- Safe local operation without paid APIs using the extractive generator and offline hash embeddings.
- Optional LLM-backed generation using Gemini or an OpenAI-compatible chat completions backend.
- Production-awareness through explicit limitations, out-of-band secrets, and documented hardening gaps.

## Prerequisites

For the local Docker path:
- Python 3.12+
- Docker / Docker Compose
- Make

For Kubernetes validation:
- kubectl
- kind or minikube
- metrics-server if you want to observe HPA behavior

## Safe local default path
```bash
cp .env.example .env
make setup
make up
python scripts/smoke_test.py
```

For the fastest offline-safe local path, set these in `.env` before `make up`:

```env
EMBEDDING_BACKEND=hash
GENERATOR_BACKEND=extractive
```

This mode needs no external LLM API key. It is useful for smoke tests, restricted-network demos, and deterministic local evaluation.

## Gemini-backed generation

To run with Gemini, set:

```env
EMBEDDING_BACKEND=hash
GENERATOR_BACKEND=gemini
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL_NAME=gemini-2.5-flash
```

Then restart the stack:

```bash
make down
make up
python scripts/smoke_test.py
```

The smoke test exercises ingestion, retrieval, generation, and citations. Do not commit `.env`; it is intentionally gitignored because it can contain real API keys.

## OpenAI-compatible generation

For a local gateway, vLLM endpoint, or other OpenAI-compatible server, set:

```env
GENERATOR_BACKEND=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8001/v1
OPENAI_COMPATIBLE_MODEL=<model-name>
OPENAI_COMPATIBLE_API_KEY=<optional-if-your-server-requires-it>
```

Offline/restricted-network evaluation:
```bash
make eval
```
(`make eval` forces `EMBEDDING_BACKEND=hash` for deterministic offline embeddings.)

## Kubernetes assets
Use only:
- `deploy/k8s/base/`
- `deploy/k8s/overlays/local/`
- `deploy/k8s/overlays/prod-template/`

Notes:
- Local overlay uses `EMBEDDING_BACKEND=hash` to keep smoke tests offline-safe.
- Base/prod templates can use `sentence_transformers`.
- NetworkPolicy explicitly allows DNS egress for service discovery.
- HPA behavior depends on cluster metrics pipeline (typically `metrics-server`).
- Production secrets must be created out-of-band (not from committed placeholder manifests).

## Security note
Never commit a real `.env`, API key, password, or token.

## Make targets
- `make setup`
- `make test`
- `make up` / `make down`
- `make eval`
- `make build`
- `make k8s-deploy`
- `make k8s-smoke`
- `make k8s-clean`

## Validation checklist

The project is designed so the following checks can be run without private keys or paid APIs:

```bash
python -m pytest -q
make eval
python scripts/run_benchmark.py
docker compose -f deploy/docker/compose.yaml config
kubectl kustomize deploy/k8s/overlays/local
kubectl kustomize deploy/k8s/overlays/prod-template
```

## Ops and platform docs
- [Kubernetes quickstart](docs/kubernetes_quickstart.md)
- [Operations runbook](docs/operations_runbook.md)
- [Observability](docs/observability.md)
- [Manual configuration](docs/manual_configuration.md)
- [Limitations](docs/limitations.md)
- [CERN alignment](docs/cern_alignment.md)
- [Benchmark report](docs/benchmark_report.md)
