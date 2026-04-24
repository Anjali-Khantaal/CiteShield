# Architecture

CiteShield is a multi-tenant RAG platform service with a FastAPI API, Qdrant vector index, and operator UI.

## Why this project matters
It demonstrates practical ML platform operations: deployment, tenant isolation, metrics, lifecycle tracking, and repeatable benchmarking.

## Components
- API service (`app/`): ingest, query, admin, metrics.
- Vector store (Qdrant): shared cluster with tenant metadata filters.
- Evaluation + lifecycle tracking (`scripts/evaluate.py`, `app/tracing.py`).
- Observability stack (`observability/`): Prometheus + Grafana.
- Kubernetes manifests (`deploy/k8s/base` + overlays).
