"use client"
import { useState, useEffect, useCallback, useRef } from "react"
import type { Artifact, ArtifactStage } from "@/lib/types"
import { getArtifacts, getCompletedStages } from "@/lib/api"

export interface UseArtifactsReturn {
  artifacts: Artifact[]
  completedStages: Set<ArtifactStage>
  loading: boolean
  refresh: () => Promise<void>
}

export function useArtifacts(sessionId: string | null): UseArtifactsReturn {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [completedStages, setCompletedStages] = useState<Set<ArtifactStage>>(new Set())
  const [loading, setLoading] = useState(false)
  const fetchingRef = useRef(false)

  const refresh = useCallback(async () => {
    if (!sessionId || fetchingRef.current) return
    fetchingRef.current = true
    try {
      const [arts, stages] = await Promise.all([getArtifacts(sessionId), getCompletedStages(sessionId)])
      setArtifacts(arts)
      setCompletedStages(new Set(stages as ArtifactStage[]))
    } catch {}
    finally { fetchingRef.current = false }
  }, [sessionId])

  useEffect(() => {
    if (!sessionId) { setArtifacts([]); setCompletedStages(new Set()); return }
    setLoading(true)
    refresh().finally(() => setLoading(false))
  }, [sessionId])

  return { artifacts, completedStages, loading, refresh }
}
