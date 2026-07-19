"use client"
// Root error boundary — reports uncaught render errors to Sentry and shows a
// minimal fallback. Only triggers for errors in the root layout/template.
import * as Sentry from "@sentry/nextjs"
import { useEffect } from "react"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        <h2 className="text-lg font-semibold text-gray-800">Something went wrong.</h2>
        <p className="text-sm text-gray-500">An unexpected error occurred. Please try again.</p>
        <button
          onClick={() => reset()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Try again
        </button>
      </body>
    </html>
  )
}
