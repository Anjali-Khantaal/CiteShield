from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    generator: str


class SessionContextResponse(BaseModel):
    role: str
    tenant_id: str | None = None


class IndexedDocumentResponse(BaseModel):
    tenant_id: str
    doc_id: str
    source: str
    chunk_count: int
    accessible_by: list[str]


class DocumentInventoryResponse(BaseModel):
    documents: list[IndexedDocumentResponse]
    total_documents: int
    total_chunks: int


class DeleteDocumentResponse(BaseModel):
    tenant_id: str
    doc_id: str
    deleted_chunks: int


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str = Field(min_length=1)
    text: str = Field(min_length=1)
    target_tenant: str | None = None


class IngestResponse(BaseModel):
    tenant_id: str
    doc_id: str
    source: str
    chunk_count: int


class CitationResponse(BaseModel):
    source: str
    chunk_id: int


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
