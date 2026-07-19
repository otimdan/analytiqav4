// Sentry init for the Edge runtime (middleware, edge routes).
// Env-based + inert unless NEXT_PUBLIC_SENTRY_DSN is set (consistent with the
// client + server configs).
import * as Sentry from "@sentry/nextjs"

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  enabled: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
})
