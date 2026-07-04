from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import session, query, feedback, health, artifacts
from app.logging_config import setup_logging

import app.config  # noqa: F401 — triggers startup validation


def create_app() -> FastAPI:
    setup_logging()
    application = FastAPI(
        title="Analytika API",
        version="1.0.0",
        description="AI-powered research data analysis platform for undergraduate and postgraduate researchers.",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(session.router)
    application.include_router(query.router)
    application.include_router(feedback.router)
    application.include_router(health.router)
    application.include_router(artifacts.router)

    return application


app = create_app()
