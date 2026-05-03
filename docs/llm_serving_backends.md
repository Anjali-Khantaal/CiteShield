# LLM serving backends

CiteShield separates RAG application logic from the answer-generation backend.

## Supported backends

| Backend | Use case | External service required |
|---|---|---|
| `extractive` | Offline demos, smoke tests, deterministic evaluation | No |
| `gemini` | Hosted Gemini generation with grounded JSON response validation | Yes |
| `openai_compatible` | vLLM, internal gateways, or other OpenAI-compatible chat-completions endpoints | Yes |

## Extractive backend

```env
GENERATOR_BACKEND=extractive
EMBEDDING_BACKEND=hash
```

This is the default safe path for local tests. It produces answers from retrieved sentences and abstains when term overlap is weak.

## Gemini backend

```env
GENERATOR_BACKEND=gemini
GEMINI_API_KEY=<your-key>
GEMINI_MODEL_NAME=gemini-2.5-flash
```

The generator requests structured JSON and validates that cited chunk indices exist in the retrieved context.

## OpenAI-compatible backend

```env
GENERATOR_BACKEND=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8001/v1
OPENAI_COMPATIBLE_MODEL=mistral-7b-instruct
OPENAI_COMPATIBLE_API_KEY=<optional-if-required>
```

The backend calls:

```text
POST ${OPENAI_COMPATIBLE_BASE_URL}/chat/completions
```

with `response_format={"type":"json_object"}`. This makes it compatible with vLLM's OpenAI server mode and many internal OpenAI-compatible gateways.

Example vLLM shape:

```bash
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8001 \
  --model mistralai/Mistral-7B-Instruct-v0.3
```

Then:

```bash
GENERATOR_BACKEND=openai_compatible \
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:8001/v1 \
OPENAI_COMPATIBLE_MODEL=mistralai/Mistral-7B-Instruct-v0.3 \
make up
```

## Grounding controls

All generative backends must return:

```json
{
  "answer": "...",
  "abstained": false,
  "used_chunk_indices": [0]
}
```

CiteShield discards invalid citation indices and abstains if the model returns no valid citations.

## Fallback behavior

Gemini and OpenAI-compatible backends are configured with an extractive fallback. If the provider is unavailable, the system can still produce grounded extractive answers from retrieved chunks.
