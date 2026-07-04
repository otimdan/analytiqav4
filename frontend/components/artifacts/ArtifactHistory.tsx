"use client"
import type { Artifact } from "@/lib/types"

export function ArtifactHistory({ artifacts }: { artifacts: Artifact[] }) {
  if (!artifacts.length) {
    return (
      <div className="w-48 shrink-0 border-l border-gray-100 bg-gray-50 px-4 py-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Analyses</p>
        <p className="mt-3 text-xs text-gray-400">Completed analyses will appear here.</p>
      </div>
    )
  }
  return (
    <div className="flex w-48 shrink-0 flex-col gap-2 overflow-y-auto border-l border-gray-100 bg-gray-50 px-4 py-6">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-400">Analyses</p>
      {artifacts.map((artifact) => {
        const variables = artifact.variables_involved || []
        const varStr = variables.slice(0, 2).join(" vs ")
        const content = artifact.content as Record<string, unknown>
        const label = artifact.artifact_type === "test_result" ? (content?.display_name as string) || "Test"
          : artifact.artifact_type === "chart" ? `${(content?.chart_type as string) || "Chart"}`
          : artifact.artifact_type === "cleaned_dataset" ? "Data cleaned" : "Summary"
        const stageColors: Record<string, string> = {
          data_preparation: "bg-gray-100 text-gray-600", descriptive: "bg-blue-50 text-blue-700",
          inferential: "bg-indigo-50 text-indigo-700", visualisation: "bg-purple-50 text-purple-700",
          interpretation: "bg-green-50 text-green-700",
        }
        return (
          <div key={artifact.id} className={`rounded-lg p-2 text-xs ${stageColors[artifact.stage] || "bg-gray-100 text-gray-600"}`}>
            <p className="font-medium">{label}</p>
            {varStr && <p className="mt-0.5 opacity-75 truncate">{varStr}</p>}
          </div>
        )
      })}
    </div>
  )
}
