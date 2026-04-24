# CERN-style platform alignment

- **ML service operation**: RAG service with health/metrics/smoke workflows and reproducible `make` commands.
- **Kubernetes/containerisation**: Kustomize base/overlays, HPA, NetworkPolicy, pinned images, Docker build.
- **Multi-tenant access**: server-side API-key tenant mapping and tenant isolation tests.
- **RAG/LLM service design**: retrieval + grounded citations + abstention behavior.
- **Observability**: Prometheus/Grafana plus low-cardinality RAG metrics.
- **Lifecycle management**: evaluation outputs + JSONL lifecycle tracking.
- **CI/CD**: tests + docker build + kustomize rendering with no private secrets.
- **Security posture**: committed files contain placeholders only; production secrets must be created out-of-band.
- **Known gap**: project remains prototype and needs production hardening before real operations.
