"use client"
import { Suspense, useEffect } from "react"
import { usePathname, useSearchParams } from "next/navigation"
import posthog from "posthog-js"
import { PostHogProvider } from "posthog-js/react"
import { initClientObservability, posthogEnabled } from "@/lib/analytics"

// Manual pageview capture for app-router client navigations (SPA route changes
// don't trigger a full page load). Wrapped in Suspense because useSearchParams
// suspends during prerender.
function PageviewTracker() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  useEffect(() => {
    if (!posthogEnabled || !pathname) return
    const qs = searchParams?.toString()
    const url = window.origin + pathname + (qs ? `?${qs}` : "")
    posthog.capture("$pageview", { $current_url: url })
  }, [pathname, searchParams])
  return null
}

export function Providers({ children }: { children: React.ReactNode }) {
  // Runs synchronously before child effects, so PostHog is ready before the
  // first pageview fires. No-op unless the keys are configured.
  initClientObservability()

  const tree = (
    <>
      <Suspense fallback={null}>
        <PageviewTracker />
      </Suspense>
      {children}
    </>
  )

  // Only mount the provider when PostHog is actually configured (otherwise the
  // client was never init'd). Sentry needs no provider.
  return posthogEnabled ? <PostHogProvider client={posthog}>{tree}</PostHogProvider> : tree
}
