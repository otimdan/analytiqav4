"use client"
import { useEffect, useRef } from "react"
import type { Message } from "@/lib/types"
import { DisambiguationPrompt } from "./DisambiguationPrompt"
import { GuidanceSuggestion } from "./GuidanceSuggestion"
import { FeedbackRating } from "./FeedbackRating"
import { Markdown } from "./Markdown"
import { CodeExecutionBlock } from "./CodeExecutionBlock"
import { ChartCard } from "@/components/artifacts/ChartCard"
import { ReportCard } from "@/components/report/ReportCard"

interface MessageListProps {
  messages: Message[]
  sessionId: string
  isStreaming: boolean
  onOptionSelect: (messageId: string, option: string) => void
  onGuidanceAccept: (messageId: string) => void
  onGuidanceRun: (query: string) => void
  onFeedbackDismiss: (messageId: string) => void
}

export function MessageList({ messages, sessionId, isStreaming, onOptionSelect, onGuidanceAccept, onGuidanceRun, onFeedbackDismiss }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, isStreaming])

  return (
    <div className="flex flex-col gap-4 px-4 py-6">
      {messages.map((message) => (
        <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
          <div className={`max-w-[80%] ${message.role === "user" ? "rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-3 text-white" : "w-full"}`}>
            {message.content && (
              message.role === "user"
                ? <p className="whitespace-pre-wrap text-sm text-white">{message.content}</p>
                : <Markdown>{message.content}</Markdown>
            )}
            {message.role === "assistant" && message.executions && message.executions.length > 0 && (
              <CodeExecutionBlock executions={message.executions} />
            )}
            {message.role === "assistant" && message.engine_verified !== undefined && (
              <VerificationBadge verified={message.engine_verified} testName={message.verified_test_name} />
            )}
            {message.images.map((img, i) => <ChartCard key={i} imageBase64={img.src} caption={img.caption} />)}
            {message.report && <ReportCard report={message.report} />}
            {message.disambiguation && (
              <DisambiguationPrompt question={message.disambiguation.question} options={message.disambiguation.options} onSelect={(opt) => onOptionSelect(message.id, opt)} />
            )}
            {message.guidance_suggestion && message.role === "assistant" && (
              <GuidanceSuggestion
                suggestion={message.guidance_suggestion}
                style={message.guidance_style}
                nextAction={message.guidance_next_action}
                onRun={onGuidanceRun}
              />
            )}
            {message.show_feedback && message.role === "assistant" && (message.server_message_id || message.id) && (
              <FeedbackRating sessionId={sessionId} messageId={message.server_message_id ?? message.id} onDismiss={() => onFeedbackDismiss(message.id)} />
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

// Tells the user whether a statistical result came from the verified test
// library (assumption-checked, deterministic) or the LLM-assisted tier.
function VerificationBadge({ verified, testName }: { verified: boolean; testName?: string }) {
  if (verified) {
    return (
      <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5" /></svg>
        Verified test{testName ? ` · ${testName}` : ""}
      </div>
    )
  }
  return (
    <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
      Not from verified library
    </div>
  )
}
