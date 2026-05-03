# Agent mode

CiteShield includes a minimal, deterministic RAG agent endpoint:

```text
POST /agent/query
```

This is intentionally not an autonomous planner. It runs a fixed tenant-scoped tool sequence:

1. `list_tenant_documents`
2. `retrieve_documents`
3. `explain_retrieval_diagnostics`

## Request

```json
{
  "question": "How do I access dashboards over VPN?",
  "top_k": 3,
  "include_diagnostics": true
}
```

Authentication uses the same `X-API-Key` tenant keys as `/query`.

## Response

```json
{
  "tenant_id": "tenant_a",
  "answer": "...",
  "citations": [{"source": "security.md", "chunk_id": 0}],
  "tools_used": [
    {"tool": "list_tenant_documents", "summary": "..."},
    {"tool": "retrieve_documents", "summary": "..."},
    {"tool": "explain_retrieval_diagnostics", "summary": "..."}
  ],
  "diagnostics": {
    "top_k": 3,
    "retrieved_count": 1,
    "retrieved_sources": ["security.md"],
    "max_score": 0.82,
    "min_score": 0.82,
    "abstained": false
  }
}
```

## Security properties

- Tenant identity is resolved from `X-API-Key`, not from request body fields.
- Tool calls use the authenticated tenant ID only.
- Document inventory is filtered to the authenticated tenant.
- Retrieval uses the same Qdrant tenant filter as `/query`.
- Superuser keys cannot use `/agent/query`; the endpoint requires a tenant key.

## Lifecycle and observability

Agent queries emit the same lifecycle and Prometheus signals as normal queries, labelled under `/agent/query`.
