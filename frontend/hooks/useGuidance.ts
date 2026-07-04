"use client"
import { useMemo } from "react"
import type { SessionState, GuidanceState } from "@/lib/types"

export function useGuidance(sessionState: SessionState | null): GuidanceState {
  return useMemo(() => ({
    hypothesis_on_record: sessionState?.hypothesis_on_record ?? false,
    suggestion_mode: sessionState?.suggestion_mode ?? false,
    hypothesis_text: sessionState?.hypothesis_text ?? null,
  }), [sessionState?.hypothesis_on_record, sessionState?.suggestion_mode, sessionState?.hypothesis_text])
}
