// Client-side observability: PostHog product analytics + Sentry error tracking.
//
// Inert by default: NEXT_PUBLIC_POSTHOG_KEY / NEXT_PUBLIC_SENTRY_DSN are inlined
// at build time, so with neither set every function here is a no-op and no
// network calls are made. Nothing about the app changes when they're unset.
//
// No PII: we don't attach dataset content. PostHog autocapture records UI
// interactions and pageviews; explicit events carry only coarse metadata.
import posthog from "posthog-js"
import * as Sentry from "@sentry/react"

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com"
const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN

export const posthogEnabled = !!POSTHOG_KEY

let initialized = false

/** Initialise Sentry + PostHog once, on the client. Safe to call repeatedly. */
export function initClientObservability() {
  if (initialized || typeof window === "undefined") return
  initialized = true

  if (SENTRY_DSN) {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
      tracesSampleRate: 0, // errors only unless we turn on performance later
      sendDefaultPii: false,
    })
  }

  if (POSTHOG_KEY) {
    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      capture_pageview: false, // captured manually for app-router navigations
      capture_pageleave: true,
      autocapture: true,
    })
  }
}

/** Associate subsequent events with a signed-in user (merges the anonymous
 *  session). No-op when PostHog is disabled. */
export function identifyUser(userId: string, properties?: Record<string, unknown>) {
  if (!POSTHOG_KEY || !userId) return
  try {
    posthog.identify(userId, properties)
  } catch {
    /* analytics must never break the app */
  }
}

/** Reset identity on sign-out so the next user isn't merged into this one. */
export function resetAnalytics() {
  if (!POSTHOG_KEY) return
  try {
    posthog.reset()
  } catch {
    /* ignore */
  }
}

/** Fire a product-analytics event. No-op when PostHog is disabled. */
export function captureEvent(event: string, properties?: Record<string, unknown>) {
  if (!POSTHOG_KEY) return
  try {
    posthog.capture(event, properties)
  } catch {
    /* ignore */
  }
}
