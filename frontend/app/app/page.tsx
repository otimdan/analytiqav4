"use client"
import { useState, useCallback, useRef, useEffect, useMemo } from "react"
import type { Message, StreamChunk, ChartImage } from "@/lib/types"
import { getMessages } from "@/lib/api"
import { useSession } from "@/hooks/useSession"
import { useTasks } from "@/hooks/useTasks"
import { useGuidance } from "@/hooks/useGuidance"
import { useArtifacts } from "@/hooks/useArtifacts"
import { useUsage } from "@/hooks/useUsage"
import { streamQuery } from "@/lib/sse"
import { ChatInput } from "@/components/chat/ChatInput"
import { MessageList } from "@/components/chat/MessageList"
import { StreamingOutput } from "@/components/chat/StreamingOutput"
import { Sidebar } from "@/components/layout/Sidebar"
import { DataExplorer } from "@/components/artifacts/DataExplorer"
import { AccountMenu } from "@/components/auth/AccountMenu"
import { UsageMeter } from "@/components/account/UsageMeter"
import { UpgradeButton } from "@/components/account/UpgradeButton"

function nanoid() { return crypto.randomUUID() }

export default function AnalysisPage() {
  const { sessionId, sessionState, loading, error, upload, select, refresh, end } = useSession()
  const tasks = useTasks()
  const guidance = useGuidance(sessionState)
  const { completedStages, refresh: refreshArtifacts } = useArtifacts(sessionId)
  const { usage, refresh: refreshUsage } = useUsage()
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [dismissedFeedback, setDismissedFeedback] = useState<Set<string>>(new Set())
  const historyLoadedFor = useRef<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Returning from Dodo checkout: refresh the plan/usage and clean the URL.
  // (Webhook is the source of truth; this just pulls the fresh state sooner.)
  useEffect(() => {
    if (typeof window === "undefined") return
    if (new URLSearchParams(window.location.search).get("checkout") === "success") {
      refreshUsage()
      window.history.replaceState({}, "", "/app")
    }
  }, [refreshUsage])

  // On restore (session id set from localStorage, chat empty), load prior
  // messages so the conversation and its code/output blocks persist.
  useEffect(() => {
    if (!sessionId || historyLoadedFor.current === sessionId) return
    if (messages.length > 0) { historyLoadedFor.current = sessionId; return }
    historyLoadedFor.current = sessionId
    getMessages(sessionId)
      .then((history) => {
        if (!history.length) return
        setMessages(history.map((h) => ({
          id: h.id,
          server_message_id: h.id,
          role: h.role,
          content: h.content,
          images: h.images ?? [],
          regime: h.regime ?? undefined,
          executions: h.executions ?? [],
          created_at: h.created_at ? new Date(h.created_at) : new Date(),
        })))
      })
      .catch(() => {})
  }, [sessionId, messages.length])

  const handleSend = useCallback(async (text: string) => {
    if (!sessionId || isStreaming) return
    const userMessage: Message = { id: nanoid(), role: "user", content: text, images: [], created_at: new Date() }
    setMessages((prev) => [...prev, userMessage])
    const assistantId = nanoid()
    const assistantMessage: Message = { id: assistantId, role: "assistant", content: "", images: [], created_at: new Date() }
    setMessages((prev) => [...prev, assistantMessage])
    setIsStreaming(true)

    await streamQuery(sessionId, text,
      (chunk: StreamChunk) => {
        setMessages((prev) => {
          const updated = [...prev]
          const idx = updated.findIndex((m) => m.id === assistantId)
          if (idx === -1) return prev
          const msg = { ...updated[idx] }
          switch (chunk.type) {
            case "text": msg.content += chunk.content || ""; msg.regime = chunk.regime; if (chunk.show_feedback) msg.show_feedback = true; break
            case "image": msg.images = [...msg.images, { src: chunk.content || "", caption: chunk.caption }]; break
            case "disambiguation": msg.disambiguation = chunk.prompt; break
            case "confirmation_prompt": msg.confirmation_prompt = chunk.content; break
            case "guidance_suggestion": msg.guidance_suggestion = chunk.content; msg.guidance_next_action = chunk.next_action; msg.is_hypothesis_candidate = chunk.is_hypothesis_candidate; break
            case "report": msg.report = chunk.report; break
            case "code_execution": msg.executions = [...(msg.executions ?? []), { code: chunk.code || "", output: chunk.output || "" }]; break
            case "done": if (chunk.message_id) msg.server_message_id = chunk.message_id; break
          }
          updated[idx] = msg
          return updated
        })
      },
      (err: Error) => {
        setMessages((prev) => {
          const updated = [...prev]
          const idx = updated.findIndex((m) => m.id === assistantId)
          if (idx !== -1) updated[idx] = { ...updated[idx], content: "Something went wrong. Please try again." }
          return updated
        })
        setIsStreaming(false)
      },
      async () => {
        setIsStreaming(false)
        await refresh()
        await refreshArtifacts()
        await refreshUsage()
      }
    )
  }, [sessionId, isStreaming, refresh, refreshArtifacts, refreshUsage])

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = "" // allow re-selecting the same file
    if (!file) return
    historyLoadedFor.current = "pending" // don't let history load clobber the greeting
    const result = await upload(file)
    if (result) {
      historyLoadedFor.current = result.session_id
      setMessages([{
        id: nanoid(), role: "assistant",
        content: `Loaded ${result.rows} rows and ${result.columns} columns from ${result.filename}. What are you trying to find out — or are you just exploring for now?`,
        images: [], created_at: new Date(),
      }])
      tasks.refresh()
    } else {
      historyLoadedFor.current = null
    }
  }, [upload, tasks])

  const handleAttach = useCallback(() => fileInputRef.current?.click(), [])

  const handleNewTask = useCallback(() => {
    if (isStreaming) return
    end()
    setMessages([])
    historyLoadedFor.current = null
  }, [isStreaming, end])

  const handleSelectTask = useCallback(async (id: string) => {
    if (isStreaming || id === sessionId) return
    setMessages([])
    historyLoadedFor.current = null
    await select(id)
  }, [isStreaming, sessionId, select])

  // Artifacts for the right rail come from the conversation: every chart image
  // and every generated report the assistant has produced this session.
  const allImages = useMemo<ChartImage[]>(
    () => messages.flatMap((m) => (m.role === "assistant" ? m.images : [])),
    [messages],
  )
  const allReports = useMemo(
    () => messages.flatMap((m) => (m.report ? [m.report] : [])),
    [messages],
  )

  const hasDataset = !!sessionId

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      <input ref={fileInputRef} type="file" accept=".csv" onChange={handleFileChange} className="hidden" />

      <Sidebar
        guidance={guidance}
        completedStages={completedStages}
        tasks={tasks.tasks}
        activeTaskId={sessionId}
        onNewTask={handleNewTask}
        onSelectTask={handleSelectTask}
        onDeleteTask={tasks.remove}
        onRenameTask={tasks.rename}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-end gap-3 border-b border-gray-100 px-4 py-2">
          {usage?.plan === "free" && <UpgradeButton />}
          <UsageMeter usage={usage} />
          <AccountMenu />
        </div>

        <div className="flex-1 overflow-y-auto">
          {hasDataset ? (
            <>
              <MessageList
                messages={messages.map((m) => ({ ...m, show_feedback: m.show_feedback && !dismissedFeedback.has(m.id) }))}
                sessionId={sessionId} suggestionMode={guidance.suggestion_mode} isStreaming={isStreaming}
                onOptionSelect={(_, opt) => handleSend(opt)}
                onGuidanceAccept={() => handleSend("Track as project")}
                onGuidanceRun={(query) => handleSend(query)}
                onFeedbackDismiss={(id) => setDismissedFeedback((prev) => new Set([...prev, id]))}
              />
              <StreamingOutput isVisible={isStreaming} />
            </>
          ) : (
            <EmptyState onUpload={handleAttach} loading={loading} error={error} />
          )}
        </div>

        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          onAttach={handleAttach}
          disabled={!hasDataset}
          placeholder={hasDataset ? "Ask anything about your data…" : "Upload a dataset to get started…"}
        />
      </div>

      <DataExplorer
        datasetFilename={sessionState?.dataset_filename ?? null}
        rowCount={sessionState?.profile_summary?.row_count}
        images={allImages}
        reports={allReports}
      />
    </div>
  )
}

function EmptyState({ onUpload, loading, error }: { onUpload: () => void; loading: boolean; error: string | null }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4 text-center">
      <h1 className="text-2xl font-semibold text-gray-800">What can I do for you today?</h1>
      <p className="mt-2 text-sm text-gray-500">Upload a CSV and I&apos;ll help you explore, test, and visualize it.</p>
      <button
        onClick={onUpload}
        disabled={loading}
        className="mt-6 flex items-center gap-2 rounded-xl border-2 border-dashed border-gray-300 bg-white px-8 py-6 text-sm text-gray-600 transition-colors hover:border-indigo-400 hover:text-indigo-600 disabled:opacity-60"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        {loading ? "Analysing dataset…" : "Upload a CSV"}
      </button>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  )
}
