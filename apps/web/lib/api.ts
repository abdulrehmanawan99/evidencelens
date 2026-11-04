import type { components } from "./schema";

export type Collection = components["schemas"]["CollectionOut"];
export type Document = components["schemas"]["DocumentOut"];
export type Investigation = components["schemas"]["InvestigationOut"];
export type Finding = components["schemas"]["FindingOut"];
export type Job = components["schemas"]["JobOut"];
export type ExportRecord = components["schemas"]["ExportOut"];
export type Page<T> = { items: T[]; next_cursor: string | null };
export type Source = components["schemas"]["SourceOut"];
export type RunSummary = {
  id: string;
  claim: string;
  outcome: string | null;
  stale: boolean;
  created_at: string;
};
export type Provider = {
  mode: string;
  message: string;
  supported_claims: string[];
  accepted_types: string[];
  max_upload_bytes: number;
  configured: boolean;
  live_enabled: boolean;
  configuration_error: string | null;
  provider: string;
  embedding: { model: string; provider: string; dimensions: number; fingerprint: string } | null;
};

export type IndexStatus = { ready: boolean; expected: number; indexed: number; fingerprint: string | null; model?: string; mode?: string; configuration_error?: string };

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init?.body && typeof init.body === "string"
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg).join("; ")
      : detail?.message;
    throw new ApiError(
      message || `Request failed (${response.status}). Please retry.`,
      response.status,
      detail?.code,
    );
  }
  return response.json() as Promise<T>;
}

export async function waitForJob(id: string, onProgress?: (job: Job) => void, signal?: AbortSignal): Promise<Job> {
  for (let attempt = 0; attempt < 240; attempt++) {
    if (signal?.aborted) throw new Error("The view was closed.");
    const job = await api<Job>(`/jobs/${id}`, { signal });
    onProgress?.(job);
    if (job.state === "succeeded") return job;
    if (job.state === "failed") throw new Error(friendlyError(job.error_code));
    if (job.state === "cancelled") throw new Error("This operation was cancelled.");
    await new Promise(resolve => setTimeout(resolve, 750));
  }
  throw new Error("This job is still running. Its status is saved; you can return to it later.");
}

export async function downloadArtifact(path: string, filename: string) {
  const response = await fetch(`/api/v1${path}`, { cache: "no-store" });
  if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail?.message || "The export could not be downloaded."); }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const friendlyError = (code: string | null) =>
  ({
    fixture_not_available:
      "This fixture supports the sample reports and the three suggested claims only. Live analysis is not connected yet.",
    source_changed:
      "Sources changed during this investigation. Start a new run.",
    source_integrity_mismatch:
      "The stored original no longer matches its upload checksum. Remove it and upload the original file again.",
    attempt_or_deadline_limit:
      "The worker could not finish within its attempt or deadline limit. Retry the operation.",
    source_unavailable:
      "The original source could not be read. Remove it and upload it again.",
    encrypted_pdf: "Encrypted PDFs are not supported. Upload a permitted, unencrypted copy.",
    ocr_required: "This PDF has no extractable text. OCR is outside v1; upload a text-based version.",
    malformed_pdf: "The PDF could not be parsed. Export a fresh PDF and try again.",
    pdf_page_limit: "PDFs can contain at most 100 pages.",
    parser_timeout: "PDF parsing exceeded its time limit. Try a smaller source.",
    parser_resource_limit: "The PDF exceeded parser resources or the isolated parser is unavailable. Check the local setup and try a simpler file.",
    parser_isolation_unavailable: "The isolated PDF parser is unavailable. Check the local setup instructions.",
    index_required: "The selected embedding profile needs a search index. Rebuild the collection index, then investigate again.",
    provider_configuration_changed: "Provider settings changed. Restart the app, rebuild the index, and start a new run.",
    provider_authentication_failed: "The provider rejected its server-side credentials. Check your local configuration.",
    provider_request_rejected: "The provider rejected the model, capabilities, or request limits. Check the configured models and capability guide.",
    provider_timeout: "The provider timed out. Check its availability and retry with a new investigation.",
    provider_rate_limited: "The provider rate limit was reached. Wait before starting another run.",
    invalid_evidence: "The model returned evidence that did not match the supplied passages. No findings were published.",
    model_refused: "The model declined this analysis. No findings were published.",
    model_incomplete: "The model could not finish within its output/context limits. No partial result was published.",
    job_deadline: "This job exceeded its overall time budget. Check the provider and input size before retrying.",
    model_context_limit: "The configured model context is too small for this analysis. Check the configuration or use a shorter claim.",
  })[code || ""] ||
  "This job failed. Retry it or inspect its event history in the local API.";
