"use client"
import type { TaskMode } from "@/lib/types"

// First step of a new task: choose a mode BEFORE a task/dataset exists. The
// choice is fixed for the task's lifetime (no switching in this version).
export function ModePicker({ onChoose }: { onChoose: (mode: TaskMode) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4 text-center">
      <h1 className="text-2xl font-semibold text-gray-800">How do you want to work?</h1>
      <p className="mt-2 text-sm text-gray-500">Pick how this task should run. This is set for the whole task.</p>

      <div className="mt-8 grid w-full max-w-3xl gap-4 sm:grid-cols-2">
        <ModeCard
          onClick={() => onChoose("explore")}
          accent="indigo"
          icon={<ChatIcon />}
          title="Explore your data"
          subtitle="Just chat with your data. Ask anything, no fixed steps."
        />
        <ModeCard
          onClick={() => onChoose("guided")}
          accent="emerald"
          icon={<StepsIcon />}
          title="Guided analysis"
          subtitle="Step-by-step from dataset to a finished report."
        />
      </div>
    </div>
  )
}

function ModeCard({ onClick, icon, title, subtitle, accent }: {
  onClick: () => void
  icon: React.ReactNode
  title: string
  subtitle: string
  accent: "indigo" | "emerald"
}) {
  const ring = accent === "indigo"
    ? "hover:border-indigo-400 hover:shadow-indigo-100"
    : "hover:border-emerald-400 hover:shadow-emerald-100"
  const chip = accent === "indigo" ? "bg-indigo-50 text-indigo-600" : "bg-emerald-50 text-emerald-600"
  return (
    <button
      onClick={onClick}
      className={`group flex flex-col items-start gap-3 rounded-2xl border border-gray-200 bg-white p-6 text-left shadow-sm transition-all hover:shadow-md ${ring}`}
    >
      <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${chip}`}>{icon}</span>
      <span className="text-base font-semibold text-gray-800">{title}</span>
      <span className="text-sm leading-snug text-gray-500">{subtitle}</span>
    </button>
  )
}

function ChatIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function StepsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <circle cx="3.5" cy="6" r="1.5" />
      <circle cx="3.5" cy="12" r="1.5" />
      <circle cx="3.5" cy="18" r="1.5" />
    </svg>
  )
}
