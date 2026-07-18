"""Optional observability: Sentry error tracking + PostHog product analytics.

Design rules (so this can ship dark and be switched on later without risk):
  1. **Inert by default.** With no SENTRY_DSN / POSTHOG_API_KEY set, every function
     here is a no-op. Local and CI runs need zero configuration.
  2. **Never breaks a request.** All capture/identify calls swallow their own
     errors — telemetry failing must never surface to a user or fail an analysis.
  3. **Degrades if the package is missing.** Imports are guarded, so the app still
     boots even before `pip install` picks up sentry-sdk / posthog.
  4. **No dataset content leaves the box.** We send event names + coarse metadata
     (regime, verified flag, test name) keyed by user/session id — never column
     names, values, hypotheses, or CSV data.
"""
from typing import Any, Optional

from app.config import (
    SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_TRACES_SAMPLE_RATE,
    POSTHOG_API_KEY, POSTHOG_HOST,
)
from app.logging_config import logger

_posthog_client = None  # set on successful init; stays None when disabled


def init_observability() -> None:
    """Initialise Sentry and PostHog if (and only if) they're configured.
    Safe to call once at startup; safe to call when nothing is configured."""
    _init_sentry()
    _init_posthog()


def _init_sentry() -> None:
    if not SENTRY_DSN:
        return
    try:
        import sentry_sdk
        # sentry-sdk auto-enables its Starlette/FastAPI integration when FastAPI is
        # installed, so unhandled request exceptions are captured without wiring.
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,  # don't attach request bodies / user data
        )
        logger.info("Sentry error tracking enabled (env=%s)", SENTRY_ENVIRONMENT)
    except Exception as e:  # bad DSN, missing package, etc. — never fatal
        logger.warning("Sentry init skipped: %s", e)


def _init_posthog() -> None:
    global _posthog_client
    if not POSTHOG_API_KEY:
        return
    try:
        from posthog import Posthog
        _posthog_client = Posthog(
            project_api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
            # Server-side events are authoritative facts, not behavioural guesses,
            # so don't let PostHog's geo/UA autocapture enrich (and PII-taint) them.
            enable_exception_autocapture=False,
        )
        logger.info("PostHog product analytics enabled (host=%s)", POSTHOG_HOST)
    except Exception as e:
        logger.warning("PostHog init skipped: %s", e)


def capture_event(distinct_id: Optional[str], event: str, properties: Optional[dict[str, Any]] = None) -> None:
    """Record a product-analytics event. No-op when PostHog is disabled. Never
    raises. `distinct_id` should be the user id (falls back to an anonymous marker
    so signed-out/anonymous sessions still count in the funnel)."""
    if _posthog_client is None:
        return
    try:
        _posthog_client.capture(
            distinct_id=distinct_id or "anonymous",
            event=event,
            properties=properties or {},
        )
    except Exception as e:
        logger.debug("PostHog capture failed (ignored): %s", e)


def capture_exception(error: BaseException, context: Optional[dict[str, Any]] = None) -> None:
    """Manually report a handled exception to Sentry (unhandled ones are captured
    automatically). No-op when Sentry is disabled. Never raises."""
    if not SENTRY_DSN:
        return
    try:
        import sentry_sdk
        if context:
            with sentry_sdk.push_scope() as scope:
                for k, v in context.items():
                    scope.set_tag(k, v)
                sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_exception(error)
    except Exception as e:
        logger.debug("Sentry capture failed (ignored): %s", e)


def shutdown_observability() -> None:
    """Flush buffered PostHog events on shutdown so nothing is lost."""
    if _posthog_client is not None:
        try:
            _posthog_client.shutdown()
        except Exception:
            pass
