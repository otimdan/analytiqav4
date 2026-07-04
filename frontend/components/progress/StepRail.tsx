"use client"
import type { ArtifactStage } from "@/lib/types"
import { RAIL_STAGES } from "@/lib/types"

export function StepRail({ completedStages, hypothesisText }: { completedStages: Set<ArtifactStage>; hypothesisText?: string | null }) {
  return (
    <div className="flex w-48 shrink-0 flex-col gap-1 border-r border-gray-100 bg-gray-50 px-4 py-6">
      {hypothesisText && (
        <div className="mb-4 rounded-lg border border-indigo-100 bg-white px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400">Project</p>
          <p className="mt-1 text-xs leading-snug text-gray-600">{hypothesisText}</p>
        </div>
      )}
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Progress</p>
      {RAIL_STAGES.map((stage, index) => {
        const isCompleted = completedStages.has(stage.key)
        return (
          <div key={stage.key} className="flex items-start gap-2">
            <div className="flex flex-col items-center">
              <div className={`flex h-5 w-5 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-300 ${isCompleted ? "border-indigo-600 bg-indigo-600 text-white" : "border-gray-300 bg-white text-gray-400"}`}>
                {isCompleted ? "✓" : index + 1}
              </div>
              {index < RAIL_STAGES.length - 1 && <div className={`mt-0.5 h-6 w-0.5 transition-colors duration-300 ${isCompleted ? "bg-indigo-200" : "bg-gray-200"}`} />}
            </div>
            <p className={`mt-0.5 text-xs leading-tight transition-colors duration-300 ${isCompleted ? "font-medium text-indigo-700" : "text-gray-400"}`}>{stage.label}</p>
          </div>
        )
      })}
    </div>
  )
}
