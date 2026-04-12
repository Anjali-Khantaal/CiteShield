from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_id: int
    text: str
    line_range: str


@dataclass(frozen=True)
class _Paragraph:
    text: str
    start_line: int
    end_line: int


def chunk_text(text: str, max_chars: int) -> list[TextChunk]:
    paragraphs = _extract_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[TextChunk] = []
    current: list[_Paragraph] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return

        chunk_text_value = "\n\n".join(item.text for item in current).strip()
        chunks.append(
            TextChunk(
                chunk_id=len(chunks),
                text=chunk_text_value,
                line_range=f"{current[0].start_line}-{current[-1].end_line}",
            )
        )
        current = []
        current_chars = 0

    for paragraph in paragraphs:
        if len(paragraph.text) > max_chars:
            flush()
            for split_text in _split_long_paragraph(paragraph.text, max_chars):
                chunks.append(
                    TextChunk(
                        chunk_id=len(chunks),
                        text=split_text,
                        line_range=f"{paragraph.start_line}-{paragraph.end_line}",
                    )
                )
            continue

        additional_chars = len(paragraph.text) + (2 if current else 0)
        if current and current_chars + additional_chars > max_chars:
            flush()

        current.append(paragraph)
        current_chars += additional_chars

    flush()
    return chunks


def _extract_paragraphs(text: str) -> list[_Paragraph]:
    paragraphs: list[_Paragraph] = []
    lines = text.splitlines()
    buffer: list[str] = []
    start_line: int | None = None

    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if stripped:
            if start_line is None:
                start_line = line_number
            buffer.append(stripped)
            continue

        if buffer and start_line is not None:
            paragraphs.append(
                _Paragraph(
                    text="\n".join(buffer),
                    start_line=start_line,
                    end_line=line_number - 1,
                )
            )
            buffer = []
            start_line = None

    if buffer and start_line is not None:
        paragraphs.append(
            _Paragraph(
                text="\n".join(buffer),
                start_line=start_line,
                end_line=len(lines),
            )
        )

    return paragraphs


def _split_long_paragraph(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    parts: list[str] = []
    current_words: list[str] = []
    current_chars = 0

    for word in words:
        word_chars = len(word) + (1 if current_words else 0)
        if current_words and current_chars + word_chars > max_chars:
            parts.append(" ".join(current_words))
            current_words = [word]
            current_chars = len(word)
            continue

        current_words.append(word)
        current_chars += word_chars

    if current_words:
        parts.append(" ".join(current_words))

    return parts
