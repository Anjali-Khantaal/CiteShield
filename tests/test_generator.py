from app.services.generator import (
    ExtractiveAnswerGenerator,
    GeminiAnswerGenerator,
    GeminiStructuredAnswer,
    OpenAICompatibleAnswerGenerator,
    generate_answer,
    get_answer_generator,
)
from app.services.retriever import RetrievalMatch
from app.config import get_settings


class FakeGeminiResponse:
    def __init__(self, parsed: GeminiStructuredAnswer) -> None:
        self.parsed = parsed


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


def test_generate_answer_uses_clean_extracted_text_from_multimodal_markdown() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="tenant_a_security_access_poster",
            chunk_id=0,
            source="derived/multimodal/tenant_a_security_access_poster.md",
            text=(
                "# Tenant A Security Access Poster\n\n"
                "Modality: image\n"
                "Source file: media/images/security_access_poster.png\n"
                "Original URL: generated://citeshield/tenant-a-security-poster\n"
                "License: Generated prototype sample for CiteShield\n"
                "Attribution: CiteShield synthetic dataset\n\n"
                "## Extracted text\n\n"
                "Tenant A Security Access Poster\n\n"
                "Tenant: tenant_a\n\n"
                "Approved production access requires MFA, a managed device, and an active ticket "
                "referencing the change window. Never send API keys over chat.\n\n"
                "CiteShield multimodal OCR sample\n\n"
                "## Segments\n\n"
                "- full asset: extracted text above\n"
            ),
            line_range="1-20",
            score=0.92,
            modality="image",
            media_path="media/images/security_access_poster.png",
            source_url="generated://citeshield/tenant-a-security-poster",
        )
    ]

    result = generate_answer(
        "What does the security poster say about MFA?",
        matches,
        generator=ExtractiveAnswerGenerator(),
    )

    assert result.answer == (
        "Approved production access requires MFA, a managed device, and an active ticket "
        "referencing the change window."
    )
    assert "Modality" not in result.answer
    assert "Source file" not in result.answer
    assert "Original URL" not in result.answer
    assert result.citations[0].modality == "image"


def test_generate_answer_prefers_image_citation_for_poster_question_with_duplicate_text() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="tenant_a_security_access_poster",
            chunk_id=0,
            source="derived/multimodal/tenant_a_security_access_poster.md",
            text=(
                "# Tenant A Security Access Poster\n\n"
                "## Extracted text\n\n"
                "Approved production access requires MFA, a managed device, and an active ticket "
                "referencing the change window."
            ),
            line_range="1-8",
            score=0.43,
            modality="image",
            media_path="media/images/security_access_poster.png",
        ),
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="security_guidelines",
            chunk_id=0,
            source="security_guidelines.md",
            text=(
                "Approved production access requires MFA, a managed device, and an active ticket "
                "referencing the change window."
            ),
            line_range="9-9",
            score=0.47,
        ),
    ]

    result = generate_answer(
        "What does the security access poster say is required for approved production access?",
        matches,
        generator=ExtractiveAnswerGenerator(),
    )

    assert "MFA" in result.answer
    assert result.citations[0].source == "derived/multimodal/tenant_a_security_access_poster.md"
    assert result.citations[0].modality == "image"


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


def test_gemini_answer_generator_returns_grounded_answer_and_citations() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="remote_work_policy",
            chunk_id=0,
            source="remote_work_policy.md",
            text="Employees must connect through the corporate VPN before opening internal dashboards.",
            line_range="1-1",
            score=0.82,
        ),
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="security_guidelines",
            chunk_id=2,
            source="security_guidelines.md",
            text="Access to customer systems also requires MFA.",
            line_range="2-2",
            score=0.46,
        ),
    ]

    generator = GeminiAnswerGenerator(
        api_key="test-key",
        model_name="gemini-2.5-flash",
        generate_content=lambda **_: FakeGeminiResponse(
            GeminiStructuredAnswer(
                answer="Employees must use the corporate VPN before opening internal dashboards.",
                used_chunk_indices=[0],
            )
        ),
    )

    result = generate_answer(
        "What is the VPN rule for internal dashboards?",
        matches,
        generator=generator,
    )

    assert "VPN" in result.answer
    assert result.citations == [type(result.citations[0])(source="remote_work_policy.md", chunk_id=0)]


def test_gemini_answer_generator_tries_llm_fallback_model() -> None:
    calls: list[str] = []
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="security_guidelines",
            chunk_id=0,
            source="security_guidelines.md",
            text="Approved production access requires MFA and a managed device.",
            line_range="1-1",
            score=0.92,
        )
    ]

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == "gemini-2.5-flash":
            raise RuntimeError("503 UNAVAILABLE")
        return FakeGeminiResponse(
            GeminiStructuredAnswer(
                answer="Approved production access requires MFA and a managed device.",
                used_chunk_indices=[0],
            )
        )

    generator = GeminiAnswerGenerator(
        api_key="test-key",
        model_name="gemini-2.5-flash",
        fallback_model_names=("gemini-2.5-flash-lite",),
        generate_content=fake_generate_content,
    )

    result = generate_answer(
        "What does the policy say about MFA?",
        matches,
        generator=generator,
    )

    assert calls == ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    assert "MFA" in result.answer
    assert result.citations == [type(result.citations[0])(source="security_guidelines.md", chunk_id=0)]


def test_gemini_prompt_uses_clean_multimodal_context() -> None:
    captured = {}
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="tenant_a_security_access_poster",
            chunk_id=0,
            source="derived/multimodal/tenant_a_security_access_poster.md",
            text=(
                "# Tenant A Security Access Poster\n\n"
                "Modality: image\n"
                "Source file: media/images/security_access_poster.png\n"
                "Original URL: generated://citeshield/tenant-a-security-poster\n"
                "License: Generated prototype sample for CiteShield\n"
                "Attribution: CiteShield synthetic dataset\n\n"
                "## Extracted text\n\n"
                "Tenant A Security Access Poster\n\n"
                "Tenant: tenant_a\n\n"
                "Approved production access requires MFA and a managed device.\n\n"
                "CiteShield multimodal OCR sample\n\n"
                "## Segments\n\n"
                "- full asset: extracted text above\n"
            ),
            line_range="1-20",
            score=0.95,
            modality="image",
            media_path="media/images/security_access_poster.png",
            source_url="generated://citeshield/tenant-a-security-poster",
        )
    ]

    def fake_generate_content(**kwargs):
        captured["contents"] = kwargs["contents"]
        return FakeGeminiResponse(
            GeminiStructuredAnswer(
                answer="Approved production access requires MFA and a managed device.",
                used_chunk_indices=[0],
            )
        )

    generator = GeminiAnswerGenerator(
        api_key="test-key",
        model_name="gemini-2.5-flash",
        generate_content=fake_generate_content,
    )

    result = generate_answer(
        "What does the security poster say about MFA?",
        matches,
        generator=generator,
    )

    prompt = captured["contents"]
    assert "Approved production access requires MFA and a managed device." in prompt
    assert "Source file:" not in prompt
    assert "Original URL:" not in prompt
    assert "Attribution:" not in prompt
    assert result.citations[0].modality == "image"


def test_gemini_answer_generator_abstains_when_model_returns_invalid_chunk_indices() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_b",
            doc_id="expense_policy",
            chunk_id=0,
            source="expense_policy.md",
            text="Refund requests are reviewed by billing operations.",
            line_range="1-1",
            score=0.77,
        )
    ]

    generator = GeminiAnswerGenerator(
        api_key="test-key",
        model_name="gemini-2.5-flash",
        generate_content=lambda **_: FakeGeminiResponse(
            GeminiStructuredAnswer(
                answer="Refund requests are reviewed by billing operations.",
                used_chunk_indices=[9],
            )
        ),
    )

    result = generate_answer(
        "Who reviews refund requests?",
        matches,
        generator=generator,
    )

    assert "do not have enough reliable context" in result.answer
    assert result.citations == []


def test_gemini_answer_generator_falls_back_to_extractive_when_provider_fails() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="remote_work_policy",
            chunk_id=0,
            source="remote_work_policy.md",
            text="Employees must connect through the corporate VPN before opening internal dashboards.",
            line_range="1-1",
            score=0.82,
        )
    ]

    def failing_generate_content(**_: object) -> object:
        raise RuntimeError("503 UNAVAILABLE")

    generator = GeminiAnswerGenerator(
        api_key="test-key",
        model_name="gemini-2.5-flash",
        generate_content=failing_generate_content,
        fallback_generator=ExtractiveAnswerGenerator(),
    )

    result = generate_answer(
        "What is the VPN rule for internal dashboards?",
        matches,
        generator=generator,
    )

    assert "VPN" in result.answer
    assert result.citations == [type(result.citations[0])(source="remote_work_policy.md", chunk_id=0)]


def test_configured_gemini_generator_can_disable_fallback() -> None:
    settings = get_settings().model_copy(
        update={
            "generator_backend": "gemini",
            "gemini_api_key": "test-key",
            "generator_enable_fallback": False,
        }
    )

    generator = get_answer_generator(settings)

    assert isinstance(generator, GeminiAnswerGenerator)
    assert generator.fallback_generator is None
    assert generator.fallback_model_names == ("gemini-2.5-flash-lite",)


def test_openai_compatible_generator_returns_grounded_answer(monkeypatch) -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="remote_work_policy",
            chunk_id=0,
            source="remote_work_policy.md",
            text="Employees must connect through the corporate VPN before opening internal dashboards.",
            line_range="1-1",
            score=0.82,
        )
    ]

    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"answer":"Employees must use VPN for internal dashboards.",'
                                '"abstained":false,"used_chunk_indices":[0]}'
                            )
                        }
                    }
                ]
            }

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.generator.httpx.post", fake_post)

    generator = OpenAICompatibleAnswerGenerator(
        base_url="http://localhost:8001/v1",
        model_name="mistral-7b-instruct",
        api_key="test-key",
    )
    result = generate_answer(
        "What is the VPN rule?",
        matches,
        generator=generator,
    )

    assert result.answer == "Employees must use VPN for internal dashboards."
    assert result.citations == [type(result.citations[0])(source="remote_work_policy.md", chunk_id=0)]
    assert captured["url"] == "http://localhost:8001/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "mistral-7b-instruct"
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_openai_compatible_generator_falls_back_to_extractive(monkeypatch) -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="remote_work_policy",
            chunk_id=0,
            source="remote_work_policy.md",
            text="Employees must connect through the corporate VPN before opening internal dashboards.",
            line_range="1-1",
            score=0.82,
        )
    ]

    def fake_post(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.generator.httpx.post", fake_post)

    generator = OpenAICompatibleAnswerGenerator(
        base_url="http://localhost:8001/v1",
        model_name="mistral-7b-instruct",
        fallback_generator=ExtractiveAnswerGenerator(),
    )
    result = generate_answer(
        "What is the VPN rule for internal dashboards?",
        matches,
        generator=generator,
    )

    assert "VPN" in result.answer
    assert result.citations == [type(result.citations[0])(source="remote_work_policy.md", chunk_id=0)]
