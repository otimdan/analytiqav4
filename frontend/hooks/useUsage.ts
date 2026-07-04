"use client"
import { useState, useEffect, useCallback } from "react"
import type { UsageSummary } from "@/lib/types"
import { getUsage } from "@/lib/api"

export function useUsage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null)

  const refresh = useCallback(async () => {
    try {
      setUsage(await getUsage())
    } catch {
      // usage is non-critical UI; ignore failures
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return { usage, refresh }
}
