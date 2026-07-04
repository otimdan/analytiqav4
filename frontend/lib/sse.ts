import type { StreamChunk } from "./types"

export type ChunkHandler = (chunk: StreamChunk) => void
export type ErrorHandler = (error: Error) => void
export type DoneHandler = () => void

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function streamQuery(
  sessionId: string,
  message: string,
  onChunk: ChunkHandler,
  onError: ErrorHandler,
  onDone: DoneHandler
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Id": sessionId },
      body: JSON.stringify({ session_id: sessionId, message }),
    })
  } catch {
    onError(new Error("Could not connect to the server. Check your connection and try again."))
    return
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }))
    onError(new Error(error.detail || "Request failed"))
    return
  }

  if (!response.body) {
    onError(new Error("No response body received."))
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        if (buffer.trim()) _processBuffer(buffer, onChunk)
        onDone()
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split("\n\n")
      buffer = parts.pop() || ""
      for (const part of parts) _processBuffer(part, onChunk)
    }
  } catch (err) {
    onError(err instanceof Error ? err : new Error("Stream reading failed."))
  } finally {
    reader.releaseLock()
  }
}

function _processBuffer(raw: string, onChunk: ChunkHandler): void {
  const lines = raw.trim().split("\n")
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const jsonStr = line.slice(6).trim()
      if (!jsonStr) continue
      try {
        const chunk = JSON.parse(jsonStr) as StreamChunk
        onChunk(chunk)
      } catch {
        console.warn("[sse] Failed to parse chunk:", jsonStr)
      }
    }
  }
}
