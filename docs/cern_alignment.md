# CiteShield Alignment with ML Platform Engineering Requirements

## ML service operation

CiteShield runs as a FastAPI RAG service with health checks, smoke tests, evaluation, benchmark commands, structured logs, and lifecycle traces. The repository favors repeatable operation over one-off demo behavior.

## Kubernetes and containerisation

The project includes Docker Compose, a Dockerfile, Kustomize base and overlays, pinned Qdrant image tags, a versioned API image tag, readiness/liveness probes, resource requests/limits, PVC-backed Qdrant storage, HPA, NetworkPolicy, and a Prometheus Operator ServiceMonitor overlay.

## Multi-tenant access

Tenant identity is resolved server-side from `X-API-Key`. Query and agent retrieval both use authenticated tenant IDs and Qdrant tenant metadata filters. Tests cover malicious request bodies that try to override tenant identity.

## Observability

CiteShield exposes Prometheus metrics for HTTP traffic, retrieval latency, generation latency, Qdrant latency, abstentions, citations, query `top_k`, indexed chunks, evaluation hit rates, and cross-tenant evaluation failures. Grafana and Prometheus assets are included under `observability/`.

## Model lifecycle management

The service records per-query and evaluation lifecycle traces to JSONL. If `MLFLOW_TRACKING_URI` is configured and MLflow is installed, the same evaluation/query metadata can be emitted to MLflow.

## RAG evaluation

`scripts/evaluate.py` runs tenant-specific and cross-tenant cases, reporting retrieval hit rate, citation hit rate, negative-case abstention rate, average latency, and cross-tenant failure count.

## Model-serving abstraction

Generation is abstracted behind `GENERATOR_BACKEND` with `extractive`, `gemini`, and `openai_compatible` implementations. The OpenAI-compatible path is suitable for vLLM or internal chat-completions gateways.

## Multimodal ML pipeline

The multimodal path demonstrates media ingestion, local OCR/ASR preprocessing, derived artifact generation, metadata preservation, and tenant-isolated indexing without storing binary media in Qdrant.

## Agent capability

`POST /agent/query` implements a deterministic tenant-scoped RAG agent with fixed tools: `list_tenant_documents`, `retrieve_documents`, and `explain_retrieval_diagnostics`.

## Load testing

`make benchmark` runs repeatable local synthetic benchmarks for 1, 5, 10, and 25 simulated users. `load_tests/locustfile.py` supports external HTTP load tests against a running service.

## Security limitations

CiteShield remains a prototype. Static API keys are for local/demo use only. Production should use OIDC/CERN SSO, audited service identities, RBAC, secret-manager integration, stronger network controls, backups, and SLO-driven operations.

## Future production hardening

Recommended next steps are production-grade identity, managed secrets, real cluster deployment evidence, backup/restore validation, ingress/TLS, SLO dashboards, alert rules, and production load testing against Qdrant server mode and the chosen model-serving backend.
