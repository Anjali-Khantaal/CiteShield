# Manual configuration

Do not commit real keys/tokens/passwords. Use `.env` locally and Kubernetes secrets in-cluster.

| Name | Required | Purpose | Where to set |
|---|---|---|---|
| GEMINI_API_KEY | Optional (required only for `GENERATOR_BACKEND=gemini`) | Gemini generation auth | `.env`, k8s secret |
| GEMINI_MODEL_NAME | Optional | Gemini model selection | `.env`, configmap |
| GENERATOR_BACKEND | Required | `extractive`, `gemini`, or `openai_compatible` | `.env`, configmap |
| OPENAI_COMPATIBLE_BASE_URL | Optional | OpenAI-compatible serving endpoint | `.env`, configmap |
| OPENAI_COMPATIBLE_API_KEY | Optional | OpenAI-compatible auth | `.env`, k8s secret |
| OPENAI_COMPATIBLE_MODEL | Optional | Model name for compatible backend | `.env`, configmap |
| MLFLOW_TRACKING_URI | Optional | Future MLflow sink | `.env` |
| GRAFANA_ADMIN_USER | Optional | Grafana local admin username | `.env` |
| GRAFANA_ADMIN_PASSWORD | Optional | Grafana local admin password | `.env` |
| QDRANT_API_KEY | Optional | Remote Qdrant auth | `.env`, k8s secret |

Kubernetes secret creation: copy `deploy/k8s/base/secret.template.yaml` into an untracked file and apply it.
