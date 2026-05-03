# Architecture

CiteShield is a multi-tenant RAG platform service with a FastAPI API, Qdrant vector index, and operator UI.

## Why this project matters
It demonstrates practical ML platform operations: deployment, tenant isolation, metrics, lifecycle tracking, and repeatable benchmarking.

## Components
- API service (`app/`): ingest, query, admin, metrics.
- Agent route (`POST /agent/query`): deterministic tenant-scoped tool workflow for retrieval, diagnostics, and grounded answering.
- Vector store (Qdrant): shared cluster with tenant metadata filters.
- Multimodal processing (`app/services/multimodal.py`): OCR, ASR, video frame sampling, derived Markdown, and media metadata sidecars.
- Evaluation + lifecycle tracking (`scripts/evaluate.py`, `app/tracing.py`).
- Observability stack (`observability/`): Prometheus + Grafana.
- Kubernetes manifests (`deploy/k8s/base` + overlays).

## Request paths

### Standard RAG query

1. Resolve tenant from `X-API-Key`.
2. Embed the question.
3. Retrieve chunks from Qdrant with a tenant metadata filter.
4. Generate a grounded answer using the configured backend.
5. Validate citations and record metrics/lifecycle traces.

### Agent query

1. Resolve tenant from `X-API-Key`.
2. Run `list_tenant_documents`.
3. Run `retrieve_documents`.
4. Run `explain_retrieval_diagnostics`.
5. Return the grounded answer, citations, tool trace, and diagnostics.

The agent path is fixed and deterministic; it does not allow free-form tool planning.

### Multimodal ingestion

1. Create generated CiteShield policy media or download public media listed in `data/multimodal_manifest.json`.
2. Extract searchable text with local OCR/ASR/video processing.
3. Write derived Markdown and metadata sidecars under each tenant.
4. Ingest derived Markdown through the existing text chunking and embedding path.
5. Return citations with optional media metadata.
