"use client"
import type { StreamChunk } from "@/lib/types"

type Report = NonNullable<StreamChunk["report"]>

function download(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click()
  document.body.removeChild(a); URL.revokeObjectURL(url)
}

export function ReportCard({ report }: { report: Report }) {
  return (
    <div className="mt-3 rounded-xl border border-green-200 bg-green-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-green-800">Report ready</p>
          <p className="mt-0.5 text-xs text-green-600">{report.artifact_count} analyses across {report.stages_covered.length} stages</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => download(report.markdown, report.filename, "text/markdown")}
            className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 transition-colors"
          >
            Download .md
          </button>
          {report.latex && (
            <button
              onClick={() => download(report.latex!, report.latex_filename || "report.tex", "application/x-tex")}
              className="rounded-lg border border-green-600 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 transition-colors"
              title="APA write-up as a copy-ready LaTeX document"
            >
              LaTeX
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
