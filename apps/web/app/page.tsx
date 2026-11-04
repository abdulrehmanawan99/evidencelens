"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  friendlyError,
  type Collection,
  type Document,
  type Finding,
  type Investigation,
  type Job,
  type Page,
  type Provider,
  type RunSummary,
  type Source,
} from "@/lib/api";

const defaultClaim = "Harbor Transit recorded 1.20 million journeys in Q2.";
const running = (state?: string) => state === "queued" || state === "running";
const readable = (value: string) => value.replaceAll("_", " ");

function Icon({
  name,
  size = 18,
}: {
  name:
    | "plus"
    | "arrow"
    | "file"
    | "upload"
    | "check"
    | "close"
    | "download"
    | "search"
    | "book"
    | "trash"
    | "external";
  size?: number;
}) {
  const paths = {
    plus: "M12 5v14M5 12h14",
    arrow: "M5 12h14m-5-5 5 5-5 5",
    file: "M14 3H6a1 1 0 0 0-1 1v16h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6",
    upload: "M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5",
    check: "m5 12 4 4L19 6",
    close: "m6 6 12 12M6 18 18 6",
    download: "M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4",
    search: "m16 16 5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
    book: "M12 5v16M3 3l9 2 9-2v16l-9 2-9-2V3Z",
    trash: "M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7",
    external: "M14 3h7v7m0-7L11 13M10 3H3v18h18v-7",
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}

function LensMark() {
  return (
    <svg
      width="34"
      height="34"
      viewBox="0 0 36 36"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="15" cy="15" r="10" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="15" cy="15" r="5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="m23 23 9 9M15 1v5M1 15h5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

export default function ReadingRoom() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionCursor, setCollectionCursor] = useState<string | null>(null);
  const [activeId, setActiveId] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [historyCursor, setHistoryCursor] = useState<string | null>(null);
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<Investigation | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [highlight, setHighlight] = useState<Finding | null>(null);
  const [claim, setClaim] = useState(defaultClaim);
  const [provider, setProvider] = useState<Provider | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [partial, setPartial] = useState(false);
  const [tab, setTab] = useState<"evidence" | "sources">("evidence");
  const [pendingDelete, setPendingDelete] = useState<{
    type: "document" | "collection";
    id: string;
    title: string;
  } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const selected = useRef({ activeId, runId });
  selected.current = { activeId, runId };
  const active = collections.find((c) => c.id === activeId);
  const ready = documents.filter((d) => d.state === "ready").length;
  const activeJobs = documents.filter((d) => running(d.state));

  const refreshCollections = useCallback(async () => {
    const result = await api<Page<Collection>>("/collections?limit=100");
    setCollections(result.items);
    setCollectionCursor(result.next_cursor);
  }, []);

  const refreshRoom = useCallback(async (id: string) => {
    const [docs, runs, collection] = await Promise.all([
      api<Page<Document>>(`/collections/${id}/documents`),
      api<Page<RunSummary>>(`/collections/${id}/investigations`),
      api<Collection>(`/collections/${id}`),
    ]);
    if (selected.current.activeId !== id) return;
    setDocuments(docs.items);
    setHistory(runs.items);
    setHistoryCursor(runs.next_cursor);
    setCollections((list) => list.map((c) => (c.id === id ? collection : c)));
  }, []);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api<Page<Collection>>("/collections?limit=100"),
      api<Provider>("/provider-status"),
    ])
      .then(([list, status]) => {
        if (!alive) return;
        setCollections(list.items);
        setCollectionCursor(list.next_cursor);
        setProvider(status);
        const id = new URLSearchParams(window.location.search).get(
          "collection",
        );
        setActiveId(
          list.items.find((c) => c.id === id)?.id || list.items[0]?.id || "",
        );
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setInitializing(false));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    setDocuments([]);
    setHistory([]);
    setRunId("");
    setRun(null);
    setSource(null);
    setHighlight(null);
    setPartial(false);
    if (!activeId) return;
    let alive = true;
    const load = () =>
      refreshRoom(activeId).catch((e) => alive && setError(e.message));
    void load();
    const timer = setInterval(load, 1500);
    const params = new URLSearchParams(window.location.search);
    if (params.get("collection") === activeId && params.get("document")) {
      const passage = params.get("passage");
      api<Source>(
        `/documents/${params.get("document")}/source${passage ? `?passage_id=${passage}` : ""}`,
      )
        .then((data) => {
          if (alive) {
            setSource(data);
            setTab("sources");
          }
        })
        .catch((e) => alive && setError(e.message));
    }
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [activeId, refreshRoom]);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    let alive = true;
    const load = () =>
      api<Investigation>(`/investigations/${runId}`)
        .then((data) => {
          if (alive) setRun(data);
        })
        .catch((e) => alive && setError(e.message));
    void load();
    const timer = setInterval(load, 1200);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [runId]);

  useEffect(() => {
    if (pendingDelete) dialog.current?.showModal();
    else dialog.current?.close();
  }, [pendingDelete]);

  async function act(name: string, fn: () => Promise<void>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Something went wrong. Please retry.",
      );
    } finally {
      setBusy("");
    }
  }

  async function loadSample() {
    await act("sample", async () => {
      const collection = await api<Collection>("/sample", { method: "POST" });
      await refreshCollections();
      setActiveId(collection.id);
      setClaim(defaultClaim);
      setNotice(
        "Four original synthetic reports added. The worker is preparing their passages.",
      );
    });
  }

  async function createCollection(event: React.FormEvent) {
    event.preventDefault();
    await act("create", async () => {
      const collection = await api<Collection>("/collections", {
        method: "POST",
        body: JSON.stringify({ title: newTitle }),
      });
      await refreshCollections();
      setActiveId(collection.id);
      setNewTitle("");
      setShowCreate(false);
    });
  }

  async function uploadFiles(files: FileList | null) {
    if (!files?.length || !activeId) return;
    const id = activeId;
    await act("upload", async () => {
      let uploaded = 0;
      for (const file of Array.from(files)) {
        if (!file.name.toLowerCase().endsWith(".txt"))
          throw new Error(
            "Choose a UTF-8 .txt file. PDF support is a later milestone.",
          );
        if (file.size > (provider?.max_upload_bytes || 2097152))
          throw new Error("Each text file must be 2 MiB or smaller.");
        await api(`/collections/${id}/documents`, {
          method: "POST",
          body: file,
          headers: {
            "Content-Type": "text/plain",
            "X-Filename": encodeURIComponent(file.name),
          },
        });
        uploaded++;
      }
      await refreshRoom(id);
      setNotice(
        `${uploaded} source${uploaded === 1 ? "" : "s"} uploaded. You can read them when ingestion finishes. Custom-source AI analysis is not connected yet.`,
      );
    });
    if (uploadInput.current) uploadInput.current.value = "";
  }

  async function investigate(event: React.FormEvent) {
    event.preventDefault();
    await act("investigate", async () => {
      const result = await api<{ id: string }>(
        `/collections/${activeId}/investigations`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ claim, allow_partial: partial }),
        },
      );
      setRun(null);
      setRunId(result.id);
      setTab("evidence");
      await refreshRoom(activeId);
    });
  }

  async function inspect(docId: string, finding?: Finding) {
    await act("source", async () => {
      const data = await api<Source>(
        `/documents/${docId}/source${finding ? `?passage_id=${finding.passage_id}` : ""}`,
      );
      if (data.document.collection_id !== selected.current.activeId) return;
      setSource(data);
      setHighlight(finding || null);
      setTab("sources");
    });
  }

  async function saveReview(
    finding: Finding,
    decision: "accepted" | "dismissed" | "unreviewed",
    note = finding.note,
  ) {
    await act(`review-${finding.id}`, async () => {
      const result = await api<Investigation>(
        `/findings/${finding.id}/review`,
        {
          method: "PUT",
          body: JSON.stringify({
            decision,
            note,
            expected_revision: finding.revision,
          }),
        },
      );
      if (result.id === selected.current.runId) setRun(result);
    });
  }

  async function download(draft: boolean) {
    if (!run) return;
    await act("export", async () => {
      const response = await fetch(
        `/api/v1/investigations/${run.id}/export?expected_revision=${run.review_revision}&draft=${draft}`,
      );
      if (!response.ok) {
        const data = await response.json();
        throw new Error(
          data.detail?.message || "The export could not be generated.",
        );
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `evidencelens-${run.id.slice(0, 8)}-r${run.review_revision}.md`;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(
        draft
          ? "Draft brief downloaded. Unreviewed evidence is labeled."
          : "Reviewed brief downloaded with source excerpts and provenance.",
      );
    });
  }

  async function remove() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    await act("delete", async () => {
      const job = await api<Job>(
        `/${target.type === "collection" ? "collections" : "documents"}/${target.id}`,
        { method: "DELETE" },
      );
      setPendingDelete(null);
      setSource(null);
      setHighlight(null);
      if (target.type === "collection") {
        setActiveId("");
        await refreshCollections();
      } else await refreshRoom(activeId);
      setNotice(
        `Access revoked. Cleanup job ${job.id.slice(0, 8)} is removing stored text and derived evidence.`,
      );
    });
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to reading room
      </a>
      <header className="app-header">
        <a className="brand" href="/" aria-label="EvidenceLens home">
          <LensMark />
          <span>
            Evidence<span className="brand-light">Lens</span>
            <small>A CLEARER VIEW OF THE EVIDENCE</small>
          </span>
        </a>
        <div className="header-right">
          <span className="local-indicator">
            <i /> Private local workspace
          </span>
          <span className="header-separator" />
          <span className="mode-tag">FIXTURE MODE</span>
          <button
            className="icon-button"
            aria-label="Show fixture limitations"
            title="About fixture mode"
            onClick={() =>
              setNotice(
                provider?.message ||
                  "Predefined synthetic scenarios. No live model is connected.",
              )
            }
          >
            <Icon name="book" />
          </button>
        </div>
      </header>
      <div className="app-shell">
        <aside className="library" aria-label="Collection library">
          <div className="library-title">
            <span className="eyebrow">YOUR LIBRARY</span>
            <button
              className="icon-button"
              aria-label="Create collection"
              onClick={() => setShowCreate(!showCreate)}
            >
              <Icon name="plus" />
            </button>
          </div>
          {showCreate && (
            <form className="create-form" onSubmit={createCollection}>
              <label htmlFor="collection-title">Collection title</label>
              <input
                id="collection-title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                maxLength={160}
                required
                autoFocus
                placeholder="e.g. Quarterly reports"
              />
              <button className="button small primary" disabled={!!busy}>
                Create collection
              </button>
            </form>
          )}
          <nav className="collection-list" aria-label="Collections">
            {collections.map((collection, index) => (
              <button
                key={collection.id}
                className={`collection-item ${collection.id === activeId ? "selected" : ""}`}
                onClick={() => {
                  setActiveId(collection.id);
                  setError("");
                }}
                aria-current={collection.id === activeId ? "page" : undefined}
              >
                <span className="collection-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span>
                  <strong>{collection.title}</strong>
                  <small>
                    {collection.document_count} sources <span>·</span>{" "}
                    {collection.ready_count} ready
                  </small>
                </span>
              </button>
            ))}
          </nav>
          {collectionCursor && (
            <button
              className="text-button"
              onClick={() =>
                act("more", async () => {
                  const data = await api<Page<Collection>>(
                    `/collections?limit=100&cursor=${encodeURIComponent(collectionCursor)}`,
                  );
                  setCollections((list) => [...list, ...data.items]);
                  setCollectionCursor(data.next_cursor);
                })
              }
            >
              More collections
            </button>
          )}
          {!collections.length && !initializing && (
            <p className="library-empty">
              Your investigations begin with a collection of sources.
            </p>
          )}
          <button
            className="new-collection"
            onClick={() => setShowCreate(true)}
          >
            <Icon name="plus" size={16} /> New collection
          </button>
          <div className="sample-note">
            <span className="eyebrow">START WITH A QUESTION</span>
            <p>
              Four reports.
              <br />
              Two different totals.
              <br />
              One claim to investigate.
            </p>
            <button
              className="text-button"
              disabled={!!busy}
              onClick={loadSample}
            >
              {busy === "sample"
                ? "Preparing reports…"
                : "Open sample collection"}
              <Icon name="arrow" size={15} />
            </button>
          </div>
          <div className="library-footer">
            <span className="tiny-lens">EL</span>
            <div>
              Local by design<small>Sources stay in this installation.</small>
            </div>
          </div>
        </aside>

        <main id="main" className="room">
          {error && (
            <div className="alert error" role="alert">
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert" role="status">
              <span>{notice}</span>
              <button
                className="icon-button"
                aria-label="Dismiss notice"
                onClick={() => setNotice("")}
              >
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          {initializing ? (
            <div className="welcome">
              <span className="eyebrow">OPENING YOUR LIBRARY</span>
              <h1>Preparing the reading room…</h1>
            </div>
          ) : !active ? (
            <section className="welcome">
              <span className="eyebrow">READ CLOSELY. THINK CLEARLY.</span>
              <h1>
                Every claim
                <br />
                deserves a source.
              </h1>
              <p>
                Bring the reports together. Find where they agree, examine where
                they don’t, and leave with a brief you can trace back to the
                evidence.
              </p>
              <div className="welcome-actions">
                <button
                  className="button primary"
                  disabled={!!busy}
                  onClick={loadSample}
                >
                  Explore the sample <Icon name="arrow" />
                </button>
                <button className="button" onClick={() => setShowCreate(true)}>
                  Create a collection
                </button>
              </div>
              <div className="welcome-method">
                <div>
                  <span>01</span>
                  <strong>Gather the sources</strong>
                  <p>Original documents, preserved with context.</p>
                </div>
                <div>
                  <span>02</span>
                  <strong>Follow the evidence</strong>
                  <p>Compare passages behind a specific claim.</p>
                </div>
                <div>
                  <span>03</span>
                  <strong>Make your judgment</strong>
                  <p>Review findings and export a cited brief.</p>
                </div>
              </div>
              <p className="fixture-footnote">
                Current build: UTF-8 text uploads and predefined sample
                analysis. PDF and live model support are upcoming.
              </p>
            </section>
          ) : (
            <>
              <div className="room-heading">
                <div>
                  <div className="breadcrumb">
                    LIBRARY <span>/</span> COLLECTION{" "}
                    {String(
                      collections.findIndex((c) => c.id === activeId) + 1,
                    ).padStart(2, "0")}
                  </div>
                  <h1>{active.title}</h1>
                  <p>
                    A reading room for claims, context, and conflicting
                    evidence.
                  </p>
                </div>
                <button
                  className="icon-button subdued"
                  aria-label="Delete collection"
                  onClick={() =>
                    setPendingDelete({
                      type: "collection",
                      id: active.id,
                      title: active.title,
                    })
                  }
                >
                  <Icon name="trash" />
                </button>
              </div>
              <section className="claim-desk" aria-label="Investigate a claim">
                <div className="section-label">
                  <span className="eyebrow">THE QUESTION ON YOUR DESK</span>
                  <span className="micro-label">
                    {ready} OF {documents.length} SOURCES READY
                  </span>
                </div>
                <form onSubmit={investigate}>
                  <label className="sr-only" htmlFor="claim">
                    Claim to investigate
                  </label>
                  <textarea
                    id="claim"
                    value={claim}
                    onChange={(e) => setClaim(e.target.value)}
                    maxLength={2000}
                    rows={2}
                    required
                    placeholder="What claim would you like to investigate?"
                  />
                  <div className="claim-actions">
                    <span>
                      <span className="tiny-dot" />
                      Source-backed analysis · fixture demonstration
                    </span>
                    <button
                      className="button primary"
                      disabled={
                        !!busy ||
                        !ready ||
                        (ready < documents.length && !partial)
                      }
                    >
                      {busy === "investigate"
                        ? "Starting…"
                        : "Investigate claim"}
                      <Icon name="arrow" size={17} />
                    </button>
                  </div>
                </form>
                {ready < documents.length && (
                  <label className="partial-choice">
                    <input
                      type="checkbox"
                      checked={partial}
                      onChange={(e) => setPartial(e.target.checked)}
                    />
                    Analyze ready sources only; record the excluded files.
                  </label>
                )}
                <details className="claim-examples">
                  <summary>Sample claims supported in fixture mode</summary>
                  <div>
                    {(provider?.supported_claims || [defaultClaim]).map((c) => (
                      <button key={c} onClick={() => setClaim(c)}>
                        {c}
                        <Icon name="arrow" size={13} />
                      </button>
                    ))}
                  </div>
                  <p>
                    Custom files can be uploaded and read. Custom claim analysis
                    requires a future live provider.
                  </p>
                </details>
              </section>

              <div className="workspace-tabs">
                <div role="tablist" aria-label="Workspace view">
                  <button
                    role="tab"
                    id="evidence-tab"
                    aria-selected={tab === "evidence"}
                    aria-controls="evidence-panel"
                    onClick={() => setTab("evidence")}
                  >
                    Evidence board <span>{run?.findings.length || "—"}</span>
                  </button>
                  <button
                    role="tab"
                    id="sources-tab"
                    aria-selected={tab === "sources"}
                    aria-controls="sources-panel"
                    onClick={() => setTab("sources")}
                  >
                    Source reader <span>{documents.length}</span>
                  </button>
                </div>
                <button
                  className="button small"
                  disabled={!!busy || documents.length >= 25}
                  onClick={() => uploadInput.current?.click()}
                >
                  <Icon name="upload" size={15} />
                  {busy === "upload" ? "Uploading…" : "Add sources"}
                </button>
                <input
                  ref={uploadInput}
                  type="file"
                  accept=".txt,text/plain"
                  multiple
                  className="sr-only"
                  aria-label="Upload UTF-8 text sources"
                  onChange={(e) => uploadFiles(e.target.files)}
                />
              </div>

              {tab === "evidence" ? (
                <section
                  id="evidence-panel"
                  role="tabpanel"
                  aria-labelledby="evidence-tab"
                  className="evidence-layout"
                >
                  <div className="evidence-main">
                    {!run ? (
                      <div className="board-empty">
                        <div className="empty-lens">
                          <Icon name="search" size={28} />
                        </div>
                        <span className="eyebrow">LET THE SOURCES SPEAK</span>
                        <h2>Your evidence belongs here.</h2>
                        <p>
                          Investigate the claim above to compare supporting
                          passages, possible conflicts, and the context between
                          them.
                        </p>
                        <div className="evidence-legend">
                          <span>
                            <i className="support" />
                            Supports
                          </span>
                          <span>
                            <i className="conflict" />
                            Conflicts
                          </span>
                          <span>
                            <i className="context" />
                            Context
                          </span>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="result-heading">
                          <div>
                            <span className="eyebrow">
                              INVESTIGATION / {run.id.slice(0, 8).toUpperCase()}
                            </span>
                            <h2>
                              {running(run.job.state)
                                ? "Following the evidence…"
                                : run.job.state === "failed"
                                  ? "Investigation needs attention"
                                  : run.job.state === "cancelled"
                                    ? "Investigation cancelled"
                                    : readable(run.outcome || "Result pending")}
                            </h2>
                          </div>
                          <span className="status-label" aria-live="polite">
                            {running(run.job.state) && (
                              <span className="spinner" />
                            )}
                            {readable(run.job.state)}
                          </span>
                        </div>
                        <p className="investigated-claim">“{run.claim}”</p>
                        {run.stale && (
                          <div className="inline-warning">
                            The source collection changed. This result is
                            retained for reference; start a new investigation to
                            review or export.
                          </div>
                        )}
                        {run.excluded_sources.length > 0 && (
                          <div className="inline-warning">
                            Partial coverage:{" "}
                            {run.excluded_sources
                              .map((s) => String(s.title))
                              .join(", ")}{" "}
                            excluded.
                          </div>
                        )}
                        {running(run.job.state) && (
                          <div className="job-progress">
                            <span className="eyebrow">
                              {readable(run.job.stage)}
                            </span>
                            <p>
                              Results are saved by the background worker. You
                              can return to this investigation later.
                            </p>
                            <button
                              className="text-button"
                              disabled={!!busy}
                              onClick={() =>
                                act("cancel", async () => {
                                  await api(`/jobs/${run.job.id}/cancel`, {
                                    method: "POST",
                                  });
                                  setNotice("Cancellation requested.");
                                })
                              }
                            >
                              Cancel investigation
                            </button>
                          </div>
                        )}
                        {run.job.state === "failed" && (
                          <div className="inline-warning">
                            {friendlyError(run.job.error_code)}
                          </div>
                        )}
                        {run.outcome === "insufficient_evidence" && (
                          <div className="insufficient">
                            <Icon name="search" size={25} />
                            <h3>
                              The selected sources don’t establish this claim.
                            </h3>
                            <p>
                              Absence of evidence is not evidence that the claim
                              is false. Try a supported sample claim or inspect
                              the source reports.
                            </p>
                          </div>
                        )}
                        {(["supports", "conflicts", "context"] as const).map(
                          (relation) => {
                            const findings = run.findings.filter(
                              (f) => f.relation === relation,
                            );
                            return findings.length ? (
                              <div
                                key={relation}
                                className={`evidence-group ${relation}`}
                              >
                                <div className="group-label">
                                  <span>
                                    {relation === "supports"
                                      ? "SUPPORTING EVIDENCE"
                                      : relation === "conflicts"
                                        ? "CANDIDATE CONFLICTS"
                                        : "CONTEXT & QUALIFICATIONS"}
                                  </span>
                                  <span>
                                    {String(findings.length).padStart(2, "0")}
                                  </span>
                                </div>
                                {findings.map((finding) => (
                                  <FindingCard
                                    key={`${finding.id}-${finding.revision}`}
                                    finding={finding}
                                    disabled={!!busy || run.stale}
                                    inspect={() =>
                                      inspect(finding.document_id, finding)
                                    }
                                    review={(decision, note) =>
                                      saveReview(finding, decision, note)
                                    }
                                  />
                                ))}
                              </div>
                            ) : null;
                          },
                        )}
                        {run.limitations && (
                          <p className="analysis-limitations">
                            <strong>A note on this result</strong>
                            {run.limitations}
                          </p>
                        )}
                      </>
                    )}
                  </div>
                  <aside className="investigation-aside">
                    <div className="aside-section">
                      <span className="eyebrow">THE SOURCE COLLECTION</span>
                      <div className="source-tally">
                        <strong>{String(ready).padStart(2, "0")}</strong>
                        <span>
                          ready to read
                          <br />
                          of {documents.length} documents
                        </span>
                      </div>
                      <div className="mini-sources">
                        {documents.map((doc, index) => (
                          <button
                            key={doc.id}
                            onClick={() => inspect(doc.id)}
                            disabled={doc.state !== "ready"}
                          >
                            <span>{String(index + 1).padStart(2, "0")}</span>
                            <strong>{doc.title.replace(".txt", "")}</strong>
                            <i
                              className={
                                doc.state === "ready"
                                  ? "ready-dot"
                                  : "pending-dot"
                              }
                            />
                          </button>
                        ))}
                      </div>
                      {!documents.length && (
                        <p className="aside-copy">
                          Add a text report or open the sample collection to
                          begin.
                        </p>
                      )}
                      {activeJobs.length > 0 && (
                        <p className="aside-copy" role="status">
                          Preparing {activeJobs.length} source
                          {activeJobs.length > 1 ? "s" : ""}…
                        </p>
                      )}
                    </div>
                    {run?.job.state === "succeeded" && (
                      <div className="aside-section export-section">
                        <span className="eyebrow">FROM EVIDENCE TO BRIEF</span>
                        <h3>Keep the context.</h3>
                        <p>
                          {
                            run.findings.filter(
                              (f) => f.decision === "accepted",
                            ).length
                          }{" "}
                          accepted ·{" "}
                          {
                            run.findings.filter(
                              (f) => f.decision === "unreviewed",
                            ).length
                          }{" "}
                          awaiting review
                        </p>
                        <button
                          className="button primary full"
                          disabled={
                            !!busy ||
                            run.stale ||
                            !run.findings.some((f) => f.decision === "accepted")
                          }
                          onClick={() => download(false)}
                        >
                          <Icon name="download" size={16} /> Export reviewed
                          brief
                        </button>
                        <button
                          className="text-button"
                          disabled={!!busy || run.stale}
                          onClick={() => download(true)}
                        >
                          Download a labeled draft
                          <Icon name="arrow" size={14} />
                        </button>
                        <small>
                          Markdown with exact excerpts, source hashes, and
                          review provenance.
                        </small>
                      </div>
                    )}
                    <div className="aside-section history">
                      <span className="eyebrow">INVESTIGATION HISTORY</span>
                      {history.length ? (
                        history.map((item) => (
                          <button
                            key={item.id}
                            className={item.id === runId ? "current" : ""}
                            onClick={() => {
                              setRun(null);
                              setRunId(item.id);
                            }}
                          >
                            <span>
                              {new Date(item.created_at).toLocaleTimeString(
                                [],
                                { hour: "2-digit", minute: "2-digit" },
                              )}
                              {item.stale ? " · SOURCES CHANGED" : ""}
                            </span>
                            <strong>{item.claim}</strong>
                            <Icon name="arrow" size={13} />
                          </button>
                        ))
                      ) : (
                        <p className="aside-copy">
                          Your investigations will be saved here.
                        </p>
                      )}
                      {historyCursor && (
                        <button
                          className="text-button"
                          onClick={() =>
                            act("history", async () => {
                              const page = await api<Page<RunSummary>>(
                                `/collections/${activeId}/investigations?cursor=${encodeURIComponent(historyCursor)}`,
                              );
                              setHistory((list) => [...list, ...page.items]);
                              setHistoryCursor(page.next_cursor);
                            })
                          }
                        >
                          Load older investigations
                        </button>
                      )}
                    </div>
                  </aside>
                </section>
              ) : (
                <section
                  id="sources-panel"
                  role="tabpanel"
                  aria-labelledby="sources-tab"
                  className="source-layout"
                >
                  <aside className="source-navigation">
                    <span className="eyebrow">
                      DOCUMENTS / {documents.length}
                    </span>
                    {documents.map((doc, index) => (
                      <div
                        className={`document-row ${source?.document.id === doc.id ? "selected" : ""}`}
                        key={doc.id}
                      >
                        <button
                          className="document-open"
                          onClick={() => inspect(doc.id)}
                          disabled={doc.state !== "ready"}
                        >
                          <Icon name="file" />
                          <span>
                            <strong>{doc.title}</strong>
                            <small>
                              {readable(doc.state)} ·{" "}
                              {(doc.size / 1024).toFixed(1)} KB
                            </small>
                          </span>
                          <span className="doc-index">
                            {String(index + 1).padStart(2, "0")}
                          </span>
                        </button>
                        <div className="document-tools">
                          {running(doc.state) && doc.job_id && (
                            <button
                              onClick={() =>
                                act("cancel", async () => {
                                  await api(`/jobs/${doc.job_id}/cancel`, {
                                    method: "POST",
                                  });
                                  await refreshRoom(activeId);
                                })
                              }
                            >
                              Cancel
                            </button>
                          )}
                          {["failed", "cancelled"].includes(doc.state) && (
                            <button
                              onClick={() =>
                                act("retry", async () => {
                                  await api(`/documents/${doc.id}/retry`, {
                                    method: "POST",
                                  });
                                  await refreshRoom(activeId);
                                })
                              }
                            >
                              Retry ingestion
                            </button>
                          )}
                          <button
                            aria-label={`Remove ${doc.title}`}
                            onClick={() =>
                              setPendingDelete({
                                type: "document",
                                id: doc.id,
                                title: doc.title,
                              })
                            }
                          >
                            Remove
                          </button>
                        </div>
                        {doc.error_code && (
                          <p className="document-error">
                            {friendlyError(doc.error_code)}
                          </p>
                        )}
                      </div>
                    ))}
                    <button
                      className="upload-zone"
                      disabled={!!busy}
                      onClick={() => uploadInput.current?.click()}
                    >
                      <Icon name="upload" size={22} />
                      <strong>Add a source</strong>
                      <span>UTF-8 .txt · up to 2 MiB</span>
                    </button>
                  </aside>
                  <div className="source-paper">
                    {source ? (
                      <>
                        <div className="paper-topline">
                          <span>ORIGINAL EXTRACTED TEXT</span>
                          <span>UTF-8 / IMMUTABLE SOURCE</span>
                        </div>
                        <h2>{source.document.title.replace(".txt", "")}</h2>
                        <div className="source-hash">
                          SHA-256 · {source.document.checksum.slice(0, 20)}…
                        </div>
                        {highlight && (
                          <div className="citation-banner">
                            <Icon name="external" size={15} />
                            Showing the exact passage cited in this finding.
                            <button
                              onClick={() => {
                                setTab("evidence");
                              }}
                            >
                              Back to evidence <Icon name="arrow" size={13} />
                            </button>
                          </div>
                        )}
                        <div className="passages">
                          {source.passages.map((p) => (
                            <div
                              className={`passage ${highlight?.passage_id === p.id ? "cited" : ""}`}
                              key={p.id}
                            >
                              <span
                                className="line-reference"
                                title={`Lines ${p.line_start}–${p.line_end}`}
                              >
                                L{p.line_start}
                                {p.line_end !== p.line_start
                                  ? `–${p.line_end}`
                                  : ""}
                              </span>
                              <p>
                                {highlight?.passage_id === p.id &&
                                p.text.includes(highlight.quote) ? (
                                  <>
                                    {p.text.slice(
                                      0,
                                      p.text.indexOf(highlight.quote),
                                    )}
                                    <mark>{highlight.quote}</mark>
                                    {p.text.slice(
                                      p.text.indexOf(highlight.quote) +
                                        highlight.quote.length,
                                    )}
                                  </>
                                ) : (
                                  p.text
                                )}
                              </p>
                            </div>
                          ))}
                        </div>
                        {source.next_after !== null && (
                          <button
                            className="button small"
                            onClick={() =>
                              act("pages", async () => {
                                const next = await api<Source>(
                                  `/documents/${source.document.id}/source?after=${source.next_after}`,
                                );
                                setSource({
                                  ...next,
                                  passages: [
                                    ...source.passages,
                                    ...next.passages,
                                  ],
                                });
                              })
                            }
                          >
                            Read more passages
                          </button>
                        )}
                        <div className="paper-bottomline">
                          SOURCE PRESERVED · INTERPRETATION IS SEPARATE
                        </div>
                      </>
                    ) : (
                      <div className="reader-empty">
                        <Icon name="book" size={35} />
                        <h2>Read at the source.</h2>
                        <p>
                          Select a ready document to inspect its original
                          extracted passages and line references.
                        </p>
                      </div>
                    )}
                  </div>
                </section>
              )}
              <footer className="room-footer">
                <span>EvidenceLens / Local preview v0.1</span>
                <span>Traceable sources. Considered judgments.</span>
              </footer>
            </>
          )}
        </main>
      </div>
      <dialog
        ref={dialog}
        className="confirm-dialog"
        onCancel={() => setPendingDelete(null)}
      >
        <span className="eyebrow">
          REMOVE {pendingDelete?.type.toUpperCase()}
        </span>
        <h2>Remove “{pendingDelete?.title}”?</h2>
        <p>
          Access will be revoked immediately. The worker will remove stored text
          and derived evidence. Downloaded briefs remain on your computer.
        </p>
        <div>
          <button className="button" onClick={() => setPendingDelete(null)}>
            Keep it
          </button>
          <button className="button danger" disabled={!!busy} onClick={remove}>
            Remove and clean up
          </button>
        </div>
      </dialog>
    </>
  );
}

function FindingCard({
  finding,
  disabled,
  inspect,
  review,
}: {
  finding: Finding;
  disabled: boolean;
  inspect: () => void;
  review: (
    decision: "accepted" | "dismissed" | "unreviewed",
    note?: string,
  ) => void;
}) {
  const [note, setNote] = useState(finding.note);
  return (
    <article
      className={`finding-card ${finding.decision === "dismissed" ? "dismissed" : ""}`}
    >
      <div className="finding-source">
        <Icon name="file" size={14} />
        <span>{finding.document_title.replace(".txt", "")}</span>
        <button onClick={inspect}>
          L{finding.line_start}–{finding.line_end}
          <Icon name="external" size={12} />
        </button>
      </div>
      <blockquote>{finding.quote}</blockquote>
      <p className="finding-explanation">{finding.explanation}</p>
      <div className="finding-footer">
        <button className="text-button" onClick={inspect}>
          Read in source
          <Icon name="arrow" size={13} />
        </button>
        <div className="review-controls">
          <button
            disabled={disabled}
            className={finding.decision === "accepted" ? "is-accepted" : ""}
            aria-pressed={finding.decision === "accepted"}
            onClick={() =>
              review(
                finding.decision === "accepted" ? "unreviewed" : "accepted",
              )
            }
          >
            <Icon name="check" size={13} />
            {finding.decision === "accepted" ? "Accepted" : "Accept"}
          </button>
          <button
            disabled={disabled}
            className={finding.decision === "dismissed" ? "is-dismissed" : ""}
            aria-pressed={finding.decision === "dismissed"}
            onClick={() =>
              review(
                finding.decision === "dismissed" ? "unreviewed" : "dismissed",
              )
            }
          >
            <Icon name="close" size={13} />
            {finding.decision === "dismissed" ? "Dismissed" : "Dismiss"}
          </button>
        </div>
      </div>
      <details className="review-note">
        <summary>
          {finding.note ? "Reviewer note" : "Add a reviewer note"}
        </summary>
        <label className="sr-only" htmlFor={`note-${finding.id}`}>
          Reviewer note for {finding.document_title}
        </label>
        <textarea
          id={`note-${finding.id}`}
          rows={2}
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          className="button small"
          disabled={disabled || note === finding.note}
          onClick={() =>
            review(
              finding.decision as "accepted" | "dismissed" | "unreviewed",
              note,
            )
          }
        >
          Save note
        </button>
      </details>
    </article>
  );
}
