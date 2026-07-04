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
  suggestionMode: boolean
  isStreaming: boolean
  onOptionSelect: (messageId: string, option: string) => void
  onGuidanceAccept: (messageId: string) => void
  onGuidanceRun: (query: string) => void
  onFeedbackDismiss: (messageId: string) => void
}

export function MessageList({ messages, sessionId, suggestionMode, isStreaming, onOptionSelect, onGuidanceAccept, onGuidanceRun, onFeedbackDismiss }: MessageListProps) {
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
            {message.images.map((img, i) => <ChartCard key={i} imageBase64={img.src} caption={img.caption} />)}
            {message.report && <ReportCard report={message.report} />}
            {message.disambiguation && (
              <DisambiguationPrompt question={message.disambiguation.question} options={message.disambiguation.options} onSelect={(opt) => onOptionSelect(message.id, opt)} />
            )}
            {message.confirmation_prompt && (
              <DisambiguationPrompt question={message.confirmation_prompt} options={["Track as project", "No, just answer this"]} onSelect={(opt) => onOptionSelect(message.id, opt)} />
            )}
            {suggestionMode && message.guidance_suggestion && message.role === "assistant" && (
              <GuidanceSuggestion
                suggestion={message.guidance_suggestion}
                isHypothesisCandidate={message.is_hypothesis_candidate}
                nextAction={message.guidance_next_action}
                onAccept={() => onGuidanceAccept(message.id)}
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
