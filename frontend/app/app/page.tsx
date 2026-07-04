"use client"
import { useState, useCallback, useRef, useEffect } from "react"
import type { Message, StreamChunk } from "@/lib/types"
import { getMessages } from "@/lib/api"
import { useSession } from "@/hooks/useSession"
import { useGuidance } from "@/hooks/useGuidance"
import { useArtifacts } from "@/hooks/useArtifacts"
import { useUsage } from "@/hooks/useUsage"
import { streamQuery } from "@/lib/sse"
import { ChatInput } from "@/components/chat/ChatInput"
import { MessageList } from "@/components/chat/MessageList"
import { StreamingOutput } from "@/components/chat/StreamingOutput"
import { StepRail } from "@/components/progress/StepRail"
import { ArtifactHistory } from "@/components/artifacts/ArtifactHistory"
import { AccountMenu } from "@/components/auth/AccountMenu"
import { UsageMeter } from "@/components/account/UsageMeter"
import { UpgradeButton } from "@/components/account/UpgradeButton"

function nanoid() { return crypto.randomUUID() }

export default function AnalysisPage() {
  const { sessionId, sessionState, loading, error, upload, refresh } = useSession()
  const guidance = useGuidance(sessionState)
  const { artifacts, completedStages, refresh: refreshArtifacts } = useArtifacts(sessionId)
  const { usage, refresh: refreshUsage } = useUsage()
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [dismissedFeedback, setDismissedFeedback] = useState<Set<string>>(new Set())
  const historyLoadedFor = useRef<string | null>(null)

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
          images: [],
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
    if (!file) return
    const result = await upload(file)
    if (result) {
      setMessages([{
        id: nanoid(), role: "assistant",
        content: `Loaded ${result.rows} rows and ${result.columns} columns from ${result.filename}. What are you trying to find out — or are you just exploring for now?`,
        images: [], created_at: new Date(),
      }])
    }
  }, [upload])

  if (!sessionId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
          <h1 className="text-xl font-semibold text-gray-900">Analytika</h1>
          <p className="mt-1 text-sm text-gray-500">AI-powered research data analysis</p>
          <label className="mt-6 block">
            <div className="cursor-pointer rounded-xl border-2 border-dashed border-gray-300 p-8 text-center hover:border-indigo-400 transition-colors">
              <p className="text-sm text-gray-600">Drop your CSV here or <span className="text-indigo-600 underline">browse</span></p>
              <p className="mt-1 text-xs text-gray-400">CSV files only</p>
            </div>
            <input type="file" accept=".csv" onChange={handleFileChange} className="hidden" />
          </label>
          {loading && <p className="mt-3 text-center text-sm text-indigo-600">Analysing dataset…</p>}
          {error && <p className="mt-3 text-center text-sm text-red-600">{error}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {guidance.hypothesis_on_record && <StepRail completedStages={completedStages} hypothesisText={guidance.hypothesis_text} />}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-4 py-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{sessionState?.dataset_filename}</span>
            <span className="text-xs text-gray-300">·</span>
            <span className="text-xs text-gray-400">{sessionState?.profile_summary?.row_count} rows</span>
          </div>
          <div className="flex items-center gap-3">
            {usage?.plan === "free" && <UpgradeButton />}
            <UsageMeter usage={usage} />
            <AccountMenu />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          <MessageList
            messages={messages.map((m) => ({ ...m, show_feedback: m.show_feedback && !dismissedFeedback.has(m.id) }))}
            sessionId={sessionId} suggestionMode={guidance.suggestion_mode} isStreaming={isStreaming}
            onOptionSelect={(_, opt) => handleSend(opt)}
            onGuidanceAccept={() => handleSend("Track as project")}
            onGuidanceRun={(query) => handleSend(query)}
            onFeedbackDismiss={(id) => setDismissedFeedback((prev) => new Set([...prev, id]))}
          />
          <StreamingOutput isVisible={isStreaming} />
        </div>
        <ChatInput onSend={handleSend} isStreaming={isStreaming} />
      </div>
      <ArtifactHistory artifacts={artifacts} />
    </div>
  )
}
