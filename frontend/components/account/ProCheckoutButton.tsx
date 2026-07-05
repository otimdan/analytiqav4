"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { createCheckout } from "@/lib/api"
import { Button } from "@/components/ui/button"

// Marketing "Get Pro" button. If signed in, starts Dodo checkout; if not, sends
// them to sign up first (they can upgrade from inside the app afterwards).
export function ProCheckoutButton({
  children,
  className,
  variant = "default",
}: {
  children: React.ReactNode
  className?: string
  variant?: "default" | "outline"
}) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  async function go() {
    setLoading(true)
    const supabase = createClient()
    const { data } = await supabase.auth.getUser()
    if (!data.user) {
      router.push("/signup")
      return
    }
    try {
      const { checkout_url } = await createCheckout()
      window.location.href = checkout_url
    } catch {
      // Billing may not be configured yet — fall back to the app, where the
      // upgrade button gives the same (and any error is surfaced there).
      setLoading(false)
      router.push("/app")
    }
  }

  return (
    <Button onClick={go} disabled={loading} variant={variant} className={className}>
      {loading ? "Starting…" : children}
    </Button>
  )
}
