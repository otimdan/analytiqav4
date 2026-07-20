import type { UploadResponse, SessionState, FeedbackRequest, Artifact, MessageHistoryItem, UsageSummary, Plan, TaskSummary, TaskMode } from "./types"
import { authHeader } from "./supabase/token"

// Trailing slashes are stripped: paths below all start with "/", and a base URL
// ending in "/" would produce "//session/upload", which FastAPI 404s.
const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "")

async function apiFetch<T>(path: string, options: RequestInit & { sessionId?: string } = {}): Promise<T> {
  const { sessionId, ...fetchOptions } = options
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await authHeader()),
    ...(fetchOptions.headers as Record<string, string>),
  }
  if (sessionId) headers["X-Session-Id"] = sessionId

  const res = await fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }))
    throw new Error(error.detail || `API error ${res.status}`)
  }
  return res.json()
}

// The backend sleeps on Render's free tier and takes ~40s to wake. Nothing else
// touches it before the first upload, so that upload would absorb the whole
// wake-up behind a bare "Analysing dataset…". Firing this on mount moves the
// wake-up into the time the user spends picking a mode and a file.
// Deliberately fire-and-forget: a failure here must never surface or block.
export function warmBackend(): void {
  fetch(`${BASE_URL}/health`).catch(() => {})
}

// Mirrors the backend's MAX_UPLOAD_MB default so an oversized file fails
// instantly instead of after a long upload. The backend stays authoritative —
// if it is configured lower, its 413 detail is what the user sees.
const MAX_UPLOAD_MB = 25

export async function uploadDataset(file: File, mode: TaskMode = "explore"): Promise<UploadResponse> {
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    throw new Error(`That file is larger than the ${MAX_UPLOAD_MB} MB limit. Try a smaller extract of the dataset.`)
  }
  const form = new FormData()
  form.append("file", file)
  form.append("mode", mode)
  const res = await fetch(`${BASE_URL}/session/upload`, { method: "POST", body: form, headers: await authHeader() })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }))
    throw new Error(error.detail || "Upload failed")
  }
  return res.json()
}

export async function getSessionState(sessionId: string): Promise<SessionState> {
  return apiFetch<SessionState>(`/session/${sessionId}/state`)
}

export async function getMessages(sessionId: string): Promise<MessageHistoryItem[]> {
  return apiFetch<MessageHistoryItem[]>(`/session/${sessionId}/messages`, { sessionId })
}

export async function closeSession(sessionId: string): Promise<void> {
  navigator.sendBeacon(`${BASE_URL}/session/${sessionId}/close`)
}

export async function resetConversation(sessionId: string): Promise<void> {
  await apiFetch(`/session/${sessionId}/reset`, { method: "POST", sessionId })
}

export async function listTasks(): Promise<TaskSummary[]> {
  return apiFetch<TaskSummary[]>("/session/list")
}

export async function renameTask(sessionId: string, title: string): Promise<void> {
  await apiFetch(`/session/${sessionId}/title`, { method: "POST", sessionId, body: JSON.stringify({ title }) })
}

export async function deleteTask(sessionId: string): Promise<void> {
  await apiFetch(`/session/${sessionId}/delete`, { method: "POST", sessionId })
}

export async function getArtifacts(sessionId: string): Promise<Artifact[]> {
  return apiFetch<Artifact[]>(`/artifacts/${sessionId}`, { sessionId })
}

export async function getCompletedStages(sessionId: string): Promise<string[]> {
  return apiFetch<string[]>(`/artifacts/${sessionId}/stages`, { sessionId })
}

export async function submitFeedback(req: FeedbackRequest): Promise<void> {
  await apiFetch("/feedback", { method: "POST", sessionId: req.session_id, body: JSON.stringify(req) })
}

export async function getUsage(): Promise<UsageSummary> {
  return apiFetch<UsageSummary>("/me/usage")
}

export async function getPlans(): Promise<Plan[]> {
  return apiFetch<Plan[]>("/billing/plans")
}

export async function createCheckout(plan: string = "pro"): Promise<{ checkout_url: string }> {
  return apiFetch<{ checkout_url: string }>("/billing/checkout", { method: "POST", body: JSON.stringify({ plan }) })
}

export async function createPortalSession(): Promise<{ portal_url: string }> {
  return apiFetch<{ portal_url: string }>("/billing/portal", { method: "POST" })
}
