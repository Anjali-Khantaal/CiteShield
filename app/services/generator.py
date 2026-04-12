from dataclasses import dataclass
import re
from typing import Protocol, Sequence

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


def get_answer_generator(settings: Settings | None = None) -> AnswerGenerator:
    settings = settings or get_settings()
    if settings.generator_backend != "extractive":
        raise ValueError(f"Unsupported generator backend: {settings.generator_backend}")

    return ExtractiveAnswerGenerator(
        min_score_threshold=settings.generator_min_score_threshold,
        min_term_overlap=(
            settings.generator_min_term_overlap if settings.feature_strict_grounding else 0
        ),
        max_sentences=settings.generator_max_sentences,
    )


def generate_answer(
    question: str,
    retrieved_chunks: Sequence[RetrievalMatch],
    generator: AnswerGenerator | None = None,
) -> AnswerWithCitations:
    generator = generator or get_answer_generator()
    return generator.generate_answer(question, retrieved_chunks)


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
        answer="I do not have enough reliable context in the retrieved documents to answer that confidently.",
        citations=[],
    )
