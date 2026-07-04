import logging
import os
import sys

_configured = False


def setup_logging() -> None:
    """Configure root logging once, at app startup.

    Level is controlled by LOG_LEVEL (default INFO). Logs go to stdout so they
    show up in the terminal during dev and in container logs in production.
    """
    global _configured
    if _configured:
        return
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
    _configured = True


# Shared application logger. Import and use: `from app.logging_config import logger`.
logger = logging.getLogger("analytika")
