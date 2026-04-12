import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.services.embeddings import get_embedding_service
from app.services.ingestion import build_tenant_point_counts, ingest_documents
from app.services.vector_store import get_qdrant_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read tenant sample docs, chunk them, embed them, and ingest them into Qdrant.",
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Directory containing tenant_a/ and tenant_b/ source documents.",
    )
    parser.add_argument(
        "--local-path",
        help="Use Qdrant local mode at this path instead of the live HTTP server.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_settings = get_settings()
    settings = base_settings.model_copy(
        update={"qdrant_local_path": args.local_path or base_settings.qdrant_local_path}
    )

    data_root = (PROJECT_ROOT / args.data_root).resolve()
    client = get_qdrant_client(settings)
    embedder = get_embedding_service(settings)

    summary = ingest_documents(
        data_root=data_root,
        client=client,
        embedder=embedder,
        settings=settings,
    )
    tenant_point_counts = build_tenant_point_counts(
        client=client,
        collection_name=settings.qdrant_collection_name,
    )

    print("Ingestion complete")
    print(f"collection={summary.collection_name}")
    print(f"documents={summary.document_count}")
    print(f"chunks={summary.chunk_count}")
    print("tenant_point_counts=" + json.dumps(tenant_point_counts, sort_keys=True))
    print(
        "documents_detail="
        + json.dumps(
            [
                {
                    "tenant_id": result.tenant_id,
                    "doc_id": result.doc_id,
                    "source": result.source,
                    "chunk_count": result.chunk_count,
                }
                for result in summary.documents
            ],
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
