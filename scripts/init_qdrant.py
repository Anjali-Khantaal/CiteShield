import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.services.vector_store import (
    SUPPORTED_CHUNK_PAYLOAD_FIELDS,
    TENANT_ID_FIELD,
    ensure_documents_collection,
    get_qdrant_client,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize the CiteShield Qdrant collection and tenant index.",
    )
    parser.add_argument(
        "--local-path",
        help="Use Qdrant local mode at this path instead of an HTTP server.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings().model_copy(
        update={"qdrant_local_path": args.local_path or get_settings().qdrant_local_path},
    )

    client = get_qdrant_client(settings)
    ensure_documents_collection(
        client=client,
        collection_name=settings.qdrant_collection_name,
        vector_size=settings.embedding_vector_size,
    )

    collection_info = client.get_collection(settings.qdrant_collection_name)
    payload_schema = getattr(collection_info, "payload_schema", {})

    print("Qdrant initialization complete")
    if settings.qdrant_local_path:
        print(f"backend=local:{settings.qdrant_local_path}")
    else:
        print(f"backend=http:{settings.qdrant_url}")
    print(f"collection={settings.qdrant_collection_name}")
    print(f"vector_size={settings.embedding_vector_size}")
    if settings.qdrant_local_path:
        print("tenant_index_present=not_verifiable_in_local_mode")
    else:
        print(f"tenant_index_present={TENANT_ID_FIELD in payload_schema}")
    print(
        "expected_payload_fields="
        + ",".join(SUPPORTED_CHUNK_PAYLOAD_FIELDS),
    )


if __name__ == "__main__":
    main()
