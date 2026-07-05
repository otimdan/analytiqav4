"use client"

// Loading state shown while the assistant is working: a running indicator, a
// terminal-style skeleton that reads as code being written, and placeholder
// chart tiles — mirroring the "Generating code" phase before results land.
export function StreamingOutput({ isVisible }: { isVisible: boolean }) {
  if (!isVisible) return null
  return (
    <div className="px-4 pb-6">
      <div className="max-w-[80%] space-y-3">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
          <span className="shimmer-text font-medium">Running analysis…</span>
        </div>

        <div className="overflow-hidden rounded-lg border border-gray-800 bg-gray-900 px-3 py-3">
          <div className="mb-2 flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-gray-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-gray-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-gray-700" />
            <span className="ml-1 text-[10px] uppercase tracking-wide text-gray-500">generating code</span>
          </div>
          {[9, 7, 11, 6].map((w, i) => (
            <div key={i} className="mb-2 flex items-center gap-2">
              <span className="w-4 text-right text-[10px] text-gray-600">{i + 1}</span>
              <span className="shimmer-bar h-2.5 rounded" style={{ width: `${w * 8}%` }} />
              {i === 3 && <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-indigo-400" />}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="shimmer-bar h-20 rounded-lg" />
          ))}
        </div>
      </div>

      <style>{`
        .shimmer-bar { background: linear-gradient(90deg, rgba(148,163,184,0.18) 25%, rgba(148,163,184,0.35) 37%, rgba(148,163,184,0.18) 63%); background-size: 400% 100%; animation: shimmer 1.4s ease infinite; }
        .shimmer-text { background: linear-gradient(90deg, #9ca3af 25%, #4f46e5 50%, #9ca3af 75%); background-size: 200% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; animation: shimmer 1.8s linear infinite; }
        @keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }
      `}</style>
    </div>
  )
}
