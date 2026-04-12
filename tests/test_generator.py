from app.services.generator import ExtractiveAnswerGenerator, generate_answer
from app.services.retriever import RetrievalMatch


def test_generate_answer_returns_grounded_answer_and_citations() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="remote_work_policy",
            chunk_id=4,
            source="policy_a.md",
            text=(
                "Remote Work Policy. Employees must connect through the corporate VPN "
                "before opening internal dashboards."
            ),
            line_range="1-2",
            score=0.62,
        ),
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="security_guidelines",
            chunk_id=2,
            source="guide_a.md",
            text="Approved production access requires MFA and a managed device.",
            line_range="3-3",
            score=0.21,
        ),
    ]

    result = generate_answer(
        "How do employees use VPN for internal dashboards?",
        matches,
        generator=ExtractiveAnswerGenerator(),
    )

    assert "VPN" in result.answer
    assert result.citations == [type(result.citations[0])(source="policy_a.md", chunk_id=4)]


def test_generate_answer_abstains_when_context_is_weak() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="holiday_schedule",
            chunk_id=0,
            source="schedule.md",
            text="The office closes on regional holidays and during scheduled maintenance windows.",
            line_range="1-1",
            score=0.01,
        )
    ]

    result = generate_answer(
        "What is the VPN rule?",
        matches,
        generator=ExtractiveAnswerGenerator(min_score_threshold=0.2),
    )

    assert "do not have enough reliable context" in result.answer
    assert result.citations == []


def test_generate_answer_skips_irrelevant_sentences_from_same_chunk() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="remote_work_policy",
            chunk_id=0,
            source="remote_work_policy.md",
            text=(
                "Employees must connect through the corporate VPN before opening internal dashboards. "
                "Travel reimbursement for home-office equipment is capped at 300 dollars per calendar year."
            ),
            line_range="1-2",
            score=0.72,
        )
    ]

    result = generate_answer(
        "How do employees use VPN for internal dashboards?",
        matches,
        generator=ExtractiveAnswerGenerator(),
    )

    assert "VPN" in result.answer
    assert "300 dollars" not in result.answer
    assert result.citations == [type(result.citations[0])(source="remote_work_policy.md", chunk_id=0)]


def test_generate_answer_abstains_when_high_score_chunk_has_no_question_overlap() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_b",
            doc_id="customer_support_handbook",
            chunk_id=0,
            source="customer_support_handbook.md",
            text=(
                "Escalations involving data exports should be routed to the platform support queue. "
                "Support agents must acknowledge severity-one incidents within fifteen minutes."
            ),
            line_range="1-2",
            score=0.91,
        )
    ]

    result = generate_answer(
        "What is the VPN rule for customer data work?",
        matches,
        generator=ExtractiveAnswerGenerator(),
    )

    assert "do not have enough reliable context" in result.answer
    assert result.citations == []
