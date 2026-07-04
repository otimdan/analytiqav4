"use client"
import { useState } from "react"
import type { CodeExecution } from "@/lib/types"

interface CodeExecutionBlockProps {
  executions: CodeExecution[]
}

export function CodeExecutionBlock({ executions }: CodeExecutionBlockProps) {
  const [open, setOpen] = useState(false)
  if (!executions.length) return null

  const label = executions.length === 1 ? "View code & output" : `View code & output (${executions.length} steps)`

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
      >
        <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
        {label}
      </button>

      {open && (
        <div className="mt-2 flex flex-col gap-3">
          {executions.map((ex, i) => (
            <div key={i} className="overflow-hidden rounded-lg border border-gray-800 bg-gray-900">
              {executions.length > 1 && (
                <div className="border-b border-gray-800 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-gray-400">
                  Step {i + 1}
                </div>
              )}
              <CodePane code={ex.code} />
              {ex.output && (
                <div className="border-t border-gray-800">
                  <div className="px-3 pt-2 text-[11px] font-medium uppercase tracking-wide text-gray-500">Output</div>
                  <pre className="max-h-80 overflow-auto px-3 py-2 text-xs leading-relaxed text-gray-300 whitespace-pre-wrap break-words">{ex.output}</pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CodePane({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }
  return (
    <div className="relative">
      <button
        onClick={copy}
        className="absolute right-2 top-2 rounded bg-gray-800 px-2 py-0.5 text-[11px] text-gray-300 hover:bg-gray-700"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="max-h-96 overflow-auto px-3 py-3 text-xs leading-relaxed text-gray-100 whitespace-pre">
        <code className="font-mono">{code}</code>
      </pre>
    </div>
  )
}
