"use client"
import { useState, useEffect, useCallback } from "react"
import type { SessionState, UploadResponse, TaskMode } from "@/lib/types"
import { uploadDataset, getSessionState, closeSession, resetConversation } from "@/lib/api"

const SESSION_STORAGE_KEY = "analytika_session_id"

export interface UseSessionReturn {
  sessionId: string | null
  sessionState: SessionState | null
  loading: boolean
  error: string | null
  upload: (file: File, mode: TaskMode) => Promise<UploadResponse | null>
  select: (sessionId: string) => Promise<void>
  refresh: () => Promise<void>
  reset: () => Promise<void>
  end: () => void
}

export function useSession(): UseSessionReturn {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionState, setSessionState] = useState<SessionState | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY)
    if (stored) _restoreSession(stored)
  }, [])

  useEffect(() => {
    const handleUnload = () => { if (sessionId) closeSession(sessionId) }
    window.addEventListener("beforeunload", handleUnload)
    return () => window.removeEventListener("beforeunload", handleUnload)
  }, [sessionId])

  async function _restoreSession(id: string) {
    setLoading(true)
    try {
      const state = await getSessionState(id)
      // Only resume a session whose dataset is still loaded. If the data was
      // wiped (or the session is otherwise unusable), drop it and fall back to
      // the upload screen instead of restoring a dead session.
      if (!state.dataset_ready) {
        localStorage.removeItem(SESSION_STORAGE_KEY)
        setSessionId(null)
        setSessionState(null)
        return
      }
      setSessionId(id)
      setSessionState(state)
    } catch {
      localStorage.removeItem(SESSION_STORAGE_KEY)
      setSessionId(null)
      setSessionState(null)
    } finally {
      setLoading(false)
    }
  }

  const upload = useCallback(async (file: File, mode: TaskMode): Promise<UploadResponse | null> => {
    setLoading(true)
    setError(null)
    try {
      const result = await uploadDataset(file, mode)
      setSessionId(result.session_id)
      localStorage.setItem(SESSION_STORAGE_KEY, result.session_id)
      setSessionState({
        session_id: result.session_id,
        mode,
        hypothesis_text: null,
        dataset_filename: result.filename,
        profile_summary: result.profile_summary,
        artifact_count: 0,
        dataset_ready: true,
      })
      return result
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.")
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  // Switch to an existing task the user picked from the sidebar. Unlike restore,
  // this keeps the task selected even if its dataset was wiped, so the user can
  // still read its history (queries will prompt a re-upload).
  const select = useCallback(async (id: string): Promise<void> => {
    if (id === sessionId) return
    setLoading(true)
    setError(null)
    try {
      const state = await getSessionState(id)
      setSessionId(id)
      setSessionState(state)
      localStorage.setItem(SESSION_STORAGE_KEY, id)
    } catch {
      setError("Could not open that task.")
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  const refresh = useCallback(async () => {
    if (!sessionId) return
    try {
      const state = await getSessionState(sessionId)
      setSessionState(state)
    } catch {}
  }, [sessionId])

  const reset = useCallback(async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      await resetConversation(sessionId)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.")
    } finally {
      setLoading(false)
    }
  }, [sessionId, refresh])

  const end = useCallback(() => {
    if (sessionId) closeSession(sessionId)
    localStorage.removeItem(SESSION_STORAGE_KEY)
    setSessionId(null)
    setSessionState(null)
  }, [sessionId])

  return { sessionId, sessionState, loading, error, upload, select, refresh, reset, end }
}
