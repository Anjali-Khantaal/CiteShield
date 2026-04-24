# CERN-style platform alignment

- **ML service operation**: RAG API with health/metrics/smoke workflows.
- **Kubernetes/containerisation**: Kustomize base+overlays, HPA, NetworkPolicy, Docker image build.
- **Multi-tenant access**: server-side API key to tenant mapping + isolation tests.
- **RAG/LLM design**: retrieval + grounded citation answer path with abstention behavior.
- **Observability**: Prometheus/Grafana assets plus RAG-specific metrics.
- **Lifecycle management**: evaluation summaries and JSONL lifecycle run tracking.
- **CI/CD**: test + Docker build + Kubernetes kustomize validation.
- **Security limitations**: static keys and no mTLS/service mesh by default.
- **Future hardening**: OIDC authn/z, secret manager, policy-as-code, SLO-driven autoscaling.
