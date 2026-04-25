import json
import logging
import statistics
import tempfile
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


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    idx = int(round((pct / 100.0) * (len(values_sorted) - 1)))
    return values_sorted[idx]


def timed_request(client: TestClient, method: str, path: str, **kwargs) -> tuple[float, int]:
    started = perf_counter()
    response = client.request(method=method, url=path, **kwargs)
    duration_ms = (perf_counter() - started) * 1000
    return duration_ms, response.status_code


def main() -> None:
    logging.getLogger("citeshield").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    with tempfile.TemporaryDirectory(prefix="citeshield-bench-") as tmpdir:
        qdrant = QdrantClient(path=tmpdir)
        settings = get_settings().model_copy(
            update={
                "generator_backend": "extractive",
                "embedding_backend": "hash",
                "qdrant_collection_name": "documents_benchmark",
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

        query_latencies: list[float] = []
        health_latencies: list[float] = []
        ingest_latencies: list[float] = []
        errors = 0

        started_all = perf_counter()
        client = TestClient(app)
        try:
            # Seed one document.
            _, status = timed_request(
                client,
                "POST",
                "/ingest",
                headers={"X-API-Key": TENANT_KEY},
                json={"source": "benchmark-seed.md", "text": "Employees must use VPN for internal dashboards."},
            )
            if status >= 400:
                errors += 1

            for i in range(20):
                latency, status = timed_request(
                    client,
                    "POST",
                    "/ingest",
                    headers={"X-API-Key": TENANT_KEY},
                    json={"source": f"benchmark-{i}.md", "text": "Employees must use VPN for internal dashboards."},
                )
                ingest_latencies.append(latency)
                if status >= 400:
                    errors += 1

            for _ in range(200):
                latency, status = timed_request(
                    client,
                    "POST",
                    "/query",
                    headers={"X-API-Key": TENANT_KEY},
                    json={"question": "What is the VPN rule?", "top_k": 3},
                )
                query_latencies.append(latency)
                if status >= 400:
                    errors += 1

            for _ in range(50):
                latency, status = timed_request(client, "GET", "/health")
                health_latencies.append(latency)
                if status >= 400:
                    errors += 1
        finally:
            app.dependency_overrides.clear()
            qdrant.close()

        elapsed = perf_counter() - started_all
        total_requests = len(query_latencies) + len(health_latencies) + len(ingest_latencies) + 1

    summary = {
        "generator_backend": "extractive",
        "embedding_backend": "hash",
        "total_requests": total_requests,
        "error_count": errors,
        "error_rate": round(errors / total_requests, 4),
        "requests_per_second": round(total_requests / elapsed, 2),
        "query_p50_ms": round(percentile(query_latencies, 50), 2),
        "query_p95_ms": round(percentile(query_latencies, 95), 2),
        "query_avg_ms": round(statistics.mean(query_latencies), 2),
    }

    output = Path("artifacts/benchmark_summary.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
