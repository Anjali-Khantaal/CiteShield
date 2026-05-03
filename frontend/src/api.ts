export type HealthResponse = {
  status: string;
  qdrant: string;
  generator: string;
};

export type SessionContextResponse = {
  role: string;
  tenant_id: string | null;
};

export type IngestResponse = {
  tenant_id: string;
  doc_id: string;
  source: string;
  chunk_count: number;
};

export type CitationResponse = {
  source: string;
  chunk_id: number;
  modality?: "image" | "audio" | "video" | string;
  media_path?: string;
  source_url?: string;
  time_range?: string;
  frame_time?: string;
};

export type QueryResponse = {
  answer: string;
  citations: CitationResponse[];
};

export type IndexedDocumentResponse = {
  tenant_id: string;
  doc_id: string;
  source: string;
  chunk_count: number;
  accessible_by: string[];
};

export type DocumentInventoryResponse = {
  documents: IndexedDocumentResponse[];
  total_documents: number;
  total_chunks: number;
};

export type DeleteDocumentResponse = {
  tenant_id: string;
  doc_id: string;
  deleted_chunks: number;
};

type RequestOptions = {
  method?: string;
  apiKey?: string;
  body?: unknown;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function normalizeBaseUrl(apiBaseUrl: string): string {
  return apiBaseUrl.replace(/\/+$/, "");
}

async function request<T>(
  apiBaseUrl: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.apiKey) {
    headers["X-API-Key"] = options.apiKey;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${normalizeBaseUrl(apiBaseUrl)}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const isJson = response.headers
    .get("content-type")
    ?.toLowerCase()
    .includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText || "Request failed.";
    throw new ApiError(detail, response.status);
  }

  return payload as T;
}

export function getHealth(apiBaseUrl: string): Promise<HealthResponse> {
  return request<HealthResponse>(apiBaseUrl, "/health");
}

export function getTenantContext(
  apiBaseUrl: string,
  apiKey: string,
): Promise<SessionContextResponse> {
  return request<SessionContextResponse>(apiBaseUrl, "/whoami", {
    apiKey,
  });
}

export function getDocumentInventory(
  apiBaseUrl: string,
  apiKey: string,
): Promise<DocumentInventoryResponse> {
  return request<DocumentInventoryResponse>(apiBaseUrl, "/admin/documents", {
    apiKey,
  });
}

export function deleteDocument(
  apiBaseUrl: string,
  apiKey: string,
  tenantId: string,
  docId: string,
): Promise<DeleteDocumentResponse> {
  return request<DeleteDocumentResponse>(
    apiBaseUrl,
    `/admin/documents/${encodeURIComponent(tenantId)}/${encodeURIComponent(docId)}`,
    {
      method: "DELETE",
      apiKey,
    },
  );
}

export function ingestDocument(
  apiBaseUrl: string,
  apiKey: string,
  payload: { source: string; text: string; target_tenant?: string },
): Promise<IngestResponse> {
  return request<IngestResponse>(apiBaseUrl, "/ingest", {
    method: "POST",
    apiKey,
    body: payload,
  });
}

export function queryDocuments(
  apiBaseUrl: string,
  apiKey: string,
  payload: { question: string; top_k?: number },
): Promise<QueryResponse> {
  return request<QueryResponse>(apiBaseUrl, "/query", {
    method: "POST",
    apiKey,
    body: payload,
  });
}

export async function getMediaBlob(
  apiBaseUrl: string,
  apiKey: string,
  tenantId: string,
  mediaPath: string,
): Promise<Blob> {
  const response = await fetch(
    `${normalizeBaseUrl(apiBaseUrl)}/media/${encodeURIComponent(tenantId)}/${mediaPath
      .split("/")
      .map((part) => encodeURIComponent(part))
      .join("/")}`,
    {
      headers: {
        "X-API-Key": apiKey,
      },
    },
  );

  if (!response.ok) {
    throw new ApiError(response.statusText || "Media request failed.", response.status);
  }

  return response.blob();
}
