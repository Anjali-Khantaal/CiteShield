# CiteShield

CiteShield is a multi-tenant RAG prototype focused on **ML platform operations**: reproducible deployment, tenant isolation, observability, evaluation, and Kubernetes workflows.

## Why this project matters
This repo emphasizes platform engineering (ops, deployment, monitoring, lifecycle evidence) rather than chatbot feature breadth.

## Safe local default path (no paid API required)
```bash
cp .env.example .env
make setup
make up
python scripts/smoke_test.py
```

Defaults:
- `GENERATOR_BACKEND=extractive` (no external LLM API required)
- `EMBEDDING_BACKEND=sentence_transformers` for realistic local runs

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

Production secrets must be created out-of-band (not from committed placeholder manifests).

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

## Ops and platform docs
- [Kubernetes quickstart](docs/kubernetes_quickstart.md)
- [Operations runbook](docs/operations_runbook.md)
- [Observability](docs/observability.md)
- [Manual configuration](docs/manual_configuration.md)
- [Limitations](docs/limitations.md)
- [CERN alignment](docs/cern_alignment.md)
- [Benchmark report](docs/benchmark_report.md)
