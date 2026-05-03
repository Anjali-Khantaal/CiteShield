# Model lifecycle tracking

CiteShield records RAG lifecycle evidence for both online queries and evaluation runs.

## Storage backends

The default backend is JSONL:

```text
artifacts/lifecycle_runs.jsonl
```

Set `LIFECYCLE_TRACKING_PATH` to write traces elsewhere.

Optional MLflow emission is enabled when both conditions are true:
- `MLFLOW_TRACKING_URI` is set.
- The Python environment has `mlflow` installed.

If MLflow is unavailable, the JSONL record still includes `mlflow_status: unavailable` and the request/evaluation continues.

## Query trace fields

Each `/query` call records:
- request ID
- tenant ID
- route
- embedding backend and model name
- generator backend and model name
- retrieval `top_k`
- retrieval latency
- generation latency
- retrieved source filenames
- citation count
- abstained true/false

Raw questions, API keys, and document text are not logged.

## Evaluation run fields

`scripts/evaluate.py` records:
- embedding backend and model
- generator backend and model
- retrieval `top_k`
- chunk size
- retrieval hit rate
- citation hit rate
- negative-case abstention rate
- average latency
- cross-tenant evaluation failure count
- evaluation CSV and summary JSON artifact paths

## Local commands

```bash
EMBEDDING_BACKEND=hash GENERATOR_BACKEND=extractive make eval
tail -n 1 artifacts/lifecycle_runs.jsonl
```

MLflow example:

```bash
python -m pip install -r requirements-mlflow.txt
MLFLOW_TRACKING_URI=file:./mlruns \
EMBEDDING_BACKEND=hash \
GENERATOR_BACKEND=extractive \
make eval
```
