// Sentry init for the browser (Next 15.3+/16 client instrumentation hook — Next
// loads this automatically on the client). Inert unless NEXT_PUBLIC_SENTRY_DSN is set.
import * as Sentry from "@sentry/nextjs"

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  enabled: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
  tracesSampleRate: 0.1, // light sampling; Session Replay intentionally left off (quota)
  sendDefaultPii: false,
})

// Instrument app-router navigations for tracing/breadcrumbs.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart
