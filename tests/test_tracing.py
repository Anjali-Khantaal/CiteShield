import json
from pathlib import Path

from app.tracing import LifecycleTracker


def test_lifecycle_tracker_logs_query_trace_jsonl(tmp_path: Path) -> None:
    output = tmp_path / "lifecycle.jsonl"
    tracker = LifecycleTracker(jsonl_path=str(output))

    tracker.log_query_trace(
        request_id="req-1",
        tenant_id="tenant_a",
        route="/query",
        embedding_backend="hash",
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        generator_backend="extractive",
        generator_model_name="extractive",
        top_k=3,
        retrieval_latency_ms=4.2,
        generation_latency_ms=1.7,
        retrieved_sources=["remote_work_policy.md"],
        citation_count=1,
        abstained=False,
    )

    event = json.loads(output.read_text(encoding="utf-8").splitlines()[0])

    assert event["event"] == "query_trace"
    assert event["request_id"] == "req-1"
    assert event["tenant_id"] == "tenant_a"
    assert event["params"]["retrieval_top_k"] == 3
    assert event["metrics"]["retrieval_latency_ms"] == 4.2
    assert event["metrics"]["citation_count"] == 1
    assert event["retrieved_sources"] == ["remote_work_policy.md"]
    assert event["mlflow_status"] == "disabled"


def test_lifecycle_tracker_logs_evaluation_artifacts_jsonl(tmp_path: Path) -> None:
    output = tmp_path / "lifecycle.jsonl"
    tracker = LifecycleTracker(jsonl_path=str(output))

    tracker.log_evaluation_run(
        params={"embedding_backend": "hash", "retrieval_top_k": 3},
        metrics={"retrieval_hit_rate_positive": 1.0, "cross_tenant_eval_failures": 0},
        artifacts={"evaluation_summary": "/tmp/summary.json"},
    )

    event = json.loads(output.read_text(encoding="utf-8").splitlines()[0])

    assert event["event"] == "evaluation_run"
    assert event["params"]["embedding_backend"] == "hash"
    assert event["metrics"]["cross_tenant_eval_failures"] == 0
    assert event["artifacts"] == {"evaluation_summary": "/tmp/summary.json"}
