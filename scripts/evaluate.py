import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings, get_settings
from app.tracing import LifecycleTracker
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.generator import AnswerGenerator, generate_answer, get_answer_generator
from app.services.ingestion import ingest_documents
from app.services.retriever import retrieve_chunks
from app.services.vector_store import get_qdrant_client

ABSTAIN_PREFIX = "I do not have enough reliable context"


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    tenant_id: str
    question: str
    expected_sources: tuple[str, ...]
    expect_abstain: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    tenant_id: str
    question: str
    expected_sources: tuple[str, ...]
    retrieved_sources: tuple[str, ...]
    citation_sources: tuple[str, ...]
    retrieval_hit_at_k: bool
    answer_abstained: bool
    citation_present: bool
    citation_hit: bool
    latency_ms: float
    answer: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval and grounded answering against built-in sample QA pairs.",
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Directory containing tenant sample documents.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/evaluation_results.csv",
        help="CSV path for evaluation output.",
    )
    parser.add_argument(
        "--local-path",
        help="Use Qdrant local mode at this path instead of the live HTTP server.",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Evaluate the existing index without re-ingesting the sample documents first.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        help="Override the configured retrieval top_k for evaluation.",
    )
    parser.add_argument(
        "--summary-json",
        default="artifacts/evaluation_summary.json",
        help="Optional JSON path for summary output.",
    )
    return parser.parse_args()


def build_default_cases() -> list[EvaluationCase]:
    return [
        EvaluationCase(
            case_id="tenant_a_remote_days",
            tenant_id="tenant_a",
            question="Which days may Tenant A employees work remotely?",
            expected_sources=("remote_work_policy.md",),
        ),
        EvaluationCase(
            case_id="tenant_a_screen_lock",
            tenant_id="tenant_a",
            question="After how many minutes should laptops lock their screens?",
            expected_sources=("remote_work_policy.md",),
        ),
        EvaluationCase(
            case_id="tenant_a_vpn_rule",
            tenant_id="tenant_a",
            question="What is the VPN rule for customer data work?",
            expected_sources=("remote_work_policy.md",),
        ),
        EvaluationCase(
            case_id="tenant_a_incident_window",
            tenant_id="tenant_a",
            question="How quickly must Tenant A security incidents be filed?",
            expected_sources=("security_guidelines.md",),
        ),
        EvaluationCase(
            case_id="tenant_a_production_access",
            tenant_id="tenant_a",
            question="What is required for approved production access?",
            expected_sources=("security_guidelines.md",),
        ),
        EvaluationCase(
            case_id="tenant_b_client_dinners",
            tenant_id="tenant_b",
            question="How much can Tenant B reimburse per attendee for client dinners?",
            expected_sources=("expense_policy.md",),
        ),
        EvaluationCase(
            case_id="tenant_b_travel_approval",
            tenant_id="tenant_b",
            question="How far in advance does international travel need finance approval?",
            expected_sources=("expense_policy.md",),
        ),
        EvaluationCase(
            case_id="tenant_b_report_deadline",
            tenant_id="tenant_b",
            question="When are expense reports due?",
            expected_sources=("expense_policy.md",),
        ),
        EvaluationCase(
            case_id="tenant_b_sev1_ack",
            tenant_id="tenant_b",
            question="How quickly must severity-one incidents be acknowledged?",
            expected_sources=("customer_support_handbook.md",),
        ),
        EvaluationCase(
            case_id="tenant_b_refund_approval",
            tenant_id="tenant_b",
            question="Who can approve refund requests for annual contracts?",
            expected_sources=("customer_support_handbook.md",),
        ),
        EvaluationCase(
            case_id="cross_tenant_a_to_b_refunds",
            tenant_id="tenant_a",
            question="Who can approve refund requests for annual contracts?",
            expected_sources=(),
            expect_abstain=True,
        ),
        EvaluationCase(
            case_id="cross_tenant_b_to_a_vpn",
            tenant_id="tenant_b",
            question="What is the VPN rule for customer data work?",
            expected_sources=(),
            expect_abstain=True,
        ),
    ]


def evaluate_case(
    *,
    case: EvaluationCase,
    client,
    settings: Settings,
    embedder: EmbeddingService,
    generator: AnswerGenerator,
) -> EvaluationResult:
    started = perf_counter()
    matches = retrieve_chunks(
        client=client,
        collection_name=settings.qdrant_collection_name,
        tenant_id=case.tenant_id,
        question=case.question,
        embedder=embedder,
        top_k=settings.retrieval_top_k,
    )
    answer = generate_answer(
        question=case.question,
        retrieved_chunks=matches,
        generator=generator,
    )
    latency_ms = (perf_counter() - started) * 1000

    retrieved_sources = tuple(match.source for match in matches)
    citation_sources = tuple(citation.source for citation in answer.citations)
    expected_source_set = set(case.expected_sources)
    retrieval_hit_at_k = bool(expected_source_set.intersection(retrieved_sources))
    citation_hit = bool(expected_source_set.intersection(citation_sources))
    answer_abstained = answer.answer.startswith(ABSTAIN_PREFIX)

    return EvaluationResult(
        case_id=case.case_id,
        tenant_id=case.tenant_id,
        question=case.question,
        expected_sources=case.expected_sources,
        retrieved_sources=retrieved_sources,
        citation_sources=citation_sources,
        retrieval_hit_at_k=retrieval_hit_at_k,
        answer_abstained=answer_abstained,
        citation_present=bool(answer.citations),
        citation_hit=citation_hit,
        latency_ms=round(latency_ms, 2),
        answer=answer.answer,
    )


def evaluate_cases(
    *,
    cases: list[EvaluationCase],
    client,
    settings: Settings,
    embedder: EmbeddingService,
    generator: AnswerGenerator,
) -> list[EvaluationResult]:
    return [
        evaluate_case(
            case=case,
            client=client,
            settings=settings,
            embedder=embedder,
            generator=generator,
        )
        for case in cases
    ]


def summarize_results(results: list[EvaluationResult], *, cases: list[EvaluationCase]) -> dict[str, float | int]:
    case_by_id = {case.case_id: case for case in cases}
    positive_results = [result for result in results if not case_by_id[result.case_id].expect_abstain]
    negative_results = [result for result in results if case_by_id[result.case_id].expect_abstain]

    return {
        "cases_total": len(results),
        "positive_cases": len(positive_results),
        "negative_cases": len(negative_results),
        "retrieval_hit_rate_overall": _ratio(sum(result.retrieval_hit_at_k for result in results), len(results)),
        "retrieval_hit_rate_positive": _ratio(
            sum(result.retrieval_hit_at_k for result in positive_results),
            len(positive_results),
        ),
        "abstain_rate_negative": _ratio(
            sum(result.answer_abstained for result in negative_results),
            len(negative_results),
        ),
        "citation_hit_rate_positive": _ratio(
            sum(result.citation_hit for result in positive_results),
            len(positive_results),
        ),
        "citation_present_rate_positive": _ratio(
            sum(result.citation_present for result in positive_results),
            len(positive_results),
        ),
        "average_latency_ms": round(
            sum(result.latency_ms for result in results) / len(results),
            2,
        )
        if results
        else 0.0,
    }


def write_results_csv(results: list[EvaluationResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "tenant_id",
        "question",
        "expected_sources",
        "retrieved_sources",
        "citation_sources",
        "retrieval_hit_at_k",
        "answer_abstained",
        "citation_present",
        "citation_hit",
        "latency_ms",
        "answer",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            row["expected_sources"] = "|".join(result.expected_sources)
            row["retrieved_sources"] = "|".join(result.retrieved_sources)
            row["citation_sources"] = "|".join(result.citation_sources)
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    base_settings = get_settings()
    updated_fields = {"qdrant_local_path": args.local_path or base_settings.qdrant_local_path}
    if args.top_k:
        updated_fields["retrieval_top_k"] = args.top_k
    settings = base_settings.model_copy(update=updated_fields)

    data_root = (PROJECT_ROOT / args.data_root).resolve()
    output_path = (PROJECT_ROOT / args.output).resolve()

    client = get_qdrant_client(settings)
    embedder = get_embedding_service(settings)
    generator = get_answer_generator(settings)

    if not args.skip_ingest:
        ingest_documents(
            data_root=data_root,
            client=client,
            embedder=embedder,
            settings=settings,
        )

    cases = build_default_cases()
    results = evaluate_cases(
        cases=cases,
        client=client,
        settings=settings,
        embedder=embedder,
        generator=generator,
    )
    write_results_csv(results, output_path)
    summary = summarize_results(results, cases=cases)
    summary_path = (PROJECT_ROOT / args.summary_json).resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tracker = LifecycleTracker(tracking_uri=settings.mlflow_tracking_uri)
    tracker.log_evaluation_run(
        params={
            "embedding_model_name": settings.embedding_model_name,
            "generator_backend": settings.generator_backend,
            "generator_model_name": settings.gemini_model_name if settings.generator_backend == "gemini" else settings.openai_compatible_model if settings.generator_backend == "openai_compatible" else "extractive",
            "retrieval_top_k": settings.retrieval_top_k,
            "chunk_size_chars": settings.chunk_size_chars,
        },
        metrics={
            "cases_total": summary["cases_total"],
            "retrieval_hit_rate_positive": summary["retrieval_hit_rate_positive"],
            "citation_hit_rate_positive": summary["citation_hit_rate_positive"],
            "abstain_rate_negative": summary["abstain_rate_negative"],
            "average_latency_ms": summary["average_latency_ms"],
        },
    )

    print("Evaluation complete")
    print(f"output={output_path}")
    print(f"summary_json={summary_path}")
    print("summary=" + json.dumps(summary, sort_keys=True))

    client.close()


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)


if __name__ == "__main__":
    main()
