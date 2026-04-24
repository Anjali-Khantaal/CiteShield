# CiteShield

CiteShield is a multi-tenant RAG service designed to showcase **ML platform operations**: reproducible deployment, tenant-aware retrieval, observability, evaluation/lifecycle tracking, and Kubernetes assets.

## Why this project matters
This repo is intentionally focused on platform engineering concerns (operations, monitoring, evaluation, security posture) rather than chatbot feature breadth.

## Quick start
```bash
cp .env.example .env
make setup
make up
python scripts/smoke_test.py
```

Run evaluation (no paid API required):
```bash
make eval
```

Stop services:
```bash
make down
```

## Make targets
- `make setup` install Python dependencies
- `make test` run test suite
- `make up` / `make down` start/stop local stack
- `make eval` run evaluation with extractive backend
- `make build` build API image
- `make k8s-deploy` deploy local k8s overlay
- `make k8s-smoke` smoke check k8s deployment
- `make k8s-clean` remove k8s resources

## Ops and platform docs
- [Architecture](docs/architecture.md)
- [Kubernetes quickstart](docs/kubernetes_quickstart.md)
- [Operations runbook](docs/operations_runbook.md)
- [Observability](docs/observability.md)
- [Model lifecycle](docs/model_lifecycle.md)
- [Threat model](docs/threat_model.md)
- [Benchmark report](docs/benchmark_report.md)
- [CERN alignment](docs/cern_alignment.md)
- [Manual configuration](docs/manual_configuration.md)
- [LLM serving backends](docs/llm_serving_backends.md)
