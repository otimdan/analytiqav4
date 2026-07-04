"use client"
import { useState } from "react"

interface GuidanceSuggestionProps {
  suggestion: string
  isHypothesisCandidate?: boolean
  onAccept?: () => void
  onDismiss?: () => void
}

export function GuidanceSuggestion({ suggestion, isHypothesisCandidate = false, onAccept, onDismiss }: GuidanceSuggestionProps) {
  const [dismissed, setDismissed] = useState(false)
  const [accepted, setAccepted] = useState(false)
  if (dismissed) return null
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
      </div>
      {!isHypothesisCandidate && (
        <button onClick={() => { setDismissed(true); onDismiss?.() }} className="text-gray-400 hover:text-gray-600">✕</button>
      )}
    </div>
  )
}
