import asyncio
from typing import Any, Callable, TypeVar

T = TypeVar("T")


async def run_db(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking (synchronous) DB helper in a worker thread.

    supabase-py is synchronous: every `.execute()` is a blocking HTTP round-trip.
    When those run directly inside an async request handler they stall the whole
    event loop, so concurrent requests can't make progress until the DB call
    returns. Wrapping the call in a thread keeps the loop free.

    Usage:
        session = await run_db(get_session, session_id)
    """
    return await asyncio.to_thread(fn, *args, **kwargs)
