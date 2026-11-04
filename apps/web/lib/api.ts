import type { components } from "./schema";

export type Collection = components["schemas"]["CollectionOut"];
export type Document = components["schemas"]["DocumentOut"];
export type Investigation = components["schemas"]["InvestigationOut"];
export type Finding = components["schemas"]["FindingOut"];
export type Job = components["schemas"]["JobOut"];
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
};

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
    throw new Error(
      message || `Request failed (${response.status}). Please retry.`,
    );
  }
  return response.json() as Promise<T>;
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
  })[code || ""] ||
  "This job failed. Retry it or inspect its event history in the local API.";
