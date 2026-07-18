"use client"
import { useMemo } from "react"
import type { SessionState, GuidanceState } from "@/lib/types"

// Guidance state now derives from the explicit task mode, not the old inferred
// booleans. The step rail shows iff the task is guided; the project header shows
// whatever research question has been captured.
export function useGuidance(sessionState: SessionState | null): GuidanceState {
  const mode = sessionState?.mode ?? "explore"
  return useMemo(() => ({
    mode,
    is_guided: mode === "guided",
    hypothesis_text: sessionState?.hypothesis_text ?? null,
  }), [mode, sessionState?.hypothesis_text])
}
