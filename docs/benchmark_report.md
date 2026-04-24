# Benchmark report template

## Scenario
- Generator backend: `extractive`
- Endpoints: `/health`, `/query`, `/ingest`
- Tool: Locust (`load_tests/locustfile.py`)

## Environment assumptions
- Local Docker Compose deployment
- CPU-only embedding model

## Results (sample template)
- p50 latency: _fill_
- p95 latency: _fill_
- error rate: _fill_
- requests/sec: _fill_

## Limitations
- Local-only synthetic workload.
- No external LLM-provider latency included when using `extractive` backend.
