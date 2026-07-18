"use client"
import type { GuidedStageKey } from "@/lib/types"
import { GUIDED_STAGES } from "@/lib/types"

// Guided-analysis progress, rendered inside the left sidebar: the tracked
// project on top, then connected dots with stage labels. Completion is derived
// from artifacts/session state (see deriveGuidedProgress).
export function StepRail({ doneKeys, hypothesisText }: { doneKeys: Set<GuidedStageKey>; hypothesisText?: string | null }) {
  return (
    <div>
      <div className="mb-4 rounded-lg border border-emerald-100 bg-white px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">Project</p>
        <p className="mt-1 text-xs leading-snug text-gray-600">{hypothesisText || "Guided analysis in progress"}</p>
      </div>
      <p className="mb-3 px-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">Guided analysis</p>
      {GUIDED_STAGES.map((stage, index) => {
        const isCompleted = doneKeys.has(stage.key)
        const isLast = index === GUIDED_STAGES.length - 1
        return (
          <div key={stage.key} className="flex items-stretch gap-2.5">
            <div className="flex flex-col items-center">
              <div className={`flex h-5 w-5 items-center justify-center rounded-full border-2 text-[10px] font-bold transition-all duration-300 ${isCompleted ? "border-emerald-600 bg-emerald-600 text-white" : "border-gray-300 bg-white text-gray-400"}`}>
                {isCompleted ? "✓" : index + 1}
              </div>
              {!isLast && <div className={`w-0.5 flex-1 transition-colors duration-300 ${isCompleted ? "bg-emerald-300" : "bg-gray-200"}`} />}
            </div>
            <p className={`pb-4 text-xs leading-tight transition-colors duration-300 ${isCompleted ? "font-medium text-emerald-700" : "text-gray-400"}`}>{stage.label}</p>
          </div>
        )
      })}
    </div>
  )
}
