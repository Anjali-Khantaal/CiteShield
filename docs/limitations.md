# Limitations

- CiteShield is a prototype, not a production security boundary.
- Authentication is static API-key based for local demos and tests; production should use OIDC/CERN SSO or another audited identity provider.
- There is no service mesh or mTLS by default.
- Local overlays use hash embeddings for reliability; this favors reproducibility over semantic quality.
- The OpenAI-compatible backend is an integration abstraction. Running scalable GPU inference with vLLM or another server is documented but not bundled into the default local stack.
- Multimodal retrieval is text-first over OCR/ASR/video-derived text, not native image/audio/video embedding search.
- OCR requires `tesseract`; video processing requires `ffmpeg`; ASR requires `faster-whisper` and may download a tiny model on first use.
- Generated audio/video samples require local text-to-speech support through macOS `say` or Linux `espeak`.
- If image or video samples contain no OCR-visible text or useful speech, CiteShield indexes title/source metadata plus an explicit empty-extraction note instead of pretending to understand visual content.
- The `/agent/query` endpoint is deliberately deterministic and small. It demonstrates tenant-scoped tool use, not a general autonomous agent framework.
- Local benchmarks use FastAPI TestClient and local Qdrant path storage, so they are useful regression signals but not production capacity numbers.
- HPA requires metrics pipeline support, usually `metrics-server`, and may not scale in minimal clusters.
- Prometheus Operator `ServiceMonitor` support requires the monitoring CRDs to exist in the target cluster.
- Production operations still require backup/restore, secret manager integration, policy enforcement, SLO-driven scaling, and incident response processes.
