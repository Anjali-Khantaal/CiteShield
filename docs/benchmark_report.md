# Benchmark report

## Scenario

- Benchmark type: local synthetic concurrent API benchmark
- Generator backend: `extractive`
- Embedding backend: `hash`
- Storage: local Qdrant path storage, reset per scenario
- Tooling:
  - `scripts/run_benchmark.py` for repeatable 1/5/10/25 simulated-user runs
  - `load_tests/locustfile.py` for external HTTP load tests against a running service

The synthetic benchmark is intentionally offline-safe. It avoids paid LLM calls and uses deterministic hash embeddings so it can run in CI or restricted-network environments.

## Reproducible command

```bash
make benchmark
cat artifacts/benchmark_summary.json
```

Equivalent direct command:

```bash
EMBEDDING_BACKEND=hash \
GENERATOR_BACKEND=extractive \
python scripts/run_benchmark.py --users 1,5,10,25 --requests-per-user 20
```

## Reported metrics

Each user-count scenario reports:
- p50 query latency
- p95 query latency
- average query latency
- error rate
- requests/sec
- average retrieval latency from query lifecycle traces
- average generation latency from query lifecycle traces
- Qdrant availability from `/health`

The JSON output is written to:

```text
artifacts/benchmark_summary.json
```

## Latest local result

Generated with `python scripts/run_benchmark.py --users 1,5,10,25 --requests-per-user 20`.

| Users | Requests | p50 query ms | p95 query ms | Error rate | Requests/sec | Retrieval avg ms | Generation avg ms | Qdrant |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | 20 | 6.03 | 10.32 | 0.0% | 150.44 | 0.85 | 0.09 | available |
| 5 | 100 | 29.12 | 140.74 | 0.0% | 106.31 | 1.45 | 0.08 | available |
| 10 | 200 | 87.86 | 253.88 | 0.0% | 97.58 | 2.32 | 0.10 | available |
| 25 | 500 | 122.09 | 302.38 | 0.0% | 166.87 | 5.38 | 0.06 | available |

## Locust path

For a running API service:

```bash
CITESHIELD_BASE_URL=http://127.0.0.1:8000 \
python -m locust -f load_tests/locustfile.py \
  --headless -u 25 -r 5 --run-time 60s \
  --csv artifacts/locust_local --csv-full-history
```

## Limitations

- This is not production performance.
- Local TestClient results do not include real network hops, ingress controllers, autoscaling warm-up, or external LLM latency.
- For multi-process or distributed load tests, use Qdrant server mode rather than embedded local path storage.
