import argparse
import json
import logging
import statistics
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.metrics import get_metrics_client, get_metrics_settings
from app.routes.health import get_health_client, get_health_settings
from app.routes.ingest import get_ingest_client, get_ingest_embedder, get_ingest_settings
from app.routes.query import get_query_client, get_query_embedder, get_query_generator, get_query_settings
from app.services.embeddings import get_embedding_service
from app.services.generator import ExtractiveAnswerGenerator


TENANT_KEY = "tenant-a-dev-key"
DEFAULT_USERS = (1, 5, 10, 25)


@dataclass(frozen=True)
class TimedResult:
    latency_ms: float
    status_code: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local synthetic CiteShield load benchmarks.")
    parser.add_argument(
        "--users",
        default="1,5,10,25",
        help="Comma-separated simulated user counts.",
    )
    parser.add_argument(
        "--requests-per-user",
        type=int,
        default=20,
        help="Number of query requests per simulated user.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/benchmark_summary.json",
        help="Path to write the benchmark summary JSON.",
    )
    return parser.parse_args()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    idx = int(round((pct / 100.0) * (len(values_sorted) - 1)))
    return values_sorted[idx]


def timed_request(client: TestClient, method: str, path: str, **kwargs) -> TimedResult:
    started = perf_counter()
    response = client.request(method=method, url=path, **kwargs)
    duration_ms = (perf_counter() - started) * 1000
    return TimedResult(latency_ms=duration_ms, status_code=response.status_code)


def run_scenario(*, users: int, requests_per_user: int, tmpdir: Path) -> dict[str, object]:
    qdrant_path = tmpdir / f"qdrant-users-{users}"
    lifecycle_path = tmpdir / f"lifecycle-users-{users}.jsonl"
    qdrant = QdrantClient(path=str(qdrant_path))
    settings = get_settings().model_copy(
        update={
            "generator_backend": "extractive",
            "embedding_backend": "hash",
            "qdrant_collection_name": f"documents_benchmark_{users}",
            "lifecycle_tracking_path": str(lifecycle_path),
            "mlflow_tracking_uri": None,
        }
    )
    embedder = get_embedding_service(settings)
    generator = ExtractiveAnswerGenerator()

    app.dependency_overrides[get_ingest_settings] = lambda: settings
    app.dependency_overrides[get_ingest_embedder] = lambda: embedder
    app.dependency_overrides[get_ingest_client] = lambda: qdrant
    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: qdrant
    app.dependency_overrides[get_query_generator] = lambda: generator
    app.dependency_overrides[get_metrics_settings] = lambda: settings
    app.dependency_overrides[get_metrics_client] = lambda: qdrant
    app.dependency_overrides[get_health_settings] = lambda: settings
    app.dependency_overrides[get_health_client] = lambda: qdrant

    try:
        client = TestClient(app)
        seed_documents(client=client, users=users)
        health = timed_request(client, "GET", "/health")
        qdrant_available = health.status_code == 200

        total_requests = users * requests_per_user
        started = perf_counter()
        results = run_queries(
            client=client,
            users=users,
            requests_per_user=requests_per_user,
        )
        elapsed_seconds = perf_counter() - started
        traces = read_query_traces(lifecycle_path)
    finally:
        app.dependency_overrides.clear()
        qdrant.close()

    latencies = [result.latency_ms for result in results]
    error_count = sum(result.status_code >= 400 for result in results)
    retrieval_latencies = [trace["metrics"]["retrieval_latency_ms"] for trace in traces if trace.get("event") == "query_trace"]
    generation_latencies = [trace["metrics"]["generation_latency_ms"] for trace in traces if trace.get("event") == "query_trace"]

    return {
        "users": users,
        "requests_per_user": requests_per_user,
        "total_requests": total_requests,
        "error_count": error_count,
        "error_rate": round(error_count / total_requests, 4) if total_requests else 0.0,
        "requests_per_second": round(total_requests / elapsed_seconds, 2) if elapsed_seconds else 0.0,
        "query_p50_ms": round(percentile(latencies, 50), 2),
        "query_p95_ms": round(percentile(latencies, 95), 2),
        "query_avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "retrieval_avg_ms": round(statistics.mean(retrieval_latencies), 2) if retrieval_latencies else 0.0,
        "generation_avg_ms": round(statistics.mean(generation_latencies), 2) if generation_latencies else 0.0,
        "qdrant_available": qdrant_available,
        "generator_backend": "extractive",
        "embedding_backend": "hash",
    }


def seed_documents(*, client: TestClient, users: int) -> None:
    for i in range(max(4, users)):
        result = timed_request(
            client,
            "POST",
            "/ingest",
            headers={"X-API-Key": TENANT_KEY},
            json={
                "source": f"benchmark-{users}-{i}.md",
                "text": (
                    "Employees must use VPN for internal dashboards. "
                    "Approved production access requires MFA and a managed device."
                ),
            },
        )
        if result.status_code >= 400:
            raise RuntimeError(f"Benchmark seed ingest failed with HTTP {result.status_code}.")


def run_queries(*, client: TestClient, users: int, requests_per_user: int) -> list[TimedResult]:
    def one_request(worker_id: int, request_id: int) -> TimedResult:
        return timed_request(
            client,
            "POST",
            "/query",
            headers={
                "X-API-Key": TENANT_KEY,
                "X-Request-ID": f"bench-u{users}-w{worker_id}-r{request_id}",
            },
            json={"question": "What is the VPN rule for internal dashboards?", "top_k": 3},
        )

    futures = []
    with ThreadPoolExecutor(max_workers=users) as executor:
        for worker_id in range(users):
            for request_id in range(requests_per_user):
                futures.append(executor.submit(one_request, worker_id, request_id))
        return [future.result() for future in as_completed(futures)]


def read_query_traces(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    traces: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                traces.append(json.loads(line))
    return traces


def parse_users(raw: str) -> list[int]:
    users = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not users:
        return list(DEFAULT_USERS)
    if any(user <= 0 for user in users):
        raise ValueError("--users values must be positive integers.")
    return users


def main() -> None:
    args = parse_args()
    logging.getLogger("citeshield").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    users = parse_users(args.users)

    with tempfile.TemporaryDirectory(prefix="citeshield-bench-") as tmp:
        tmpdir = Path(tmp)
        scenarios = [
            run_scenario(users=user_count, requests_per_user=args.requests_per_user, tmpdir=tmpdir)
            for user_count in users
        ]

    summary = {
        "scenario": "local_synthetic_concurrent_testclient",
        "description": "Offline-safe concurrent FastAPI TestClient benchmark with local Qdrant path storage.",
        "scenarios": scenarios,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
