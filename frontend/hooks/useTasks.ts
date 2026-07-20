"use client"
import { useState, useEffect, useCallback } from "react"
import type { TaskSummary } from "@/lib/types"
import { listTasks, deleteTask as apiDeleteTask, renameTask as apiRenameTask } from "@/lib/api"
import { useAuthUser } from "@/hooks/useAuthUser"

export interface UseTasksReturn {
  tasks: TaskSummary[]
  loading: boolean
  refresh: () => Promise<void>
  remove: (id: string) => Promise<void>
  rename: (id: string, title: string) => Promise<void>
}

// The user's saved tasks for the sidebar. Refresh after upload / task switch so
// the list and its "most recent" ordering stay current.
export function useTasks(): UseTasksReturn {
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [loading, setLoading] = useState(false)
  const { user, loading: authLoading } = useAuthUser()

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setTasks(await listTasks())
    } catch {
      // Unauthenticated or offline — leave the list as-is.
    } finally {
      setLoading(false)
    }
  }, [])

  const remove = useCallback(async (id: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== id))
    try {
      await apiDeleteTask(id)
    } catch {
      await refresh()
    }
  }, [refresh])

  const rename = useCallback(async (id: string, title: string) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, title } : t)))
    try {
      await apiRenameTask(id, title)
    } catch {
      await refresh()
    }
  }, [refresh])

  // Wait for Supabase to hydrate before asking for the list. Firing on mount
  // sent /session/list without a token on a fresh sign-in; the 401 was caught
  // and swallowed, so the sidebar stayed empty until some later action (an
  // upload) happened to refresh it. Keying on user.id also reloads the list
  // when the account changes and clears it on sign-out.
  useEffect(() => {
    if (authLoading) return
    if (!user) { setTasks([]); return }
    refresh()
  }, [authLoading, user?.id, refresh])

  return { tasks, loading, refresh, remove, rename }
}
