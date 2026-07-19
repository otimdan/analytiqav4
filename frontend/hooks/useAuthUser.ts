"use client"
import { useEffect, useState } from "react"
import type { User } from "@supabase/supabase-js"
import { createClient } from "@/lib/supabase/client"
import { identifyUser, resetAnalytics } from "@/lib/analytics"

// Client-side current-user state, kept in sync with auth changes (login/logout).
export function useAuthUser() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createClient()
    // Tie analytics identity to the Supabase user id so client-side events merge
    // with the backend's user-keyed events (same distinct_id). No-op if PostHog
    // is disabled. Reset on sign-out so the next user isn't merged in.
    const syncAnalytics = (u: User | null) => {
      if (u) identifyUser(u.id)
      else resetAnalytics()
    }
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user)
      syncAnalytics(data.user)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
      syncAnalytics(session?.user ?? null)
    })
    return () => sub.subscription.unsubscribe()
  }, [])

  return { user, loading }
}
