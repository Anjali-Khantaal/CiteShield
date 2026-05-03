import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.health import get_health_client, get_health_settings
from app.routes.ingest import get_ingest_client, get_ingest_embedder, get_ingest_settings
from app.routes.query import get_query_client, get_query_embedder, get_query_generator, get_query_settings
from app.services.embeddings import get_embedding_service
from app.services.generator import ExtractiveAnswerGenerator, get_answer_generator
from app.services.ingestion import ingest_documents
from app.services.multimodal import load_multimodal_manifest, process_multimodal_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process and optionally ingest multimodal sample files.")
    parser.add_argument("--manifest", default="data/multimodal_manifest.json")
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--demo-query", action="store_true")
    parser.add_argument("--demo-generator", choices=("extractive", "configured"), default="extractive")
    parser.add_argument("--local-path", default="artifacts/qdrant_multimodal")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = (PROJECT_ROOT / args.data_root).resolve()
    manifest_path = (PROJECT_ROOT / args.manifest).resolve()
    items = load_multimodal_manifest(manifest_path, data_root=data_root)
    results = process_multimodal_manifest(items, data_root=data_root)
    print("processed=" + json.dumps([result.derived_path.as_posix() for result in results]))

    if args.ingest:
        local_path = (PROJECT_ROOT / args.local_path).resolve()
        settings = get_settings().model_copy(
            update={
                "qdrant_local_path": str(local_path),
            }
        )
        client = QdrantClient(path=str(local_path))
        embedder = get_embedding_service(settings)
        try:
            summary = ingest_documents(data_root=data_root, client=client, embedder=embedder, settings=settings)
            print("ingested=" + json.dumps({"documents": summary.document_count, "chunks": summary.chunk_count}))
            if args.demo_query:
                _run_demo_queries(
                    client=client,
                    settings=settings,
                    embedder=embedder,
                    items=items,
                    demo_generator=args.demo_generator,
                )
        finally:
            app.dependency_overrides.clear()
            client.close()


def _run_demo_queries(*, client: QdrantClient, settings, embedder, items, demo_generator: str) -> None:
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: client
    app.dependency_overrides[get_query_generator] = (
        (lambda: get_answer_generator(settings))
        if demo_generator == "configured"
        else (lambda: ExtractiveAnswerGenerator())
    )
    app.dependency_overrides[get_ingest_settings] = lambda: settings
    app.dependency_overrides[get_ingest_embedder] = lambda: embedder
    app.dependency_overrides[get_ingest_client] = lambda: client
    app.dependency_overrides[get_health_settings] = lambda: settings
    app.dependency_overrides[get_health_client] = lambda: client

    tenant_keys = {
        "tenant_a": settings.tenant_a_api_key,
        "tenant_b": settings.tenant_b_api_key,
    }
    test_client = TestClient(app)
    for item in items:
        term = item.expected_terms[0] if item.expected_terms else item.title
        response = test_client.post(
            "/query",
            headers={"X-API-Key": tenant_keys[item.tenant_id]},
            json={"question": f"What does {item.title} mention about {term}?", "top_k": 5},
        )
        payload = response.json()
        citations = payload.get("citations", [])
        print(
            "demo_query="
            + json.dumps(
                {
                    "tenant_id": item.tenant_id,
                    "modality": item.modality,
                    "status_code": response.status_code,
                    "citations": citations,
                },
                sort_keys=True,
            )
        )
        if response.status_code != 200:
            raise SystemExit(f"Demo query failed for {item.modality}: HTTP {response.status_code}")
        if not any(citation.get("modality") == item.modality for citation in citations):
            raise SystemExit(f"Demo query did not return a {item.modality} citation.")


if __name__ == "__main__":
    main()
