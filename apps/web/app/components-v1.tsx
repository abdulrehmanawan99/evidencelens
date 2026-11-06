"use client";

import { useEffect, useRef, useState } from "react";
import { api, downloadArtifact, friendlyError, waitForJob, type Document, type ExportRecord, type IndexStatus, type Investigation, type Job, type Page, type Provider, type Source } from "@/lib/api";

type Notices = { onError: (message: string) => void; onNotice: (message: string) => void };

export function ProviderBar({ provider, index, collectionId, refresh, onError, onNotice }: Notices & { provider: Provider | null; index: IndexStatus | null; collectionId: string; refresh: () => Promise<void> }) {
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  async function start(kind: "reindex" | "provider") {
    setBusy(true); onError("");
    try {
      const created = await api<Job>(kind === "reindex" ? `/collections/${collectionId}/reindex` : "/provider-checks", { method: "POST", ...(kind === "provider" ? { body: JSON.stringify({ collection_id: collectionId }) } : {}) });
      setJob(created);
      await waitForJob(created.id, setJob);
      await refresh();
      onNotice(kind === "reindex" ? "The selected search index is ready." : provider?.mode === "fixture" ? "Fixture capability check passed. This does not verify a live model." : "Provider capability check passed. Quality still depends on source evidence and model evaluation.");
    } catch (error) { onError(error instanceof Error ? error.message : "This operation failed."); }
    finally { setBusy(false); }
  }
  return <section className="provider-bar" aria-label="Provider and search readiness">
    <div><strong>{provider?.mode === "fixture" ? "Fixture demonstration" : "Live model configuration"}</strong><span>{provider?.provider || "Loading configuration"}{provider?.embedding && ` · retrieval: ${provider.embedding.provider} / ${provider.embedding.model}`}</span>{provider?.configuration_error && <p className="configuration-error">Configuration incomplete: {provider.configuration_error.replaceAll("_", " ")}. See the local provider setup guide.</p>}{provider?.mode !== "fixture" && <p>Selected source excerpts leave this computer for the configured provider. Review is required.</p>}</div>
    <div className="provider-actions"><span>{index?.ready ? `${index.indexed} passages indexed` : index?.expected ? `${index.indexed} / ${index.expected} passages indexed` : "No ready search index"}</span><button className="button small" disabled={busy || !provider?.configured} onClick={() => start("reindex")}>Rebuild search index</button><button className="button small" disabled={busy || !provider?.configured} onClick={() => start("provider")}>Check provider</button>{busy && job && <button className="text-button" onClick={() => api(`/jobs/${job.id}/cancel`, { method: "POST" }).catch(error => onError(error.message))}>Cancel {job.kind.replaceAll("_", " ")}</button>}</div>
    {busy && job && <p role="status">{job.stage.replaceAll("_", " ")} · status is saved in the background.</p>}
  </section>;
}

export function SourceVersions({ source, inspect, changed, onError, onNotice }: Notices & { source: Source; inspect: (id: string) => Promise<void>; changed: () => Promise<void> }) {
  const [versions, setVersions] = useState<Document[]>([]);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { let alive = true; api<Page<Document>>(`/documents/${source.document.id}/versions`).then(result => alive && setVersions(result.items)).catch(error => alive && onError(error.message)); return () => { alive = false; }; }, [source.document.id, onError]);
  async function replace(file: File) {
    setBusy(true); onError("");
    try {
      if (!/\.(pdf|txt)$/i.test(file.name) || file.size > 20 * 1024 * 1024) throw new Error("Choose a PDF or UTF-8 text file up to 20 MiB.");
      await api(`/documents/${source.document.id}/versions`, { method: "POST", body: file, headers: { "Content-Type": file.name.toLowerCase().endsWith(".pdf") ? "application/pdf" : "text/plain", "X-Filename": encodeURIComponent(file.name) } });
      await changed(); onNotice("Replacement queued. Previous source versions are retained; prior investigations are now stale.");
    } catch (error) { onError(error instanceof Error ? error.message : "Replacement failed."); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  async function activate() {
    setBusy(true);
    try { await api(`/documents/${source.document.id}/activate`, { method: "POST" }); await changed(); onNotice("This source version is active. Start a new investigation to use it."); } catch (error) { onError(error instanceof Error ? error.message : "Activation failed."); } finally { setBusy(false); }
  }
  return <div className="source-versions"><label>Source version<select aria-label="Source version" value={source.document.id} disabled={busy} onChange={event => inspect(event.target.value)}>{versions.map(version => <option key={version.id} value={version.id}>v{version.version} · {version.active ? "active" : "retained"} · {version.state}</option>)}</select></label><button className="button small" disabled={busy} onClick={() => input.current?.click()}>Upload replacement</button>{!source.document.active && <button className="button small" disabled={busy || source.document.state !== "ready"} onClick={activate}>Use this version</button>}<input ref={input} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="sr-only" aria-label="Upload replacement source" onChange={event => { const file = event.target.files?.[0]; if (file) void replace(file); }} /></div>;
}

export function ClaimSuggestions({ passageId, collectionId, choose, onError }: { passageId: string; collectionId: string; choose: (claim: string) => void; onError: (message: string) => void }) {
  const [claims, setClaims] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const job = useRef<string | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; if (job.current) void api(`/jobs/${job.current}/cancel`, { method: "POST" }).catch(() => {}); }; }, []);
  async function suggest() {
    setBusy(true); onError("");
    try {
      const created = await api<Job>(`/collections/${collectionId}/claim-suggestions`, { method: "POST", body: JSON.stringify({ passage_id: passageId }) }); job.current = created.id;
      const result = await waitForJob(created.id);
      if (alive.current) { setClaims((result.result_payload?.claims as string[]) || []); setChecked(true); }
    } catch (error) { if (alive.current) onError(error instanceof Error ? error.message : "Suggestions failed."); } finally { job.current = null; if (alive.current) setBusy(false); }
  }
  return <div className="claim-suggestions"><button className="text-button" disabled={busy} onClick={suggest}>{busy ? "Reading this passage…" : "Suggest claims from this passage"}</button>{busy && <button className="text-button" onClick={() => job.current && api(`/jobs/${job.current}/cancel`, { method: "POST" }).catch(error => onError(error.message))}>Cancel</button>}{claims.length > 0 && <div className="suggestion-results"><span>Choose a claim to review before investigating:</span>{claims.map(claim => <button key={claim} onClick={() => choose(claim)}>{claim}</button>)}</div>}{checked && !claims.length && <p>No claim was suggested from this passage.</p>}</div>;
}

export function ExportHistory({ run, refreshKey, onError, onNotice }: Notices & { run: Investigation; refreshKey: number }) {
  const [exports, setExports] = useState<ExportRecord[]>([]);
  useEffect(() => { let alive = true; api<Page<ExportRecord>>(`/investigations/${run.id}/exports`).then(result => alive && setExports(result.items)).catch(error => alive && onError(error.message)); return () => { alive = false; }; }, [run.id, refreshKey, run.stale, onError]);
  if (!exports.length) return null;
  return <div className="saved-exports"><span className="eyebrow">SAVED BRIEF REVISIONS</span>{exports.slice(0, 10).map(row => <button key={row.id} disabled={row.state !== "ready" || run.stale} onClick={() => downloadArtifact(`/exports/${row.id}/download`, `evidencelens-${run.id.slice(0, 8)}-r${row.review_revision}.md`).then(() => onNotice("Saved brief downloaded.")).catch(error => onError(error.message))}>Review r{row.review_revision} · {row.draft ? "draft" : "reviewed"}<small>{row.state}</small></button>)}</div>;
}

export function Provenance({ run, inspectPassage, onError }: { run: Investigation; inspectPassage: (id: string) => void; onError: (message: string) => void }) {
  const [hits, setHits] = useState<{ passage_id: string; method: string; rank: number; in_context: boolean }[] | null>(null);
  return <details className="provenance" onToggle={event => { if (event.currentTarget.open && hits === null) api<{ hits: NonNullable<typeof hits> }>(`/investigations/${run.id}/trace`).then(result => setHits(result.hits)).catch(error => onError(error.message)); }}><summary>Retrieval and model provenance</summary><p>{run.mode === "fixture" ? "Fixture output; lexical demo embeddings; no live model calls." : `${run.configuration.generation_model || run.mode} · ${run.provider_calls.length} recorded provider attempts`}</p><p>Retrieval: {String((run.configuration.embedding as { provider?: string } | undefined)?.provider || "legacy fixture")}.</p><p>Analysis: {String(run.configuration.analysis_version || "legacy fixture")}. Source and embedding versions are pinned in this run.</p>{run.provider_calls.map((call, index) => <p key={index}>{String(call.kind)} · {String(call.model)} · {String(call.state)} · {String(call.duration_ms)} ms</p>)}{hits?.filter(hit => hit.in_context).slice(0, 24).map(hit => <button key={`${hit.method}-${hit.passage_id}`} onClick={() => inspectPassage(hit.passage_id)}>{hit.method} #{hit.rank} · open supplied passage</button>)}</details>;
}
