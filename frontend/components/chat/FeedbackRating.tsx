"use client"
import { useState } from "react"
import { submitFeedback } from "@/lib/api"

export function FeedbackRating({ sessionId, messageId, onDismiss }: { sessionId: string; messageId: string; onDismiss: () => void }) {
  const [submitted, setSubmitted] = useState(false)
  const handleRate = async (rating: number) => {
    setSubmitted(true)
    try { await submitFeedback({ session_id: sessionId, message_id: messageId, rating }) } catch {}
    setTimeout(onDismiss, 800)
  }
  if (submitted) return <div className="mt-1 text-xs text-gray-400">Thanks for the feedback ✓</div>
  return (
    <div className="mt-2 flex items-center gap-2">
      <span className="text-xs text-gray-400">Was this helpful?</span>
      <div className="flex gap-0.5">
        {[1,2,3,4,5].map((star) => (
          <button key={star} onClick={() => handleRate(star)} className="text-lg leading-none text-gray-300 hover:text-amber-400 transition-colors">★</button>
        ))}
      </div>
      <button onClick={onDismiss} className="text-xs text-gray-300 hover:text-gray-500">skip</button>
    </div>
  )
}
