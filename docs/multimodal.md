# Multimodal RAG

CiteShield supports a text-first multimodal prototype. Raw image, audio, and video files stay in tenant-scoped media folders. Local OCR/ASR/video processing extracts searchable text into derived Markdown files, and those derived files are indexed into the existing tenant-isolated Qdrant collection.

## Data sources

The default manifest uses generated CiteShield policy media so the samples match the existing tenant documents:
- Tenant A security-access poster: MFA, managed devices, API keys, vault rotation.
- Tenant A remote-work audio briefing: VPN, customer data, screen lock, encryption.
- Tenant B support-escalation video: severity-one acknowledgement, thirty-minute updates, platform support routing.

If you replace the generated samples with external files, use public or freely licensed media only. Recommended sources:
- NASA Image and Video Library: public NASA media and metadata.
- LibriVox: public-domain audio.
- Wikimedia Commons: public-domain and freely licensed images/audio/video.
- Internet Archive: public/open media collections.

The sample manifest is:

```text
data/multimodal_manifest.json
```

## Data layout

```text
data/
  tenant_a/
    media/
      images/
      audio/
      video/
    derived/
      multimodal/
  tenant_b/
    media/
      images/
      audio/
      video/
    derived/
      multimodal/
```

Binary media is never stored in Qdrant. Qdrant stores vectors, extracted text, tenant metadata, source paths, and optional media metadata.

## Dependencies

Install Python dependencies:

```bash
./.conda/bin/python -m pip install -r requirements-multimodal.txt
```

Install system tools:

```bash
brew install tesseract ffmpeg
```

Linux:

```bash
sudo apt-get install -y tesseract-ocr ffmpeg
python -m pip install -r requirements-multimodal.txt
```

## Processing flow

1. `scripts/download_multimodal_samples.py` creates generated CiteShield media or downloads public media from `data/multimodal_manifest.json`.
2. `scripts/process_multimodal.py` extracts text:
   - images: `Pillow` + `pytesseract`
   - audio: `faster-whisper` tiny model
   - video: `ffmpeg` frame sampling + OCR and audio ASR
3. Extracted text is written to `data/<tenant>/derived/multimodal/*.md`.
4. A sidecar `*.metadata.json` stores modality, media path, source URL, license, and attribution.
5. Existing ingestion reads derived Markdown and sidecar metadata, then indexes chunks in Qdrant.

If OCR/ASR runs successfully but the asset has no detectable speech or visible text, the processor still writes a derived record with the title, source, license, attribution, and an explicit empty-extraction note. Missing OCR/ASR dependencies fail clearly; empty media extraction does not break text-only CiteShield.

## Commands

```bash
make multimodal-download PYTHON=./.conda/bin/python
make multimodal-process PYTHON=./.conda/bin/python
make multimodal-ingest PYTHON=./.conda/bin/python
```

End-to-end demo:

```bash
make multimodal-demo PYTHON=./.conda/bin/python
```

LLM-backed demo, using the configured `GENERATOR_BACKEND` such as `gemini`:

```bash
GENERATOR_BACKEND=gemini GENERATOR_ENABLE_FALLBACK=false GEMINI_API_KEY=<your-key> make multimodal-demo-llm PYTHON=./.conda/bin/python
```

## Citation shape

Multimodal citations extend the existing text citation shape:

```json
{
  "source": "derived/multimodal/tenant_a_security_access_poster.md",
  "chunk_id": 0,
  "modality": "image",
  "media_path": "media/images/security_access_poster.png",
  "source_url": "generated://citeshield/tenant-a-security-poster",
  "time_range": null,
  "frame_time": null
}
```

Text-only citations remain backward-compatible and omit null media fields in API responses.

## Limitations

- OCR and ASR quality depends on media quality and local tools.
- Generated audio/video samples require either macOS `say` or Linux `espeak` for local text-to-speech.
- `faster-whisper` may download a tiny model on first use.
- Video processing samples frames at a low rate for prototype speed.
- This is text-first multimodal RAG, not native image/audio/video embedding search.
- Replacement public visual samples may not contain visible text, so demo retrieval can come from title/source metadata rather than OCR content.
- Keep sample media small; for larger assets, commit only the manifest and derived text.
