from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from textwrap import wrap
from typing import Literal

from app.services.ingestion import TENANT_IDS

Modality = Literal["image", "audio", "video"]
SUPPORTED_MODALITIES = {"image", "audio", "video"}


class MultimodalDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class MultimodalManifestItem:
    tenant_id: str
    source_url: str
    local_path: Path
    modality: Modality
    title: str
    license: str
    attribution: str
    sample_text: str = ""
    expected_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultimodalProcessingResult:
    tenant_id: str
    modality: Modality
    title: str
    media_path: Path
    derived_path: Path
    metadata_path: Path
    extracted_text: str


def load_multimodal_manifest(manifest_path: Path, *, data_root: Path) -> list[MultimodalManifestItem]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_items = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError("Multimodal manifest must be a list or an object with an 'items' list.")

    return [_parse_manifest_item(item, data_root=data_root) for item in raw_items]


def download_manifest_media(items: list[MultimodalManifestItem], *, timeout_seconds: int = 60) -> list[Path]:
    downloaded: list[Path] = []
    for item in items:
        item.local_path.parent.mkdir(parents=True, exist_ok=True)
        if item.source_url.startswith("generated://"):
            generate_sample_media(item)
            downloaded.append(item.local_path)
            continue

        if item.local_path.exists() and item.local_path.stat().st_size > 0:
            downloaded.append(item.local_path)
            continue

        request = urllib.request.Request(
            item.source_url,
            headers={"User-Agent": "CiteShield multimodal prototype"},
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            item.local_path.write_bytes(response.read())
        downloaded.append(item.local_path)
    return downloaded


def generate_sample_media(item: MultimodalManifestItem) -> None:
    if not item.sample_text.strip():
        raise ValueError(f"Generated multimodal sample requires sample_text: {item.title}")

    item.local_path.parent.mkdir(parents=True, exist_ok=True)
    if item.modality == "image":
        _generate_policy_image(item)
        return
    if item.modality == "audio":
        _generate_policy_audio(item)
        return
    if item.modality == "video":
        _generate_policy_video(item)
        return

    raise ValueError(f"Unsupported generated sample modality: {item.modality}")


def process_multimodal_manifest(
    items: list[MultimodalManifestItem],
    *,
    data_root: Path,
) -> list[MultimodalProcessingResult]:
    return [process_multimodal_item(item, data_root=data_root) for item in items]


def process_multimodal_item(
    item: MultimodalManifestItem,
    *,
    data_root: Path,
) -> MultimodalProcessingResult:
    if not item.local_path.exists():
        raise FileNotFoundError(
            f"Media file does not exist: {item.local_path}. Run scripts/download_multimodal_samples.py first."
        )

    if item.modality == "image":
        extracted_text = extract_image_text(item.local_path)
    elif item.modality == "audio":
        extracted_text = extract_audio_text(item.local_path)
    elif item.modality == "video":
        extracted_text = extract_video_text(item.local_path)
    else:
        raise ValueError(f"Unsupported modality: {item.modality}")

    extracted_text = extracted_text.strip() or (
        "No OCR/ASR text was extracted from this asset. "
        "The record is indexed with its title, source, license, and attribution metadata."
    )

    tenant_dir = data_root / item.tenant_id
    derived_dir = tenant_dir / "derived" / "multimodal"
    derived_dir.mkdir(parents=True, exist_ok=True)
    doc_id = _derive_doc_id(item.title or item.local_path.stem)
    derived_path = derived_dir / f"{doc_id}.md"
    metadata_path = derived_path.with_suffix(".metadata.json")

    relative_media_path = item.local_path.relative_to(tenant_dir).as_posix()
    relative_derived_path = derived_path.relative_to(tenant_dir).as_posix()
    derived_path.write_text(
        render_derived_markdown(
            item=item,
            relative_media_path=relative_media_path,
            extracted_text=extracted_text,
        ),
        encoding="utf-8",
    )
    metadata_path.write_text(
        json.dumps(
            {
                "modality": item.modality,
                "media_path": relative_media_path,
                "source_url": item.source_url,
                "license": item.license,
                "attribution": item.attribution,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return MultimodalProcessingResult(
        tenant_id=item.tenant_id,
        modality=item.modality,
        title=item.title,
        media_path=Path(relative_media_path),
        derived_path=Path(relative_derived_path),
        metadata_path=metadata_path,
        extracted_text=extracted_text,
    )


def render_derived_markdown(
    *,
    item: MultimodalManifestItem,
    relative_media_path: str,
    extracted_text: str,
) -> str:
    return "\n".join(
        [
            f"# {item.title}",
            "",
            f"Modality: {item.modality}",
            f"Source file: {relative_media_path}",
            f"Original URL: {item.source_url}",
            f"License: {item.license}",
            f"Attribution: {item.attribution}",
            "",
            "## Extracted text",
            "",
            extracted_text.strip(),
            "",
            "## Segments",
            "",
            "- full asset: extracted text above",
            "",
        ]
    )


def extract_image_text(path: Path) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise MultimodalDependencyError(
            "Image OCR requires Pillow and pytesseract. Install requirements-multimodal.txt and system tesseract."
        ) from exc

    if shutil.which("tesseract") is None:
        raise MultimodalDependencyError("Image OCR requires the 'tesseract' system binary.")

    with Image.open(path) as image:
        return str(pytesseract.image_to_string(image))


def extract_audio_text(path: Path) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise MultimodalDependencyError(
            "Audio ASR requires faster-whisper. Install requirements-multimodal.txt."
        ) from exc

    model = _get_whisper_model()
    segments, _info = model.transcribe(str(path), beam_size=1)
    return "\n".join(
        f"{_format_seconds(segment.start)}-{_format_seconds(segment.end)}: {segment.text.strip()}"
        for segment in segments
        if segment.text.strip()
    )


def extract_video_text(path: Path) -> str:
    if shutil.which("ffmpeg") is None:
        raise MultimodalDependencyError("Video processing requires the 'ffmpeg' system binary.")

    with tempfile.TemporaryDirectory(prefix="citeshield-video-") as tmp:
        tmpdir = Path(tmp)
        frame_pattern = tmpdir / "frame-%03d.jpg"
        audio_path = tmpdir / "audio.wav"

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-vf",
                "fps=1/5",
                str(frame_pattern),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(audio_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        frame_text = []
        for frame in sorted(tmpdir.glob("frame-*.jpg")):
            text = extract_image_text(frame).strip()
            if text:
                frame_text.append(f"frame {frame.stem.removeprefix('frame-')}: {text}")

        transcript = extract_audio_text(audio_path) if audio_path.exists() else ""
        sections = []
        if transcript.strip():
            sections.append(transcript.strip())
        if frame_text:
            sections.append("\n".join(frame_text))
        return "\n\n".join(sections)


@lru_cache(maxsize=1)
def _get_whisper_model():
    from faster_whisper import WhisperModel

    return WhisperModel("tiny", device="cpu", compute_type="int8", use_auth_token=False)


def _generate_policy_image(item: MultimodalManifestItem) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise MultimodalDependencyError(
            "Generated image samples require Pillow. Install requirements-multimodal.txt."
        ) from exc

    width, height = 1400, 900
    image = Image.new("RGB", (width, height), color="#f7f7f3")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(size=56)
    body_font = _load_font(size=42)
    small_font = _load_font(size=28)

    draw.rectangle((0, 0, width, 120), fill="#172554")
    draw.text((60, 34), item.title, fill="#ffffff", font=title_font)
    draw.text((60, 160), f"Tenant: {item.tenant_id}", fill="#334155", font=small_font)

    y = 220
    for line in wrap(item.sample_text, width=48):
        draw.text((60, y), line, fill="#111827", font=body_font)
        y += 58

    draw.rectangle((60, height - 120, width - 60, height - 50), outline="#94a3b8", width=3)
    draw.text((85, height - 100), "CiteShield multimodal OCR sample", fill="#334155", font=small_font)
    image.save(item.local_path)


def _generate_policy_audio(item: MultimodalManifestItem) -> None:
    if shutil.which("ffmpeg") is None:
        raise MultimodalDependencyError("Generated audio samples require the 'ffmpeg' system binary.")

    with tempfile.TemporaryDirectory(prefix="citeshield-audio-") as tmp:
        tmpdir = Path(tmp)
        spoken_path = tmpdir / "spoken.aiff"
        if shutil.which("say"):
            subprocess.run(
                ["say", "-o", str(spoken_path), item.sample_text],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif shutil.which("espeak"):
            subprocess.run(
                ["espeak", "-w", str(spoken_path), item.sample_text],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            raise MultimodalDependencyError(
                "Generated audio samples require macOS 'say' or Linux 'espeak'."
            )

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(spoken_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(item.local_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _generate_policy_video(item: MultimodalManifestItem) -> None:
    if shutil.which("ffmpeg") is None:
        raise MultimodalDependencyError("Generated video samples require the 'ffmpeg' system binary.")

    with tempfile.TemporaryDirectory(prefix="citeshield-video-sample-") as tmp:
        tmpdir = Path(tmp)
        slide_paths = []
        concat_path = tmpdir / "slides.txt"
        audio_path = tmpdir / "voice.wav"
        for index, slide_text in enumerate(_split_video_slides(item.sample_text), start=1):
            slide_path = tmpdir / f"slide-{index:02d}.png"
            slide_item = MultimodalManifestItem(
                tenant_id=item.tenant_id,
                source_url=item.source_url,
                local_path=slide_path,
                modality="image",
                title=f"{item.title} ({index})",
                license=item.license,
                attribution=item.attribution,
                sample_text=slide_text,
                expected_terms=item.expected_terms,
            )
            _generate_policy_image(slide_item)
            slide_paths.append(slide_path)

        audio_item = MultimodalManifestItem(
            tenant_id=item.tenant_id,
            source_url=item.source_url,
            local_path=audio_path,
            modality="audio",
            title=item.title,
            license=item.license,
            attribution=item.attribution,
            sample_text=item.sample_text,
            expected_terms=item.expected_terms,
        )
        _generate_policy_audio(audio_item)
        _write_ffmpeg_concat_file(concat_path, slide_paths=slide_paths, duration_seconds=7)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-i",
                str(audio_path),
                "-vf",
                "fps=1",
                "-shortest",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(item.local_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _split_video_slides(text: str) -> list[str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    if len(sentences) >= 2:
        return sentences

    words = text.split()
    midpoint = max(1, len(words) // 2)
    return [" ".join(words[:midpoint]), " ".join(words[midpoint:]).strip() or text]


def _write_ffmpeg_concat_file(path: Path, *, slide_paths: list[Path], duration_seconds: int) -> None:
    lines: list[str] = []
    for slide_path in slide_paths:
        lines.append(f"file '{slide_path.as_posix()}'")
        lines.append(f"duration {duration_seconds}")
    lines.append(f"file '{slide_paths[-1].as_posix()}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_font(*, size: int):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _parse_manifest_item(raw: object, *, data_root: Path) -> MultimodalManifestItem:
    if not isinstance(raw, dict):
        raise ValueError("Each multimodal manifest item must be an object.")

    tenant_id = _required_string(raw, "tenant_id")
    if tenant_id not in TENANT_IDS:
        raise ValueError(f"Unsupported tenant_id in multimodal manifest: {tenant_id}")

    modality = _required_string(raw, "modality").lower()
    if modality not in SUPPORTED_MODALITIES:
        raise ValueError(f"Unsupported modality in multimodal manifest: {modality}")

    local_path = (data_root.parent / _required_string(raw, "local_path")).resolve()
    data_root_resolved = data_root.resolve()
    if not local_path.is_relative_to(data_root_resolved):
        raise ValueError(f"local_path must stay under {data_root}: {local_path}")

    return MultimodalManifestItem(
        tenant_id=tenant_id,
        source_url=_required_string(raw, "source_url"),
        local_path=local_path,
        modality=modality,  # type: ignore[arg-type]
        title=_required_string(raw, "title"),
        license=_required_string(raw, "license"),
        attribution=_required_string(raw, "attribution"),
        sample_text=str(raw.get("sample_text", "")).strip(),
        expected_terms=tuple(str(item) for item in raw.get("expected_terms", []) if str(item).strip()),
    )


def _required_string(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"Missing required multimodal manifest field: {key}")
    return str(value).strip()


def _derive_doc_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "_", value.strip().lower()).strip("_")
    return normalized or "multimodal_asset"


def _format_seconds(value: float) -> str:
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
