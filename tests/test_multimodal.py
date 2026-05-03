import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.query import (
    get_query_client,
    get_query_embedder,
    get_query_generator,
    get_query_settings,
)
from app.services.generator import ExtractiveAnswerGenerator
from app.services.ingestion import ingest_documents
from app.services.multimodal import (
    MultimodalManifestItem,
    extract_audio_text,
    extract_image_text,
    extract_video_text,
    download_manifest_media,
    generate_sample_media,
    load_multimodal_manifest,
    process_multimodal_item,
    render_derived_markdown,
)


class KeywordEmbedder:
    embedding_size = 4

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "earthrise" in lowered else 0.0,
                    1.0 if "hello" in lowered else 0.0,
                    1.0 if "example" in lowered else 0.0,
                    1.0 if "vpn" in lowered else 0.0,
                ]
            )
        return vectors


def test_load_multimodal_manifest_validates_items(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    manifest = data_root / "multimodal_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "tenant_id": "tenant_a",
                        "source_url": "https://example.org/image.png",
                        "local_path": "data/tenant_a/media/images/sample.png",
                        "modality": "image",
                        "title": "Sample image",
                        "license": "Public domain",
                        "attribution": "Example",
                        "expected_terms": ["earthrise"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    items = load_multimodal_manifest(manifest, data_root=data_root)

    assert len(items) == 1
    assert items[0].tenant_id == "tenant_a"
    assert items[0].modality == "image"
    assert items[0].local_path == data_root / "tenant_a/media/images/sample.png"
    assert items[0].sample_text == ""
    assert items[0].expected_terms == ("earthrise",)


def test_generated_manifest_media_uses_local_generator(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "data/tenant_a/media/images/security.png"
    item = MultimodalManifestItem(
        tenant_id="tenant_a",
        source_url="generated://citeshield/security-poster",
        local_path=image_path,
        modality="image",
        title="Security Poster",
        license="Generated sample",
        attribution="CiteShield",
        sample_text="Never send API keys over chat.",
        expected_terms=("api keys",),
    )

    def fake_generate(sample: MultimodalManifestItem) -> None:
        sample.local_path.write_bytes(b"generated media")

    monkeypatch.setattr("app.services.multimodal.generate_sample_media", fake_generate)

    assert download_manifest_media([item]) == [image_path]
    assert image_path.read_bytes() == b"generated media"


def test_image_ocr_path_with_generated_fixture(monkeypatch, tmp_path: Path) -> None:
    image_module = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "ocr.png"
    image = image_module.new("RGB", (120, 40), color="white")
    image.save(image_path)

    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(image_to_string=lambda image: "Earthrise OCR text"),
    )
    monkeypatch.setattr("app.services.multimodal.shutil.which", lambda binary: "/usr/bin/tesseract")

    assert extract_image_text(image_path) == "Earthrise OCR text"


def test_audio_asr_path_with_mocked_whisper(monkeypatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "hello.wav"
    audio_path.write_bytes(b"fake audio")

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def transcribe(self, path, beam_size):
            return [SimpleNamespace(start=0.0, end=1.5, text=" hello from audio ")], {}

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeWhisperModel),
    )

    assert extract_audio_text(audio_path) == "00:00-00:01: hello from audio"


def test_video_processing_with_mocked_ffmpeg_and_extractors(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "example.ogv"
    video_path.write_bytes(b"fake video")

    def fake_run(command, check, stdout, stderr):
        output = Path(command[-1])
        if "%03d" in output.name:
            (output.parent / "frame-001.jpg").write_bytes(b"fake frame")
        else:
            output.write_bytes(b"fake audio")
        return None

    monkeypatch.setattr("app.services.multimodal.shutil.which", lambda binary: "/usr/bin/ffmpeg")
    monkeypatch.setattr("app.services.multimodal.subprocess.run", fake_run)
    monkeypatch.setattr("app.services.multimodal.extract_image_text", lambda path: "Example frame text")
    monkeypatch.setattr("app.services.multimodal.extract_audio_text", lambda path: "00:00-00:02: Example audio text")

    text = extract_video_text(video_path)

    assert "Example audio text" in text
    assert "Example frame text" in text


def test_generated_video_uses_multiple_slides(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "support.mp4"
    generated_slides: list[str] = []
    concat_files: list[str] = []

    def fake_generate_image(item: MultimodalManifestItem) -> None:
        generated_slides.append(item.sample_text)
        item.local_path.write_bytes(b"slide")

    def fake_generate_audio(item: MultimodalManifestItem) -> None:
        item.local_path.write_bytes(b"audio")

    def fake_run(command, check, stdout, stderr):
        concat_path = Path(command[command.index("-i") + 1])
        concat_files.append(concat_path.read_text(encoding="utf-8"))
        Path(command[-1]).write_bytes(b"video")
        return None

    monkeypatch.setattr("app.services.multimodal.shutil.which", lambda binary: "/usr/bin/ffmpeg")
    monkeypatch.setattr("app.services.multimodal._generate_policy_image", fake_generate_image)
    monkeypatch.setattr("app.services.multimodal._generate_policy_audio", fake_generate_audio)
    monkeypatch.setattr("app.services.multimodal.subprocess.run", fake_run)

    generate_sample_media(
        MultimodalManifestItem(
            tenant_id="tenant_b",
            source_url="generated://citeshield/support-video",
            local_path=video_path,
            modality="video",
            title="Support Video",
            license="Generated",
            attribution="CiteShield",
            sample_text=(
                "Severity one incidents need acknowledgement within fifteen minutes. "
                "Updates continue every thirty minutes. "
                "Data export escalations route to platform support."
            ),
        )
    )

    assert video_path.read_bytes() == b"video"
    assert len(generated_slides) == 3
    assert concat_files[0].count("duration 7") == 3


def test_process_multimodal_item_writes_derived_markdown_and_metadata(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    media_path = data_root / "tenant_a/media/images/earthrise.png"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"fake image")

    item = MultimodalManifestItem(
        tenant_id="tenant_a",
        source_url="https://example.org/earthrise.png",
        local_path=media_path,
        modality="image",
        title="Earthrise Image",
        license="Public domain",
        attribution="NASA",
        expected_terms=("earthrise",),
    )
    monkeypatch.setattr("app.services.multimodal.extract_image_text", lambda path: "Earthrise above the moon")

    result = process_multimodal_item(item, data_root=data_root)

    derived = data_root / "tenant_a" / result.derived_path
    assert derived.exists()
    assert "Earthrise above the moon" in derived.read_text(encoding="utf-8")
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["modality"] == "image"
    assert metadata["media_path"] == "media/images/earthrise.png"
    assert metadata["attribution"] == "NASA"


def test_multimodal_sidecar_metadata_is_indexed_and_returned_in_citations(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    derived_dir = data_root / "tenant_a/derived/multimodal"
    derived_dir.mkdir(parents=True)
    (derived_dir / "earthrise.md").write_text(
        "# Earthrise\n\nEarthrise appears above the moon in this NASA image.",
        encoding="utf-8",
    )
    (derived_dir / "earthrise.metadata.json").write_text(
        json.dumps(
            {
                "modality": "image",
                "media_path": "media/images/earthrise.png",
                "source_url": "https://example.org/earthrise.png",
                "license": "Public domain",
                "attribution": "NASA",
            }
        ),
        encoding="utf-8",
    )

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
            "lifecycle_tracking_path": str(tmp_path / "lifecycle.jsonl"),
        }
    )
    embedder = KeywordEmbedder()
    ingest_documents(data_root=data_root, client=client, embedder=embedder, settings=settings)

    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: client
    app.dependency_overrides[get_query_generator] = lambda: ExtractiveAnswerGenerator()

    try:
        response = TestClient(app).post(
            "/query",
            json={"question": "What does the Earthrise image show?"},
            headers={"X-API-Key": get_settings().tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["source"] == "derived/multimodal/earthrise.md"
    assert citation["modality"] == "image"
    assert citation["media_path"] == "media/images/earthrise.png"
    assert citation["source_url"] == "https://example.org/earthrise.png"


def test_render_derived_markdown_contains_required_sections(tmp_path: Path) -> None:
    item = MultimodalManifestItem(
        tenant_id="tenant_a",
        source_url="https://example.org/audio.ogg",
        local_path=tmp_path / "audio.ogg",
        modality="audio",
        title="Hello Audio",
        license="Public domain",
        attribution="Example",
        expected_terms=("hello",),
    )

    rendered = render_derived_markdown(
        item=item,
        relative_media_path="media/audio/audio.ogg",
        extracted_text="00:00-00:01: hello",
    )

    assert "# Hello Audio" in rendered
    assert "Modality: audio" in rendered
    assert "## Extracted text" in rendered
    assert "## Segments" in rendered
