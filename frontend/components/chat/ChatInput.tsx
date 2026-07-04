"use client"
import { useState, useRef, useCallback } from "react"
import type { KeyboardEvent } from "react"

interface ChatInputProps {
  onSend: (message: string) => void
  isStreaming: boolean
  placeholder?: string
}

export function ChatInput({ onSend, isStreaming, placeholder = "Ask anything about your data…" }: ChatInputProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed) return
    onSend(trimmed)
    setValue("")
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }, [value, onSend])

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
  }, [handleSend])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    const el = e.target
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 200) + "px"
  }, [])

  return (
    <div className="flex items-end gap-2 border-t border-gray-200 bg-white p-4">
      <textarea ref={textareaRef} value={value} onChange={handleChange} onKeyDown={handleKeyDown}
        placeholder={placeholder} rows={1}
        className="flex-1 resize-none rounded-xl border border-gray-300 bg-gray-50 px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
      <button onClick={handleSend} disabled={!value.trim()}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40 transition-colors">
        {isStreaming
          ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          : <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
              <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
            </svg>}
      </button>
    </div>
  )
}
