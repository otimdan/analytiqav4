"use client"
import { useState, useEffect, useRef } from "react"
import type { ArtifactStage, GuidanceState, TaskSummary } from "@/lib/types"
import { StepRail } from "@/components/progress/StepRail"
import { AccountMenu } from "@/components/auth/AccountMenu"

interface SidebarProps {
  guidance: GuidanceState
  completedStages: Set<ArtifactStage>
  tasks: TaskSummary[]
  activeTaskId: string | null
  onNewTask: () => void
  onSelectTask: (id: string) => void
  onDeleteTask: (id: string) => void
  onRenameTask: (id: string, title: string) => void
}

// Left navigation rail, Julius-style: brand, New Task, the user's saved tasks
// (recents), the guided-analysis step rail (only while a hypothesis is tracked),
// and the account avatar pinned to the footer.
export function Sidebar({ guidance, completedStages, tasks, activeTaskId, onNewTask, onSelectTask, onDeleteTask, onRenameTask }: SidebarProps) {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-gray-100 bg-gray-50/60">
      <div className="flex items-center px-4 py-4">
        <span className="text-lg font-semibold tracking-tight text-indigo-600">Analytika</span>
      </div>

      <div className="px-3">
        <button
          onClick={onNewTask}
          className="flex w-full items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
        >
          <PlusIcon />
          New task
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">Tasks</p>
        {tasks.length === 0 ? (
          <p className="px-1 text-xs text-gray-400">Your uploaded datasets will show up here.</p>
        ) : (
          <ul className="space-y-0.5">
            {tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                active={task.id === activeTaskId}
                onSelect={() => onSelectTask(task.id)}
                onDelete={() => onDeleteTask(task.id)}
                onRename={(title) => onRenameTask(task.id, title)}
              />
            ))}
          </ul>
        )}

        {guidance.hypothesis_on_record && (
          <div className="mt-6">
            <StepRail completedStages={completedStages} hypothesisText={guidance.hypothesis_text} />
          </div>
        )}
      </nav>

      <div className="border-t border-gray-100 px-3 py-3">
        <AccountMenu variant="sidebar" />
      </div>
    </aside>
  )
}

function TaskRow({ task, active, onSelect, onDelete, onRename }: {
  task: TaskSummary
  active: boolean
  onSelect: () => void
  onDelete: () => void
  onRename: (title: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(task.title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) { inputRef.current?.focus(); inputRef.current?.select() }
  }, [editing])

  function startEdit() { setDraft(task.title); setEditing(true) }
  function commit() {
    const next = draft.trim()
    setEditing(false)
    if (next && next !== task.title) onRename(next)
  }

  if (editing) {
    return (
      <li>
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit()
            else if (e.key === "Escape") setEditing(false)
          }}
          className="w-full rounded-lg border border-indigo-300 bg-white px-2.5 py-2 text-sm text-gray-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </li>
    )
  }

  return (
    <li>
      <div className={`group flex items-center gap-1 rounded-lg px-2.5 py-2 text-sm transition-colors ${active ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100"}`}>
        <button onClick={onSelect} onDoubleClick={startEdit} className="flex min-w-0 flex-1 items-center gap-2 text-left" title={task.title}>
          <SpreadsheetIcon />
          <span className="block truncate">{task.title}</span>
        </button>
        <button onClick={startEdit} title="Rename task" className="shrink-0 rounded p-1 text-gray-300 opacity-0 transition hover:bg-gray-200 hover:text-indigo-600 group-hover:opacity-100">
          <PencilIcon />
        </button>
        <button
          onClick={() => { if (window.confirm(`Delete “${task.title}”? This removes its messages and artifacts.`)) onDelete() }}
          title="Delete task"
          className="shrink-0 rounded p-1 text-gray-300 opacity-0 transition hover:bg-gray-200 hover:text-red-500 group-hover:opacity-100"
        >
          <TrashIcon />
        </button>
      </div>
    </li>
  )
}

function PencilIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function SpreadsheetIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="shrink-0" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  )
}
