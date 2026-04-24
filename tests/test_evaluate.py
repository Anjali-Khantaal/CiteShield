from scripts.evaluate import EvaluationResult, build_default_cases, summarize_results


def test_build_default_cases_has_expected_balance() -> None:
    cases = build_default_cases()

    assert len(cases) == 12
    assert sum(case.tenant_id == "tenant_a" and not case.expect_abstain for case in cases) == 5
    assert sum(case.tenant_id == "tenant_b" and not case.expect_abstain for case in cases) == 5
    assert sum(case.expect_abstain for case in cases) == 2


def test_summarize_results_tracks_hits_abstentions_and_latency() -> None:
    cases = build_default_cases()[:2]
    results = [
        EvaluationResult(
            case_id=cases[0].case_id,
            tenant_id=cases[0].tenant_id,
            question=cases[0].question,
            expected_sources=cases[0].expected_sources,
            retrieved_sources=("remote_work_policy.md",),
            citation_sources=("remote_work_policy.md",),
            retrieval_hit_at_k=True,
            answer_abstained=False,
            citation_present=True,
            citation_hit=True,
            latency_ms=12.5,
            answer="Employees may work remotely on Mondays and Fridays.",
        ),
        EvaluationResult(
            case_id=cases[1].case_id,
            tenant_id=cases[1].tenant_id,
            question=cases[1].question,
            expected_sources=cases[1].expected_sources,
            retrieved_sources=(),
            citation_sources=(),
            retrieval_hit_at_k=False,
            answer_abstained=True,
            citation_present=False,
            citation_hit=False,
            latency_ms=7.5,
            answer="I do not have enough reliable context in the retrieved documents to answer that confidently.",
        ),
    ]

    summary = summarize_results(results, cases=cases)

    assert summary == {
        "cases_total": 2,
        "positive_cases": 2,
        "negative_cases": 0,
        "retrieval_hit_rate_overall": 0.5,
        "retrieval_hit_rate_positive": 0.5,
        "abstain_rate_negative": 0.0,
        "citation_hit_rate_positive": 0.5,
        "citation_present_rate_positive": 0.5,
        "average_latency_ms": 10.0,
    }
