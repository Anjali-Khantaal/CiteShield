import { FormEvent, startTransition, useEffect, useState } from "react";

import {
  ApiError,
  type CitationResponse,
  type DocumentInventoryResponse,
  type HealthResponse,
  type IngestResponse,
  type IndexedDocumentResponse,
  type QueryResponse,
  type SessionContextResponse,
  deleteDocument,
  getDocumentInventory,
  getHealth,
  getMediaBlob,
  getTenantContext,
  ingestDocument,
  queryDocuments,
} from "./api";

const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const STORAGE_KEYS = {
  apiBaseUrl: "citeshield.apiBaseUrl",
  apiKey: "citeshield.apiKey",
};

const DEV_KEY_OPTIONS = [
  { label: "Tenant A", value: "tenant-a-dev-key" },
  { label: "Tenant B", value: "tenant-b-dev-key" },
  { label: "Superuser", value: "superuser-dev-key" },
] as const;

const TENANT_OPTIONS = [
  { label: "Tenant A", value: "tenant_a" },
  { label: "Tenant B", value: "tenant_b" },
] as const;

type TabKey = "environment" | "workflow" | "ingest" | "query" | "documents";

const STEP_TABS: Array<{
  id: TabKey;
  step: string;
  label: string;
  helper: string;
}> = [
  {
    id: "workflow",
    step: "01",
    label: "Workflow",
    helper: "Order of work",
  },
  {
    id: "environment",
    step: "02",
    label: "Environment",
    helper: "API and tenant",
  },
  {
    id: "query",
    step: "03",
    label: "Query",
    helper: "Ask and inspect",
  },
  {
    id: "ingest",
    step: "04",
    label: "Document ingest",
    helper: "Add or refresh content",
  },
  {
    id: "documents",
    step: "05",
    label: "Documents",
    helper: "Inventory and delete",
  },
];

function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.status}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error.";
}

function inferTenantFromApiKey(apiKey: string): string | null {
  if (apiKey === "tenant-a-dev-key") {
    return "tenant_a";
  }
  if (apiKey === "tenant-b-dev-key") {
    return "tenant_b";
  }
  return null;
}

function getCitationMediaLabel(citation: CitationResponse): string {
  if (!citation.modality) {
    return "Text";
  }
  return citation.modality.charAt(0).toUpperCase() + citation.modality.slice(1);
}

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("workflow");

  const [apiBaseUrl, setApiBaseUrl] = useState(() => {
    return window.localStorage.getItem(STORAGE_KEYS.apiBaseUrl) ?? DEFAULT_API_BASE_URL;
  });
  const [apiKey, setApiKey] = useState(() => {
    return window.localStorage.getItem(STORAGE_KEYS.apiKey) ?? "";
  });

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [sessionContext, setSessionContext] = useState<SessionContextResponse | null>(null);
  const [tenantError, setTenantError] = useState<string | null>(null);

  const [ingestSource, setIngestSource] = useState("policy.md");
  const [ingestText, setIngestText] = useState("");
  const [ingestTargetTenant, setIngestTargetTenant] = useState<string>(
    () => inferTenantFromApiKey(window.localStorage.getItem(STORAGE_KEYS.apiKey) ?? "") ?? "tenant_a",
  );
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [ingestLoading, setIngestLoading] = useState(false);

  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState("3");
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [documentInventory, setDocumentInventory] = useState<DocumentInventoryResponse | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [documentsNotice, setDocumentsNotice] = useState<string | null>(null);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const activeTenantId =
    sessionContext?.role === "tenant" && sessionContext.tenant_id
      ? sessionContext.tenant_id
      : inferTenantFromApiKey(apiKey);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.apiBaseUrl, apiBaseUrl);
  }, [apiBaseUrl]);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEYS.apiKey, apiKey);
  }, [apiKey]);

  useEffect(() => {
    setSessionContext(null);
    setTenantError(null);
    setDocumentInventory(null);
    setDocumentsError(null);
    setDocumentsNotice(null);
  }, [apiKey, apiBaseUrl]);

  useEffect(() => {
    void refreshHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const resolvedTenantFromSession =
      sessionContext?.role === "tenant" && sessionContext.tenant_id ? sessionContext.tenant_id : null;
    const resolvedTenantFromKey = inferTenantFromApiKey(apiKey);
    const nextTenant = resolvedTenantFromSession ?? resolvedTenantFromKey;

    if (nextTenant) {
      setIngestTargetTenant(nextTenant);
      return;
    }

    if (!apiKey.trim()) {
      setIngestTargetTenant("tenant_a");
    }
  }, [apiKey, sessionContext]);

  useEffect(() => {
    if (activeTab === "documents" && apiKey === "superuser-dev-key") {
      void refreshDocuments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  async function refreshHealth() {
    setHealthLoading(true);
    setHealthError(null);
    setTenantError(null);
    try {
      const healthResponse = await getHealth(apiBaseUrl);
      startTransition(() => {
        setHealth(healthResponse);
      });

      if (!apiKey.trim()) {
        setSessionContext(null);
        return;
      }

      try {
        const tenantResponse = await getTenantContext(apiBaseUrl, apiKey.trim());
        startTransition(() => {
          setSessionContext(tenantResponse);
        });
      } catch (error) {
        setSessionContext(null);
        setTenantError(formatApiError(error));
      }
    } catch (error) {
      setHealth(null);
      setHealthError(formatApiError(error));
    } finally {
      setHealthLoading(false);
    }
  }

  async function handleIngest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey.trim()) {
      setIngestError("Select a tenant key before ingesting documents.");
      return;
    }
    if (!ingestTargetTenant) {
      setIngestError("Select the target tenant before ingesting.");
      return;
    }

    setIngestLoading(true);
    setIngestError(null);
    try {
      const response = await ingestDocument(apiBaseUrl, apiKey.trim(), {
        source: ingestSource.trim(),
        text: ingestText.trim(),
        target_tenant: ingestTargetTenant,
      });
      startTransition(() => {
        setIngestResult(response);
        setSessionContext(
          apiKey === "superuser-dev-key"
            ? { role: "superuser", tenant_id: null }
            : { role: "tenant", tenant_id: response.tenant_id },
        );
      });
      setIngestText("");
      setActiveTab("query");
      void refreshHealth();
    } catch (error) {
      setIngestResult(null);
      setIngestError(formatApiError(error));
    } finally {
      setIngestLoading(false);
    }
  }

  async function handleQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiKey.trim()) {
      setQueryError("Select a tenant key before querying.");
      return;
    }
    if (apiKey === "superuser-dev-key") {
      setQueryError("Switch to Tenant A or Tenant B to query tenant content.");
      return;
    }

    const parsedTopK = Number.parseInt(topK, 10);
    setQueryLoading(true);
    setQueryError(null);
    try {
      const response = await queryDocuments(apiBaseUrl, apiKey.trim(), {
        question: question.trim(),
        top_k: Number.isNaN(parsedTopK) ? undefined : parsedTopK,
      });
      startTransition(() => {
        setQueryResult(response);
      });
    } catch (error) {
      setQueryResult(null);
      setQueryError(formatApiError(error));
    } finally {
      setQueryLoading(false);
    }
  }

  async function refreshDocuments() {
    if (!apiKey.trim()) {
      setDocumentsError("Select the superuser key to view the full document inventory.");
      setDocumentInventory(null);
      return;
    }
    if (apiKey !== "superuser-dev-key") {
      setDocumentsError("Select the superuser key to view the full document inventory.");
      setDocumentInventory(null);
      return;
    }

    setDocumentsLoading(true);
    setDocumentsError(null);
    setDocumentsNotice(null);

    try {
      const response = await getDocumentInventory(apiBaseUrl, apiKey.trim());
      startTransition(() => {
        setDocumentInventory(response);
      });
    } catch (error) {
      setDocumentInventory(null);
      setDocumentsError(formatApiError(error));
    } finally {
      setDocumentsLoading(false);
    }
  }

  async function handleDeleteDocument(document: IndexedDocumentResponse) {
    if (!apiKey.trim()) {
      setDocumentsError("Select the superuser key before deleting documents.");
      return;
    }

    const confirmed = window.confirm(
      `Delete ${document.source} from ${document.tenant_id}? This removes all indexed chunks for that document.`,
    );
    if (!confirmed) {
      return;
    }

    const target = `${document.tenant_id}:${document.doc_id}`;
    setDeleteTarget(target);
    setDocumentsError(null);
    setDocumentsNotice(null);

    try {
      const result = await deleteDocument(apiBaseUrl, apiKey.trim(), document.tenant_id, document.doc_id);
      setDocumentsNotice(`Deleted ${document.source} from ${result.tenant_id}.`);
      await refreshDocuments();
    } catch (error) {
      setDocumentsError(formatApiError(error));
    } finally {
      setDeleteTarget(null);
    }
  }

  const serviceStatuses = [
    {
      label: "API",
      value: health?.status === "ok" ? "Online" : health?.status ?? "unknown",
      tone: health?.status === "ok" ? "good" : "warn",
    },
    {
      label: "Qdrant",
      value: health?.qdrant === "ok" ? "Online" : health?.qdrant ?? "unknown",
      tone: health?.qdrant === "ok" ? "good" : "warn",
    },
    {
      label: "Generator",
      value: health?.generator === "configured" ? "Ready" : health?.generator ?? "unknown",
      tone: health?.generator === "configured" ? "good" : "warn",
    },
  ] as const;

  const resolvedTenant = sessionContext?.tenant_id ?? "";
  const accessStatusLabel = apiKey.trim()
    ? sessionContext?.role === "superuser"
      ? "Superuser"
      : resolvedTenant || (tenantError ? "Unverified" : "Run check")
    : "No key";
  const accessStatusTone = sessionContext ? "good" : "warn";
  const selectedKeyLabel =
    DEV_KEY_OPTIONS.find((option) => option.value === apiKey)?.label ??
    (apiKey.trim() ? "Custom" : "Missing");
  const isSuperuserSelected = apiKey === "superuser-dev-key";
  const activeTenant =
    sessionContext?.role === "tenant" && sessionContext.tenant_id
      ? sessionContext.tenant_id
      : inferTenantFromApiKey(apiKey);
  const exampleQuestions =
    resolvedTenant === "tenant_a"
      ? [
          "What is the VPN rule for internal dashboards?",
          'What should the Launchpad session banner show before opening the analytics cluster?',
          "How quickly must a Launchpad access incident be reported?",
        ]
      : resolvedTenant === "tenant_b"
        ? [
            "Who reviews refund exceptions?",
            "Which requests need director approval?",
            "What code is used for refund exception cases?",
          ]
        : [
            "What is the VPN rule for internal dashboards?",
            "Who reviews refund exceptions?",
            "What code is used for refund exception cases?",
          ];

  function renderTabContent() {
    switch (activeTab) {
      case "environment":
        return (
          <div className="tab-layout tab-layout-split">
            <section className="panel">
              <PanelHeading
                title="Environment"
                description="Set the API URL, choose an access key, and verify the connection."
              />

              <div className="stack">
                <label className="field">
                  <span>API base URL</span>
                  <input
                    value={apiBaseUrl}
                    onChange={(event) => setApiBaseUrl(event.target.value)}
                    placeholder="http://127.0.0.1:8000"
                  />
                </label>

                <div className="field">
                  <span>Access key</span>
                  <div className="key-selector">
                    {DEV_KEY_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={`key-choice ${apiKey === option.value ? "key-choice-active" : ""}`}
                        onClick={() => setApiKey(option.value)}
                      >
                        {option.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      className={`key-choice key-choice-clear ${!apiKey ? "key-choice-active" : ""}`}
                      onClick={() => setApiKey("")}
                    >
                      Clear
                    </button>
                  </div>
                </div>

                <div className="actions">
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => void refreshHealth()}
                    disabled={healthLoading}
                  >
                    {healthLoading ? "Checking..." : "Check status"}
                  </button>
                  <button type="button" onClick={() => setActiveTab("query")}>
                    Go to query
                  </button>
                </div>
              </div>

              {healthError ? <p className="feedback error">{healthError}</p> : null}
            </section>

            <section className="panel">
              <PanelHeading title="Service status" />

              <div className="status-panel">
                <div className="status-panel-header">
                  <span className="result-label">Current state</span>
                  {healthLoading ? <span className="status-note">Refreshing…</span> : null}
                </div>
                <div className="status-list">
                  <StatusRow
                    label="Resolved access"
                    value={
                      sessionContext?.role === "superuser"
                        ? "Superuser"
                        : resolvedTenant || (tenantError ? "Unverified" : "Not checked")
                    }
                    tone={sessionContext ? "good" : "warn"}
                  />
                  {serviceStatuses.map((item) => (
                    <StatusRow
                      key={item.label}
                      label={item.label}
                      value={item.value}
                      tone={item.tone}
                    />
                  ))}
                </div>
              </div>

              {tenantError ? <p className="feedback error">{tenantError}</p> : null}
            </section>
          </div>
        );

      case "workflow":
        return (
          <div className="tab-layout tab-layout-workflow">
            <section className="panel panel-wide">
              <PanelHeading title="Workflow" />
              <div className="workflow-grid">
                <WorkflowStep
                  number="01"
                  title="Check environment"
                  description="Confirm the API, tenant, Qdrant, and generator."
                />
                <WorkflowStep
                  number="02"
                  title="Run a query"
                  description="See whether the current index already answers the question."
                />
                <WorkflowStep
                  number="03"
                  title="Ingest if needed"
                  description="Add or refresh tenant content when the answer is missing or stale."
                />
                <WorkflowStep
                  number="04"
                  title="Query again"
                  description="Confirm the answer and citations after the update."
                />
                <WorkflowStep
                  number="05"
                  title="Review documents"
                  description="Use the Documents tab with the superuser key to inspect or delete indexed content."
                />
              </div>
            </section>

            <section className="panel">
              <PanelHeading title="Rules" />
              <ul className="detail-list">
                <li>Tenant scope always comes from <code>X-API-Key</code>.</li>
                <li>Answers should include citations.</li>
                <li>Tenant keys stay locked to their own tenant. Superuser can choose the ingest target.</li>
                <li>Document inventory and deletion require the superuser key.</li>
              </ul>
            </section>

            <section className="panel">
              <PanelHeading title="What to ask" />
              <ExampleQuestionList
                questions={exampleQuestions}
                onSelect={(value) => {
                  setQuestion(value);
                  setActiveTab("query");
                }}
              />
            </section>

            <section className="panel">
              <PanelHeading title="Next" />
              <div className="actions">
                <button type="button" onClick={() => setActiveTab("environment")}>
                  Open environment
                </button>
              </div>
            </section>
          </div>
        );

      case "ingest":
        return (
          <div className="tab-layout tab-layout-split">
            <section className="panel">
              <PanelHeading title="Document ingest" />

              <form className="stack" onSubmit={(event) => void handleIngest(event)}>
                <div className="field">
                  <span>Target tenant</span>
                  <div className="tenant-selector">
                    {TENANT_OPTIONS.map((option) => {
                      const isLocked = !isSuperuserSelected && activeTenant !== option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          className={`tenant-choice ${ingestTargetTenant === option.value ? "tenant-choice-active" : ""}`}
                          disabled={isLocked}
                          onClick={() => setIngestTargetTenant(option.value)}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                  <p className="field-note">
                    {isSuperuserSelected
                      ? "Superuser can switch the target tenant."
                      : `Locked to ${activeTenant ?? "the active tenant"}.`}
                  </p>
                </div>

                <label className="field">
                  <span>Source filename</span>
                  <input
                    value={ingestSource}
                    onChange={(event) => setIngestSource(event.target.value)}
                    placeholder="policy.md"
                  />
                </label>

                <label className="field">
                  <span>Document text</span>
                  <textarea
                    value={ingestText}
                    onChange={(event) => setIngestText(event.target.value)}
                    placeholder="Paste markdown or plain text here."
                    rows={10}
                  />
                </label>

                <div className="actions">
                  <button type="submit" disabled={ingestLoading}>
                    {ingestLoading ? "Ingesting..." : "Ingest document"}
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => setActiveTab("documents")}
                  >
                    Open documents
                  </button>
                </div>
              </form>

              {ingestError ? <p className="feedback error">{ingestError}</p> : null}
              {!ingestError && ingestResult ? (
                <p className="feedback success">
                  Indexed <strong>{ingestResult.source}</strong> for{" "}
                  <strong>{ingestResult.tenant_id}</strong> ({ingestResult.chunk_count} chunk
                  {ingestResult.chunk_count === 1 ? "" : "s"}).
                </p>
              ) : null}
            </section>

            <section className="panel">
              <PanelHeading title="Latest write" />

              {ingestResult ? (
                <div className="result-card">
                  <div>
                    <span className="result-label">Tenant</span>
                    <strong>
                      {TENANT_OPTIONS.find((option) => option.value === ingestResult.tenant_id)?.label ??
                        ingestResult.tenant_id}
                    </strong>
                  </div>
                  <div>
                    <span className="result-label">Document</span>
                    <strong>{ingestResult.doc_id}</strong>
                  </div>
                  <div>
                    <span className="result-label">Chunks indexed</span>
                    <strong>{ingestResult.chunk_count}</strong>
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <strong>No document indexed yet.</strong>
                  <p>Add a source name and document text.</p>
                </div>
              )}
            </section>
          </div>
        );

      case "documents":
        return (
          <div className="tab-layout tab-layout-documents">
            <section className="panel panel-wide">
              <PanelHeading
                title="Documents"
                description="Inventory and delete indexed documents across tenants."
              />

              <div className="documents-toolbar">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => void refreshDocuments()}
                  disabled={documentsLoading}
                >
                  {documentsLoading ? "Refreshing..." : "Refresh inventory"}
                </button>
              </div>

              {!isSuperuserSelected ? (
                <div className="empty-state">
                  <strong>Superuser key required.</strong>
                  <p>Select Superuser in Environment to view all indexed documents.</p>
                </div>
              ) : documentInventory?.documents.length ? (
                <div className="documents-list">
                  {documentInventory.documents.map((document) => {
                    const target = `${document.tenant_id}:${document.doc_id}`;
                    return (
                      <div className="document-card" key={target}>
                        <div className="document-card-header">
                          <div>
                            <strong>{document.source}</strong>
                            <p>{document.doc_id}</p>
                          </div>
                          <button
                            type="button"
                            className="button-secondary button-danger"
                            disabled={deleteTarget === target}
                            onClick={() => void handleDeleteDocument(document)}
                          >
                            {deleteTarget === target ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                        <div className="document-meta">
                          <DocumentMetaItem label="Tenant" value={document.tenant_id} />
                          <DocumentMetaItem label="Access" value={`${document.accessible_by[0]} only`} />
                          <DocumentMetaItem label="Chunks" value={String(document.chunk_count)} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <strong>No indexed documents found.</strong>
                  <p>Refresh the inventory after ingesting content.</p>
                </div>
              )}

              {documentsError ? <p className="feedback error">{documentsError}</p> : null}
              {documentsNotice ? <p className="feedback success">{documentsNotice}</p> : null}
            </section>

            <section className="panel">
              <PanelHeading title="Inventory summary" />
              <div className="result-card">
                <div>
                  <span className="result-label">Documents</span>
                  <strong>{documentInventory?.total_documents ?? 0}</strong>
                </div>
                <div>
                  <span className="result-label">Chunks</span>
                  <strong>{documentInventory?.total_chunks ?? 0}</strong>
                </div>
                <div>
                  <span className="result-label">Access</span>
                  <strong>{isSuperuserSelected ? "Superuser" : "Tenant key"}</strong>
                </div>
              </div>
            </section>
          </div>
        );

      case "query":
        return (
          <div className="tab-layout tab-layout-query">
            <section className="panel panel-wide">
              <PanelHeading title="Query" />

              <form className="stack" onSubmit={(event) => void handleQuery(event)}>
                <label className="field">
                  <span>Question</span>
                  <textarea
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="How do analysts use VPN for internal dashboards?"
                    rows={6}
                  />
                </label>

                <div className="query-controls">
                  <label className="field field-compact">
                    <span>Top K</span>
                    <input
                      value={topK}
                      onChange={(event) => setTopK(event.target.value)}
                      inputMode="numeric"
                      placeholder="3"
                    />
                  </label>

                  <div className="actions">
                    <button type="submit" disabled={queryLoading || isSuperuserSelected}>
                      {queryLoading ? "Querying..." : "Run query"}
                    </button>
                  </div>
                </div>
              </form>

              {isSuperuserSelected ? (
                <p className="feedback warn">Switch to Tenant A or Tenant B to query tenant content.</p>
              ) : null}
              {queryError ? <p className="feedback error">{queryError}</p> : null}
            </section>

            <section className="panel">
              <PanelHeading title="Suggested questions" />
              <ExampleQuestionList
                questions={exampleQuestions}
                onSelect={(value) => setQuestion(value)}
              />
            </section>

            <section className="panel">
              <PanelHeading title="Answer" />
              <div className="answer-copy">
                <p>
                  {queryResult?.answer ?? "The answer will appear here."}
                </p>
              </div>
            </section>

            <section className="panel">
              <PanelHeading title="Citations" />
              <div className="citations">
                {queryResult?.citations.length ? (
                  <ul>
                    {queryResult.citations.map((citation) => (
                      <CitationItem
                        key={`${citation.source}:${citation.chunk_id}`}
                        citation={citation}
                        apiBaseUrl={apiBaseUrl}
                        apiKey={apiKey.trim()}
                        tenantId={activeTenantId}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="muted">No citations yet.</p>
                )}
              </div>
            </section>
          </div>
        );
    }
  }

  return (
    <div className="shell">
      <header className="masthead">
        <div className="brand-block">
          <p className="eyebrow">Operations Console</p>
          <h1>CiteShield</h1>
          <p className="lede">
            Manage tenant-scoped content and review cited answers from one console.
          </p>
        </div>
        <div className="signal-row signal-row-single">
          <div className="signal-card">
            <span className="signal-label">Auth model</span>
            <strong>The backend resolves tenant scope from the <code>X-API-Key</code> header.</strong>
          </div>
        </div>
      </header>

      <section className="summary-strip">
        <SummaryCard label="API endpoint" value={apiBaseUrl} />
        <SummaryCard
          label="Key"
          value={selectedKeyLabel}
          tone={apiKey.trim() ? "good" : "warn"}
        />
        <SummaryCard
          label="Access"
          value={accessStatusLabel}
          tone={accessStatusTone}
        />
        <SummaryCard label="Section" value={STEP_TABS.find((tab) => tab.id === activeTab)?.label ?? ""} />
        <div className="summary-card summary-health-card">
          <span className="summary-label">Services</span>
          <div className="summary-health-list">
            {serviceStatuses.map((item) => (
              <HealthBadge
                key={item.label}
                label={item.label}
                value={item.value}
                tone={item.tone}
              />
            ))}
          </div>
        </div>
      </section>

      <section className="workspace-shell">
        <nav className="step-tabs" aria-label="Workspace sections">
          {STEP_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`step-tab ${tab.id === activeTab ? "step-tab-active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="step-tab-step">{tab.step}</span>
              <span className="step-tab-copy">
                <strong>{tab.label}</strong>
                <small>{tab.helper}</small>
              </span>
            </button>
          ))}
        </nav>

        <section className="workspace-panel">{renderTabContent()}</section>
      </section>
    </div>
  );
}

type PanelHeadingProps = {
  title: string;
  description?: string;
};

function PanelHeading({ title, description }: PanelHeadingProps) {
  return (
    <div className="panel-heading">
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
    </div>
  );
}

type SummaryCardProps = {
  label: string;
  value: string;
  tone?: "good" | "warn";
};

function SummaryCard({ label, value, tone }: SummaryCardProps) {
  return (
    <div className="summary-card">
      <span className="summary-label">{label}</span>
      <strong className={`summary-value ${tone ? `summary-value-${tone}` : ""}`}>{value}</strong>
    </div>
  );
}

type HealthBadgeProps = {
  label: string;
  value: string;
  tone: "good" | "warn";
};

function HealthBadge({ label, value, tone }: HealthBadgeProps) {
  return (
    <div className={`health-badge health-badge-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

type StatusRowProps = {
  label: string;
  value: string;
  tone: "good" | "warn";
};

function StatusRow({ label, value, tone }: StatusRowProps) {
  return (
    <div className="status-row">
      <div className="status-row-copy">
        <span>{label}</span>
      </div>
      <span className={`status-chip status-chip-${tone}`}>{value}</span>
    </div>
  );
}

type WorkflowStepProps = {
  number: string;
  title: string;
  description: string;
};

function WorkflowStep({ number, title, description }: WorkflowStepProps) {
  return (
    <div className="workflow-step">
      <span className="workflow-number">{number}</span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}

function DocumentMetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="document-meta-item">
      <span className="result-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

type ExampleQuestionListProps = {
  questions: string[];
  onSelect: (value: string) => void;
};

function ExampleQuestionList({ questions, onSelect }: ExampleQuestionListProps) {
  return (
    <div className="example-list">
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          className="example-item"
          onClick={() => onSelect(question)}
        >
          {question}
        </button>
      ))}
    </div>
  );
}

function CitationItem({
  citation,
  apiBaseUrl,
  apiKey,
  tenantId,
}: {
  citation: CitationResponse;
  apiBaseUrl: string;
  apiKey: string;
  tenantId: string | null;
}) {
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);

  useEffect(() => {
    if (!citation.media_path || !citation.modality || !tenantId || !apiKey) {
      setMediaUrl(null);
      setMediaError(null);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;
    setMediaError(null);

    void getMediaBlob(apiBaseUrl, apiKey, tenantId, citation.media_path)
      .then((blob) => {
        if (cancelled) {
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setMediaUrl(objectUrl);
      })
      .catch((error) => {
        if (!cancelled) {
          setMediaUrl(null);
          setMediaError(formatApiError(error));
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [apiBaseUrl, apiKey, citation.media_path, citation.modality, tenantId]);

  return (
    <li className="citation-item">
      <div className="citation-heading">
        <strong>{citation.source}</strong>
        <span className="modality-chip">{getCitationMediaLabel(citation)}</span>
      </div>
      <span>Chunk {citation.chunk_id + 1}</span>
      {citation.media_path ? <span>Media: {citation.media_path}</span> : null}
      {citation.source_url ? <span>Source: {citation.source_url}</span> : null}
      {mediaError ? <p className="media-error">{mediaError}</p> : null}
      {mediaUrl && citation.modality === "image" ? (
        <img className="citation-media citation-media-image" src={mediaUrl} alt={citation.source} />
      ) : null}
      {mediaUrl && citation.modality === "audio" ? (
        <audio className="citation-media" controls src={mediaUrl} />
      ) : null}
      {mediaUrl && citation.modality === "video" ? (
        <video className="citation-media" controls src={mediaUrl} />
      ) : null}
    </li>
  );
}

export default App;
