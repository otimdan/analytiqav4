// Sentry init for the Node.js server runtime (SSR, route handlers).
// Env-based + inert unless NEXT_PUBLIC_SENTRY_DSN is set (consistent with the
// client + edge configs). DSN is public (client-embedded), so env, not a secret.
import * as Sentry from "@sentry/nextjs"

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  enabled: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
  // 10% transaction sampling — keeps performance-monitoring quota low (the wizard
  // default of 1.0 traces every request). Raise for more perf data.
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
})
