# CiteShield

CiteShield is a multi-tenant RAG application for tenant-scoped document search and cited answers.

It has:
- a FastAPI backend
- Qdrant for vector search
- a React operator console
- API-key-based tenant isolation
- Docker, Kubernetes, and CI assets for packaging and deployment

## What It Does

Each request carries an `X-API-Key`. The backend resolves that key to a tenant server-side, retrieves only that tenant's documents, and returns an answer with citations.

Current tenants:
- `tenant_a`
- `tenant_b`

Current document types:
- Markdown
- Plain text

## Core Flow

1. Ingest a document for a tenant.
2. Split the document into chunks.
3. Embed the chunks and store them in Qdrant with tenant metadata.
4. Query with a tenant key.
5. Retrieve only that tenant's chunks.
6. Generate an answer from retrieved context and return citations.

## Architecture

- Backend: FastAPI
- Frontend: React + Vite + TypeScript
- Vector store: Qdrant
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Generator: Gemini-backed answer generator with backend citation validation
- Auth: `X-API-Key`

The vector store is shared, but every stored chunk carries `tenant_id`, and every query applies a tenant filter. The client does not choose its tenant through the request body.

## Quick Start

### 1. Configure the backend

Copy the example env file:

```bash
cp .env.example .env
```

Set a valid Gemini key in `.env`:

```env
GEMINI_API_KEY=your-real-key
GENERATOR_BACKEND=gemini
GEMINI_MODEL_NAME=gemini-2.5-flash
```

### 2. Start the local stack

```bash
docker compose -f deploy/docker/compose.yaml up --build -d
```

This starts:
- API on `http://127.0.0.1:8000`
- Qdrant on `http://127.0.0.1:6333`

### 3. Initialize Qdrant and load sample data

```bash
./.conda/bin/python scripts/init_qdrant.py
./.conda/bin/python scripts/ingest_sample_docs.py
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Default Keys

- Tenant A: `tenant-a-dev-key`
- Tenant B: `tenant-b-dev-key`
- Superuser: `superuser-dev-key`

## How Access Works

- `tenant-a-dev-key`
  - can ingest for `tenant_a`
  - can query only `tenant_a`
- `tenant-b-dev-key`
  - can ingest for `tenant_b`
  - can query only `tenant_b`
- `superuser-dev-key`
  - can inspect all indexed documents
  - can delete indexed documents
  - can ingest for either tenant by selecting the target tenant in the UI
  - does not use the query tab for tenant-scoped retrieval

## Main Endpoints

- `GET /health`
  - API, Qdrant, and generator readiness
- `GET /metrics`
  - Prometheus metrics
- `GET /whoami`
  - resolves the current API key to a tenant or superuser role
- `POST /ingest`
  - ingests one document
- `POST /query`
  - returns an answer with citations
- `GET /admin/documents`
  - superuser document inventory
- `DELETE /admin/documents/{tenant_id}/{doc_id}`
  - superuser document deletion

## Example Requests

Health:

```bash
curl http://127.0.0.1:8000/health
```

Ingest:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tenant-a-dev-key' \
  --data-raw '{"source":"remote_work_policy.md","text":"Tenant A analysts must use the corporate VPN before opening internal dashboards."}'
```

Query:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tenant-a-dev-key' \
  --data-raw '{"question":"What is the VPN rule for internal dashboards?","top_k":3}'
```

Superuser inventory:

```bash
curl -H 'X-API-Key: superuser-dev-key' http://127.0.0.1:8000/admin/documents
```

## Frontend

The UI is a lightweight operator console. It supports:
- environment setup and health checks
- tenant-scoped query
- document ingest
- superuser inventory and deletion

The UI talks to the same backend routes listed above. It does not hold a separate tenant model.

## Development

Run tests:

```bash
./.conda/bin/python -m pytest -q
```

Run the evaluation script:

```bash
./.conda/bin/python scripts/evaluate.py
```

Stop the local stack:

```bash
docker compose -f deploy/docker/compose.yaml down
```

Reset Qdrant storage:

```bash
docker compose -f deploy/docker/compose.yaml down -v
```

## Deployment Assets

This repo includes:
- `deploy/docker/` for local container packaging
- `deploy/k8s/` for Kubernetes manifests
- `.github/workflows/ci.yaml` for CI

They are part of the repo, but you do not need them to understand or run the project locally.

## Repository Layout

```text
CiteShield/
  app/          FastAPI app
  data/         sample tenant documents
  deploy/       Docker and Kubernetes assets
  docs/         diagrams
  frontend/     React UI
  scripts/      setup, ingest, and evaluation scripts
  tests/        backend tests
```

## Notes

- Gemini mode requires a valid `GEMINI_API_KEY`.
- Citations are validated by the backend against retrieved chunks.
- Tenant isolation is enforced in application logic and retrieval filters.
