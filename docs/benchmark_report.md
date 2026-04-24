# Benchmark report template

## Scenario
- Generator backend: `extractive`
- Embedding backend: `hash` (offline deterministic) or `sentence_transformers`
- Endpoints: `/health`, `/query`, `/ingest`
- Tool: Locust (`load_tests/locustfile.py`)

## Environment assumptions
- Local Docker Compose
- Prototype deployment profile

## Results
- p50 latency: _fill_
- p95 latency: _fill_
- error rate: _fill_
- requests/sec: _fill_

## Limitations
- Synthetic local load only.
- Not representative of production multi-node cluster behavior.
