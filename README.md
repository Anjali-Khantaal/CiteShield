# CiteShield

CiteShield is a multi-tenant Retrieval-Augmented Generation (RAG) backend that ingests tenant-specific documents, retrieves only tenant-scoped context, and returns grounded answers with citations.

The project is intentionally built in passes:

- [x] RAG core works
- [x] tenant isolation works
- [x] packaging and metrics work
- [x] Kubernetes and CI work

## What This Project Demonstrates

- FastAPI application structure with separated routes, services, auth, and metrics
- shared Qdrant vector store with logical tenant isolation through `tenant_id`
- server-side tenant resolution from `X-API-Key`
- answer generation constrained to retrieved context
- Prometheus-style metrics and health checks
- Docker Compose for local reproducibility
- Kubernetes manifests for application, data, config, secrets, and quotas
- GitHub Actions CI for tests and image build verification

## Current Scope

Version 1 is intentionally narrow:

- exactly 2 tenants: `tenant_a` and `tenant_b`
- text and markdown documents only
- answer + citations
- `top_k = 3`
- no OCR
- no reranker
- no hybrid search
- no RBAC
- no UI

## How It Works

At a high level:

1. a client sends `X-API-Key`
2. FastAPI resolves the key to `tenant_a` or `tenant_b`
3. `/ingest` chunks and embeds text, then stores vectors in Qdrant with payload metadata
4. `/query` embeds the question, searches Qdrant with a mandatory tenant filter, and generates a grounded answer
5. the response returns an answer plus citations tied to chunk IDs

The key design decision is simple:

- one FastAPI service
- one shared Qdrant collection
- every vector payload carries `tenant_id`
- every query applies a mandatory tenant filter
- the client never chooses its own tenant identity

## Architecture

Static SVG diagrams are used instead of live Mermaid blocks because SVG renders reliably across GitHub and IDE previewers.

### System Overview

![System overview](docs/diagrams/system-overview.svg)

### Ingestion Flow

![Ingestion flow](docs/diagrams/ingestion-flow.svg)

### Query Flow

![Query flow](docs/diagrams/query-flow.svg)

### Kubernetes Topology

![Kubernetes topology](docs/diagrams/kubernetes-topology.svg)

### Condensed Request Path

![Condensed request path](docs/diagrams/condensed-request-path.svg)

## Tech Stack

- API: FastAPI
- Vector store: Qdrant
- Embeddings: Sentence Transformers (`all-MiniLM-L6-v2`)
- Generator: extractive grounded answer generator
- Metrics: `prometheus-client`
- Local packaging: Docker Compose
- Orchestration: Kubernetes
- CI: GitHub Actions

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| App scaffold | Completed | FastAPI app with health, ingest, query, and metrics routes |
| Vector store bootstrap | Completed | Shared `documents` collection and `tenant_id` payload index |
| Ingestion | Completed | Script-based and API-based ingestion |
| Retrieval | Completed | Tenant-filtered semantic search |
| Generation | Completed | Grounded answers with citations |
| Auth and isolation | Completed | `X-API-Key` resolves tenant server-side |
| Metrics | Completed | Request, ingest, retrieval error, latency, and chunk metrics |
| Health | Completed | API, Qdrant, and generator readiness |
| Testing | Completed | 22 passing tests |
| Evaluation | Completed | QA evaluation script with CSV output |
| Packaging | Completed | Dockerfile and Docker Compose verified |
| Kubernetes | Completed | Namespaces, ConfigMap, Secret, Deployments, Services, ResourceQuota |
| CI | Completed | GitHub Actions tests and Docker build check |

## Quick Start

### 1. Create a Python environment

Conda:

```bash
conda env create -p ./.conda -f environment.yml
conda activate "$(pwd)/.conda"
```

`venv` + `pip`:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  --extra-index-url https://pypi.org/simple \
  torch==2.11.0
python -m pip install -r requirements.txt
```

### 2. Start the local stack

```bash
docker compose -f deploy/docker/compose.yaml up --build -d
```

This starts:

- the FastAPI API on `127.0.0.1:8000`
- Qdrant on the internal Docker network

Qdrant is intentionally not published to the host in Compose.

### 3. Initialize Qdrant

```bash
./.conda/bin/python scripts/init_qdrant.py
```

This creates:

- collection: `documents`
- vector size: `384`
- distance metric: `cosine`
- payload index: `tenant_id`

### 4. Load sample documents

```bash
./.conda/bin/python scripts/ingest_sample_docs.py
```

This ingests the sample markdown documents from:

- `data/tenant_a/`
- `data/tenant_b/`

### 5. Check service health

```bash
curl http://127.0.0.1:8000/health
```

Expected shape:

```json
{
  "status": "ok",
  "qdrant": "ok",
  "generator": "configured"
}
```

## Authentication And Tenant Isolation

Tenant identity is derived only from the API key.

- header: `X-API-Key`
- default local key for `tenant_a`: `tenant-a-dev-key`
- default local key for `tenant_b`: `tenant-b-dev-key`

The API ignores any client-supplied `tenant_id` fields. A caller cannot switch tenants by changing the request body.

Isolation rules:

- every stored chunk includes `tenant_id`
- every retrieval query filters on `tenant_id`
- auth decides the tenant, not the client
- cross-tenant leakage should fail by construction

## API Overview

### `GET /health`

Returns API, Qdrant, and generator readiness.

### `GET /metrics`

Returns Prometheus-compatible metrics.

Current application metrics:

- `rag_requests_total`
- `rag_ingest_total`
- `rag_retrieval_errors_total`
- `rag_request_latency_seconds`
- `rag_indexed_chunks`

### `POST /ingest`

Request:

```json
{
  "source": "remote_work_policy.md",
  "text": "Tenant A analysts must use the corporate VPN before opening internal dashboards."
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tenant-a-dev-key' \
  --data-raw '{"source":"remote_work_policy.md","text":"Tenant A analysts must use the corporate VPN before opening internal dashboards."}'
```

Response:

```json
{
  "tenant_id": "tenant_a",
  "doc_id": "remote_work_policy",
  "source": "remote_work_policy.md",
  "chunk_count": 1
}
```

### `POST /query`

Request:

```json
{
  "question": "How do analysts use VPN for internal dashboards?",
  "top_k": 3
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tenant-a-dev-key' \
  --data-raw '{"question":"How do analysts use VPN for internal dashboards?","top_k":3}'
```

Response:

```json
{
  "answer": "Tenant A analysts must use the corporate VPN before opening internal dashboards.",
  "citations": [
    {
      "source": "remote_work_policy.md",
      "chunk_id": 0
    }
  ]
}
```

## Local Development

### Run the API directly

If you want to run the app outside Compose:

```bash
uvicorn app.main:app --reload
```

You will also need a reachable Qdrant instance. For local Docker Qdrant only:

```bash
./scripts/run_qdrant.sh
./.conda/bin/python scripts/init_qdrant.py
```

### Run tests

```bash
./.conda/bin/python -m pytest -q
```

Current status: `22 passed`

### Run evaluation

```bash
./.conda/bin/python scripts/evaluate.py
```

The evaluator includes:

- 5 QA pairs for tenant A
- 5 QA pairs for tenant B
- 2 negative cross-tenant checks

It writes a CSV report to:

- `artifacts/evaluation_results.csv`

Tracked fields include:

- retrieval hit@k
- answer abstained or not
- citation present or not
- latency in milliseconds

## Configuration

The app reads settings from environment variables through `pydantic-settings`.

Important configuration values:

- `TENANT_A_API_KEY`
- `TENANT_B_API_KEY`
- `EMBEDDING_MODEL_NAME`
- `EMBEDDING_BATCH_SIZE`
- `CHUNK_SIZE_CHARS`
- `RETRIEVAL_TOP_K`
- `GENERATOR_BACKEND`
- `GENERATOR_MIN_SCORE_THRESHOLD`
- `GENERATOR_MIN_TERM_OVERLAP`
- `GENERATOR_MAX_SENTENCES`
- `FEATURE_STRICT_GROUNDING`
- `QDRANT_HOST`
- `QDRANT_HTTP_PORT`
- `QDRANT_GRPC_PORT`
- `QDRANT_COLLECTION_NAME`

## Docker Compose

Compose lives in `deploy/docker/compose.yaml`.

What it provides:

- `api` service
- `qdrant` service
- persistent Qdrant storage via `qdrant_storage`
- embedding model cache via `model_cache`

Useful commands:

```bash
docker compose -f deploy/docker/compose.yaml up --build -d
docker compose -f deploy/docker/compose.yaml ps
docker compose -f deploy/docker/compose.yaml down
```

## Kubernetes

Kubernetes manifests live in `deploy/k8s/`.

Current layout:

- `rag-app`: shared application namespace
- `vector-db`: shared Qdrant namespace
- `tenant-a`: tenant overlay namespace
- `tenant-b`: tenant overlay namespace

Manifest roles:

- `namespace.yaml`: namespaces
- `configmap.yaml`: non-secret application config
- `secret.yaml`: API keys and external LLM key placeholder
- `deployment.yaml`: API deployment, Qdrant deployment, and Qdrant PVC
- `service.yaml`: internal `ClusterIP` services
- `quota.yaml`: small `ResourceQuota` objects for the tenant namespaces

Apply order:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.yaml
kubectl apply -f deploy/k8s/deployment.yaml
kubectl apply -f deploy/k8s/service.yaml
kubectl apply -f deploy/k8s/quota.yaml
```

Operational notes:

- the API deployment expects an image named `citeshield-api:latest`
- for a remote cluster, push the image to a registry and update the image reference
- for kind or minikube, load the local image into the cluster first
- the API uses cross-namespace DNS to reach Qdrant:
  - `citeshield-qdrant.vector-db.svc.cluster.local`

## GitHub Actions

CI is defined in `.github/workflows/ci.yaml`.

It runs on:

- `push`
- `pull_request`

Jobs:

- `test`
  - checks out the repo
  - sets up Python `3.14`
  - installs CPU-only PyTorch and the pinned dependencies
  - runs `python -m pytest -q`
- `docker-build`
  - runs after tests pass
  - builds the API image from `deploy/docker/Dockerfile`
  - does not push to a registry

The current remote workflow has already run successfully on GitHub for this repo.

## Repository Layout

```text
CiteShield/
  app/
    auth.py
    config.py
    main.py
    metrics.py
    models.py
    routes/
      health.py
      ingest.py
      query.py
    services/
      chunking.py
      embeddings.py
      generator.py
      ingestion.py
      retriever.py
      vector_store.py
  data/
    tenant_a/
    tenant_b/
  deploy/
    docker/
    k8s/
  docs/
    diagrams/
  scripts/
    evaluate.py
    ingest_sample_docs.py
    init_qdrant.py
    run_qdrant.sh
  tests/
  README.md
```

## Definition Of Done For This Version

A reviewer should be able to:

1. start the app locally with Docker Compose
2. ingest documents for `tenant_a` and `tenant_b`
3. query as tenant A and receive only tenant A citations
4. query as tenant B and receive only tenant B citations
5. call `GET /health`
6. call `GET /metrics`
7. run tests in CI
8. inspect Kubernetes manifests covering config, secrets, namespaces, and quotas

## Known Constraints

- the current generator is extractive, not an external LLM integration
- the project is intentionally backend-only
- tenant isolation is logical, not physical, at the vector-store layer
- Kubernetes manifests are present, but this README does not assume a live cluster is already running

