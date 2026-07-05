"use client"
import { useState, useEffect, useCallback } from "react"
import type { TaskSummary } from "@/lib/types"
import { listTasks, deleteTask as apiDeleteTask, renameTask as apiRenameTask } from "@/lib/api"

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

  useEffect(() => { refresh() }, [refresh])

  return { tasks, loading, refresh, remove, rename }
}
