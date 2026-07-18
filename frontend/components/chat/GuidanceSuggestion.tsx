"use client"
import { useState } from "react"
import type { NextAction, NudgeStyle } from "@/lib/types"

interface GuidanceSuggestionProps {
  suggestion: string
  style?: NudgeStyle
  isHypothesisCandidate?: boolean
  nextAction?: NextAction | null
  onAccept?: () => void
  onRun?: (query: string) => void
  onDismiss?: () => void
}

export function GuidanceSuggestion({ suggestion, style = "soft", isHypothesisCandidate = false, nextAction, onAccept, onRun, onDismiss }: GuidanceSuggestionProps) {
  const [dismissed, setDismissed] = useState(false)
  const [ran, setRan] = useState(false)
  const [accepted, setAccepted] = useState(false)
  if (dismissed) return null

  // Directive (guided mode): a forward next-step, styled as an expected action
  // with no "Not now" — the user can always just type something else instead.
  if (style === "directive") {
    return (
      <div className="mt-2 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
        <span className="mt-0.5 text-emerald-600">→</span>
        <div className="flex-1">
          <p className="text-sm text-gray-700">{suggestion}</p>
          {nextAction && !ran && (
            <button onClick={() => { setRan(true); onRun?.(nextAction.query) }} className="mt-2 inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
              {nextAction.label}
            </button>
          )}
          {ran && <p className="mt-1 text-xs text-emerald-700">✓ Continuing…</p>}
        </div>
      </div>
    )
  }

  // Soft (explore mode): the original dismissible amber suggestion.
  const showRun = !isHypothesisCandidate && nextAction && !ran
  return (
    <div className="mt-2 flex items-start gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3">
      <span className="mt-0.5 text-amber-500">💡</span>
      <div className="flex-1">
        <p className="text-sm text-gray-700">{suggestion}</p>

        {isHypothesisCandidate && !accepted && (
          <div className="mt-2 flex gap-2">
            <button onClick={() => { setAccepted(true); onAccept?.() }} className="rounded-lg bg-amber-500 px-3 py-1 text-xs font-medium text-white hover:bg-amber-600">Track as project</button>
            <button onClick={() => { setDismissed(true); onDismiss?.() }} className="rounded-lg border border-amber-300 px-3 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100">Not now</button>
          </div>
        )}
        {accepted && <p className="mt-1 text-xs text-amber-700">✓ Tracking this as your research project</p>}

        {showRun && (
          <div className="mt-2 flex gap-2">
            <button onClick={() => { setRan(true); onRun?.(nextAction!.query) }} className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
              {nextAction!.label}
            </button>
            <button onClick={() => { setDismissed(true); onDismiss?.() }} className="rounded-lg border border-amber-300 px-3 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100">Not now</button>
          </div>
        )}
        {ran && <p className="mt-1 text-xs text-indigo-700">✓ Running…</p>}
      </div>

      {!isHypothesisCandidate && !nextAction && (
        <button onClick={() => { setDismissed(true); onDismiss?.() }} className="text-gray-400 hover:text-gray-600">✕</button>
      )}
    </div>
  )
}
