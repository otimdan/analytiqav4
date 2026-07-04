"use client"
export function ReportCard({ report }: { report: { markdown: string; filename: string; artifact_count: number; stages_covered: string[] } }) {
  const handleDownload = () => {
    const blob = new Blob([report.markdown], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = report.filename
    document.body.appendChild(a); a.click()
    document.body.removeChild(a); URL.revokeObjectURL(url)
  }
  return (
    <div className="mt-3 rounded-xl border border-green-200 bg-green-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-green-800">Report ready</p>
          <p className="mt-0.5 text-xs text-green-600">{report.artifact_count} analyses across {report.stages_covered.length} stages</p>
        </div>
        <button onClick={handleDownload} className="shrink-0 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 transition-colors">Download .md</button>
      </div>
    </div>
  )
}
