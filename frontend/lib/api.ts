import type { UploadResponse, SessionState, FeedbackRequest, Artifact, MessageHistoryItem, UsageSummary, Plan, TaskSummary } from "./types"
import { authHeader } from "./supabase/token"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

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

export async function uploadDataset(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append("file", file)
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
