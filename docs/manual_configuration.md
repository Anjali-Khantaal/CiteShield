# Manual configuration

Do not commit real keys/tokens/passwords. Use `.env` locally and Kubernetes secrets out-of-band.

| Name | Required | Purpose | Where to set |
|---|---|---|---|
| EMBEDDING_BACKEND | Optional | `sentence_transformers` (default) or `hash` (offline deterministic) | `.env`, k8s configmap |
| GENERATOR_BACKEND | Required | `extractive`, `gemini`, or `openai_compatible` | `.env`, k8s configmap |
| GENERATOR_ENABLE_FALLBACK | Optional | Set `false` to fail instead of falling back to extractive when an LLM backend errors | `.env`, k8s configmap |
| GEMINI_API_KEY | Optional (required when backend=`gemini`) | Gemini auth | `.env`, k8s secret |
| GEMINI_FALLBACK_MODEL_NAMES_RAW | Optional | Comma-separated Gemini model fallback list, for example `gemini-2.5-flash-lite` | `.env`, k8s configmap |
| OPENAI_COMPATIBLE_BASE_URL | Optional | OpenAI-compatible endpoint | `.env`, k8s configmap |
| OPENAI_COMPATIBLE_MODEL | Optional | OpenAI-compatible model name | `.env`, k8s configmap |
| OPENAI_COMPATIBLE_API_KEY | Optional | OpenAI-compatible auth | `.env`, k8s secret |
| QDRANT_LOCAL_PATH | Optional | Embedded local Qdrant path; leave blank for Docker/Kubernetes Qdrant service mode | `.env` |
| QDRANT_API_KEY | Optional | Remote Qdrant auth | `.env`, k8s secret |
| MLFLOW_TRACKING_URI | Optional | External MLflow lifecycle sink | `.env` |
| LIFECYCLE_TRACKING_PATH | Optional | JSONL lifecycle trace path | `.env` |
| GRAFANA_ADMIN_USER | Optional | Grafana username | `.env` |
| GRAFANA_ADMIN_PASSWORD | Optional | Grafana password | `.env` |

## Kubernetes production secret creation (out-of-band)
Example (do not commit command history with real values):

```bash
kubectl -n rag-app create secret generic citeshield-app-secrets \
  --from-literal=TENANT_A_API_KEY='<real>' \
  --from-literal=TENANT_B_API_KEY='<real>' \
  --from-literal=SUPERUSER_API_KEY='<real>' \
  --from-literal=GEMINI_API_KEY='<optional>' \
  --from-literal=OPENAI_COMPATIBLE_API_KEY='<optional>' \
  --from-literal=QDRANT_API_KEY='<optional>'
```

The committed `deploy/k8s/overlays/prod-template/secret.template.yaml` is documentation only and is not applied by default.
