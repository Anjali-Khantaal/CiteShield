from dataclasses import dataclass
import logging
import re
from typing import Any, Callable, Protocol, Sequence

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.services.retriever import RetrievalMatch

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "with",
}

_ABSTAIN_ANSWER = (
    "I do not have enough reliable context in the retrieved documents to answer that confidently."
)
_LOGGER = logging.getLogger(__name__)
_GEMINI_SYSTEM_INSTRUCTION = """
You are a grounded answer generator for a retrieval-augmented system.

Rules:
- Use only the provided retrieved context.
- Do not use outside knowledge.
- If the context is insufficient, abstain.
- Return JSON only.
- "used_chunk_indices" must only contain integer indices that exist in the provided context.
- If you abstain, return the standard abstention answer exactly and an empty used_chunk_indices array.
""".strip()


@dataclass(frozen=True)
class Citation:
    source: str
    chunk_id: int


@dataclass(frozen=True)
class AnswerWithCitations:
    answer: str
    citations: list[Citation]


class AnswerGenerator(Protocol):
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: Sequence[RetrievalMatch],
    ) -> AnswerWithCitations: ...


class GeminiStructuredAnswer(BaseModel):
    answer: str = Field(default="")
    abstained: bool = False
    used_chunk_indices: list[int] = Field(default_factory=list)


class GeminiGenerateContentCallable(Protocol):
    def __call__(
        self,
        *,
        model: str,
        contents: object,
        config: object | None = None,
    ) -> object: ...


class ExtractiveAnswerGenerator:
    def __init__(
        self,
        min_score_threshold: float = 0.15,
        min_term_overlap: int = 2,
        max_sentences: int = 2,
    ) -> None:
        self.min_score_threshold = min_score_threshold
        self.min_term_overlap = min_term_overlap
        self.max_sentences = max_sentences

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: Sequence[RetrievalMatch],
    ) -> AnswerWithCitations:
        if not retrieved_chunks:
            return _abstain()

        best_match = max(retrieved_chunks, key=lambda item: item.score)
        candidates = _build_sentence_candidates(question=question, retrieved_chunks=retrieved_chunks)
        max_overlap = max((int(item["overlap"]) for item in candidates), default=0)

        if max_overlap < self.min_term_overlap:
            return _abstain()

        candidates = [
            item for item in candidates if int(item["overlap"]) >= self.min_term_overlap
        ]

        if not candidates:
            fallback_text = _first_content_sentence(best_match.text)
            if not fallback_text:
                return _abstain()

            return AnswerWithCitations(
                answer=fallback_text,
                citations=[Citation(source=best_match.source, chunk_id=best_match.chunk_id)],
            )

        selected = candidates[: self.max_sentences]
        answer = " ".join(item["sentence"] for item in selected).strip()
        citations = _build_citations(selected)

        if not answer:
            return _abstain()

        return AnswerWithCitations(answer=answer, citations=citations)


class GeminiAnswerGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        temperature: float = 0.0,
        max_output_tokens: int = 300,
        timeout_seconds: int = 30,
        generate_content: GeminiGenerateContentCallable | None = None,
        fallback_generator: AnswerGenerator | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.fallback_generator = fallback_generator
        self._generate_content = generate_content or _build_gemini_generate_content(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: Sequence[RetrievalMatch],
    ) -> AnswerWithCitations:
        if not retrieved_chunks:
            return _abstain()

        try:
            response = self._generate_content(
                model=self.model_name,
                contents=_build_gemini_prompt(question=question, retrieved_chunks=retrieved_chunks),
                config=_build_gemini_generation_config(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                ),
            )
        except Exception as exc:
            if self.fallback_generator is not None:
                _LOGGER.warning(
                    "Gemini generation failed, falling back to extractive answer generation: %s",
                    exc,
                )
                return self.fallback_generator.generate_answer(question, retrieved_chunks)
            raise RuntimeError("Gemini generation request failed.") from exc

        structured = _coerce_gemini_response(response)
        return _validate_grounded_answer(structured, retrieved_chunks)


def get_answer_generator(settings: Settings | None = None) -> AnswerGenerator:
    settings = settings or get_settings()
    backend = settings.generator_backend.strip().lower()

    if backend == "extractive":
        return ExtractiveAnswerGenerator(
            min_score_threshold=settings.generator_min_score_threshold,
            min_term_overlap=(
                settings.generator_min_term_overlap if settings.feature_strict_grounding else 0
            ),
            max_sentences=settings.generator_max_sentences,
        )

    if backend == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when generator_backend=gemini.")

        fallback_generator = ExtractiveAnswerGenerator(
            min_score_threshold=settings.generator_min_score_threshold,
            min_term_overlap=(
                settings.generator_min_term_overlap if settings.feature_strict_grounding else 0
            ),
            max_sentences=settings.generator_max_sentences,
        )

        return GeminiAnswerGenerator(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model_name,
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_max_output_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
            fallback_generator=fallback_generator,
        )

    raise ValueError(f"Unsupported generator backend: {settings.generator_backend}")


def generate_answer(
    question: str,
    retrieved_chunks: Sequence[RetrievalMatch],
    generator: AnswerGenerator | None = None,
) -> AnswerWithCitations:
    generator = generator or get_answer_generator()
    return generator.generate_answer(question, retrieved_chunks)


def _build_gemini_generate_content(
    *,
    api_key: str,
    timeout_seconds: int,
) -> GeminiGenerateContentCallable:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - dependency failure path
        raise ValueError(
            "google-genai is not installed. Install it before using generator_backend=gemini."
        ) from exc

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
    )

    def generate_content(
        *,
        model: str,
        contents: object,
        config: object | None = None,
    ) -> object:
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    return generate_content


def _build_gemini_generation_config(
    *,
    temperature: float,
    max_output_tokens: int,
) -> object:
    from google.genai import types

    return types.GenerateContentConfig(
        systemInstruction=_GEMINI_SYSTEM_INSTRUCTION,
        temperature=temperature,
        maxOutputTokens=max_output_tokens,
        responseMimeType="application/json",
        responseSchema=GeminiStructuredAnswer,
    )


def _build_gemini_prompt(
    *,
    question: str,
    retrieved_chunks: Sequence[RetrievalMatch],
) -> str:
    chunk_blocks: list[str] = []

    for index, chunk in enumerate(retrieved_chunks):
        chunk_blocks.append(
            "\n".join(
                [
                    f"Retrieved index: {index}",
                    f"Source: {chunk.source}",
                    f"Chunk ID: {chunk.chunk_id}",
                    f"Line range: {chunk.line_range or 'unknown'}",
                    f"Text: {chunk.text}",
                ]
            )
        )

    return "\n\n".join(
        [
            f"Question:\n{question}",
            "Retrieved context:",
            "\n\n".join(chunk_blocks),
            (
                'Return JSON with keys "answer", "abstained", and "used_chunk_indices". '
                "If the context is insufficient, abstain."
            ),
        ]
    )


def _coerce_gemini_response(response: object) -> GeminiStructuredAnswer:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, GeminiStructuredAnswer):
            return parsed
        return GeminiStructuredAnswer.model_validate(parsed)

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return GeminiStructuredAnswer.model_validate_json(text)

    raise ValueError("Gemini response did not contain structured JSON output.")


def _validate_grounded_answer(
    structured: GeminiStructuredAnswer,
    retrieved_chunks: Sequence[RetrievalMatch],
) -> AnswerWithCitations:
    if structured.abstained:
        return _abstain()

    answer = structured.answer.strip()
    if not answer:
        return _abstain()

    citations: list[Citation] = []
    seen: set[tuple[str, int]] = set()

    for index in structured.used_chunk_indices:
        if index < 0 or index >= len(retrieved_chunks):
            continue

        match = retrieved_chunks[index]
        key = (match.source, match.chunk_id)
        if key in seen:
            continue

        seen.add(key)
        citations.append(Citation(source=match.source, chunk_id=match.chunk_id))

    if not citations:
        return _abstain()

    return AnswerWithCitations(answer=answer, citations=citations)


def _build_sentence_candidates(
    *,
    question: str,
    retrieved_chunks: Sequence[RetrievalMatch],
) -> list[dict[str, object]]:
    question_terms = _significant_terms(question)
    candidates: list[dict[str, object]] = []

    for position, chunk in enumerate(retrieved_chunks):
        for sentence in _sentences_from_markdown(chunk.text):
            sentence_terms = _significant_terms(sentence)
            overlap = len(question_terms & sentence_terms)
            score = chunk.score + overlap * 0.25 - position * 0.01
            candidates.append(
                {
                    "score": score,
                    "overlap": overlap,
                    "sentence": sentence,
                    "source": chunk.source,
                    "chunk_id": chunk.chunk_id,
                }
            )

    candidates.sort(
        key=lambda item: (
            float(item["score"]),
            int(item["overlap"]),
            -len(str(item["sentence"])),
        ),
        reverse=True,
    )
    return _dedupe_sentences(candidates)


def _dedupe_sentences(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []

    for candidate in candidates:
        sentence = str(candidate["sentence"])
        normalized = sentence.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)

    return deduped


def _build_citations(selected: list[dict[str, object]]) -> list[Citation]:
    seen: set[tuple[str, int]] = set()
    citations: list[Citation] = []

    for item in selected:
        citation = Citation(
            source=str(item["source"]),
            chunk_id=int(item["chunk_id"]),
        )
        key = (citation.source, citation.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation)

    return citations


def _sentences_from_markdown(text: str) -> list[str]:
    cleaned_lines = [line.lstrip("# ").strip() for line in text.splitlines() if line.strip()]
    normalized = " ".join(cleaned_lines)
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _first_content_sentence(text: str) -> str:
    sentences = _sentences_from_markdown(text)
    return sentences[0] if sentences else ""


def _significant_terms(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return {word for word in words if word not in _STOP_WORDS and len(word) > 2}


def _abstain() -> AnswerWithCitations:
    return AnswerWithCitations(
        answer=_ABSTAIN_ANSWER,
        citations=[],
    )
