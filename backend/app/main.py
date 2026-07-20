from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import session, query, feedback, health, artifacts, account, billing
from app.logging_config import setup_logging
from app.config import ALLOWED_ORIGINS
from app.observability import init_observability, shutdown_observability
from app.request_limits import BodySizeLimitMiddleware

import app.config  # noqa: F401 — triggers startup validation


@asynccontextmanager
async def _lifespan(application: FastAPI):
    yield
    # Flush buffered analytics on shutdown (no-op when PostHog is disabled).
    shutdown_observability()


def create_app() -> FastAPI:
    setup_logging()
    # Initialise Sentry BEFORE the app is built so its FastAPI integration can wrap
    # request handling. No-op unless SENTRY_DSN / POSTHOG_API_KEY are configured.
    init_observability()
    application = FastAPI(
        title="Analytika API",
        version="1.0.0",
        description="AI-powered research data analysis platform for undergraduate and postgraduate researchers.",
        lifespan=_lifespan,
    )

    # Middleware order: the LAST one added is the OUTERMOST. The body-size limit
    # is added first so CORS ends up wrapping it — otherwise its 413 would go out
    # without CORS headers and the browser would surface an opaque network error
    # instead of the message.
    application.add_middleware(BodySizeLimitMiddleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Session-Id"],
    )

    application.include_router(session.router)
    application.include_router(query.router)
    application.include_router(feedback.router)
    application.include_router(health.router)
    application.include_router(artifacts.router)
    application.include_router(account.router)
    application.include_router(billing.router)

    return application


app = create_app()
