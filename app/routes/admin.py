from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client import QdrantClient

from app.auth import SuperuserContext, get_superuser_context
from app.config import Settings, get_settings
from app.metrics import refresh_indexed_chunks
from app.models import (
    DeleteDocumentResponse,
    DocumentInventoryResponse,
    IndexedDocumentResponse,
)
from app.services.vector_store import (
    delete_document_chunks,
    get_qdrant_client,
    list_indexed_documents,
)

router = APIRouter(tags=["admin"])


def get_admin_settings() -> Settings:
    return get_settings()


def get_admin_client(
    settings: Settings = Depends(get_admin_settings),
) -> QdrantClient:
    return get_qdrant_client(settings)


@router.get("/admin/documents", response_model=DocumentInventoryResponse)
def list_documents(
    _superuser: SuperuserContext = Depends(get_superuser_context),
    settings: Settings = Depends(get_admin_settings),
    client: QdrantClient = Depends(get_admin_client),
) -> DocumentInventoryResponse:
    documents = list_indexed_documents(
        client=client,
        collection_name=settings.qdrant_collection_name,
    )
    response_documents = [
        IndexedDocumentResponse(
            tenant_id=document.tenant_id,
            doc_id=document.doc_id,
            source=document.source,
            chunk_count=document.chunk_count,
            accessible_by=[document.tenant_id],
        )
        for document in documents
    ]
    return DocumentInventoryResponse(
        documents=response_documents,
        total_documents=len(response_documents),
        total_chunks=sum(document.chunk_count for document in documents),
    )


@router.delete(
    "/admin/documents/{tenant_id}/{doc_id}",
    response_model=DeleteDocumentResponse,
)
def delete_document(
    tenant_id: str,
    doc_id: str,
    _superuser: SuperuserContext = Depends(get_superuser_context),
    settings: Settings = Depends(get_admin_settings),
    client: QdrantClient = Depends(get_admin_client),
) -> DeleteDocumentResponse:
    deleted_chunks = delete_document_chunks(
        client=client,
        collection_name=settings.qdrant_collection_name,
        tenant_id=tenant_id,
        doc_id=doc_id,
    )

    if deleted_chunks == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    refresh_indexed_chunks(
        client=client,
        collection_name=settings.qdrant_collection_name,
    )
    return DeleteDocumentResponse(
        tenant_id=tenant_id,
        doc_id=doc_id,
        deleted_chunks=deleted_chunks,
    )
