# Model lifecycle tracking

CiteShield uses lightweight JSONL lifecycle tracking in `artifacts/lifecycle_runs.jsonl`.

Each evaluation run logs:
- embedding model
- generator backend/model
- retrieval `top_k`
- chunk size
- retrieval/citation hit metrics
- abstention rate
- average latency

Optional: set `MLFLOW_TRACKING_URI` for future MLflow integration.
