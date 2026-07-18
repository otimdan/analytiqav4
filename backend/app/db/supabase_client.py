import threading
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

# One Supabase client PER THREAD (not a single global).
#
# supabase-py is synchronous and we fan DB calls out across worker threads via
# `run_db` (asyncio.to_thread). The client's underlying httpx connection uses
# HTTP/2, which multiplexes every request over a single socket. httpx is safe
# used within one thread, but sharing one HTTP/2 connection across threads races
# the h2 state machine — the frontend firing /artifacts, /stages and /state at
# once would terminate the connection (RemoteProtocolError, error_code 1) and
# 500. A thread-local client gives each worker its own connection pool, so no
# two threads ever touch the same connection. The to_thread pool is small and
# threads are reused, so only a handful of clients are ever created.
_local = threading.local()


def get_client() -> Client:
    client = getattr(_local, "client", None)
    if client is None:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        _local.client = client
    return client
