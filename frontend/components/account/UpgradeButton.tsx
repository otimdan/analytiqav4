"use client"
import { useState } from "react"
import { Sparkles } from "lucide-react"
import { createCheckout } from "@/lib/api"
import { Button } from "@/components/ui/button"

// Shown when the user is on the free plan. Kicks off Dodo hosted checkout and
// redirects the browser to the returned checkout URL.
export function UpgradeButton({ size = "sm", className }: { size?: "sm" | "default"; className?: string }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  async function upgrade() {
    setLoading(true)
    setError(false)
    try {
      const { checkout_url } = await createCheckout()
      window.location.href = checkout_url
    } catch {
      setError(true)
      setLoading(false)
    }
  }

  return (
    <Button
      size={size}
      onClick={upgrade}
      disabled={loading}
      className={className}
      title={error ? "Couldn't start checkout — try again" : "Upgrade to Pro"}
    >
      <Sparkles className="size-4" />
      {loading ? "Starting…" : error ? "Try again" : "Upgrade"}
    </Button>
  )
}
