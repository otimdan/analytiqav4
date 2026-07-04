import asyncio
from e2b_code_interpreter import Sandbox

from app.config import E2B_API_KEY, SANDBOX_TIMEOUT_SECONDS
from app.db.sessions import get_session, update_sandbox_id, clear_sandbox_id
from app.db.artifacts import get_code_replay_sequence
from app.sandbox.chart_theme import CHART_THEME_BOOTSTRAP
from app.logging_config import logger


async def _apply_chart_theme(sbx: Sandbox) -> None:
    """Set the shared matplotlib theme in the sandbox kernel. rcParams persist
    for the kernel's lifetime, so this only needs to run once per connection —
    it's cheap and idempotent, so we run it on both create and reconnect."""
    try:
        await asyncio.to_thread(sbx.run_code, CHART_THEME_BOOTSTRAP)
    except Exception as e:
        logger.warning("Could not apply chart theme: %s", e)


async def _ensure_dataset_mounted(sbx: Sandbox, session) -> None:
    """Guarantee /home/user/data.csv exists in the sandbox.

    E2B sandboxes expire and their filesystem is wiped even when `connect`
    still succeeds, so we can't trust a live reconnect to still have the file.
    Re-writing from the durable dataset_csv is idempotent and cheap.
    """
    if not session.dataset_csv:
        return
    try:
        exists = await asyncio.to_thread(sbx.files.exists, "/home/user/data.csv")
    except Exception:
        exists = False
    if not exists:
        await asyncio.to_thread(sbx.files.write, "/home/user/data.csv", session.dataset_csv)


async def get_or_create_sandbox(session_id: str) -> Sandbox:
    session = await asyncio.to_thread(get_session, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    if session.sandbox_id:
        try:
            sbx = await asyncio.to_thread(Sandbox.connect, session.sandbox_id, api_key=E2B_API_KEY)
            await asyncio.to_thread(sbx.run_code, "1+1")
            await _ensure_dataset_mounted(sbx, session)
            await _apply_chart_theme(sbx)
            return sbx
        except Exception:
            pass

    return await _create_and_mount(session_id)


async def _create_and_mount(session_id: str) -> Sandbox:
    session = await asyncio.to_thread(get_session, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    sbx: Sandbox = await asyncio.to_thread(
        Sandbox.create,
        timeout=SANDBOX_TIMEOUT_SECONDS,
        metadata={"session": session_id},
        api_key=E2B_API_KEY,
    )

    await asyncio.to_thread(update_sandbox_id, session_id, sbx.sandbox_id)
    await _apply_chart_theme(sbx)

    if session.dataset_csv:
        await asyncio.to_thread(sbx.files.write, "/home/user/data.csv", session.dataset_csv)

    replay_sequence = await asyncio.to_thread(get_code_replay_sequence, session_id)

    for code_block in replay_sequence:
        try:
            await asyncio.to_thread(sbx.run_code, code_block)
        except Exception as e:
            logger.warning("Replay step failed for session %s: %s", session_id, e)

    return sbx


async def terminate_sandbox(session_id: str) -> None:
    session = await asyncio.to_thread(get_session, session_id)
    if not session or not session.sandbox_id:
        return
    try:
        sbx = await asyncio.to_thread(Sandbox.connect, session.sandbox_id, api_key=E2B_API_KEY)
        await asyncio.to_thread(sbx.close)
    except Exception:
        pass
    # Keep dataset_csv so a page refresh (which fires /close) doesn't destroy
    # the uploaded data — only release the sandbox handle.
    await asyncio.to_thread(clear_sandbox_id, session_id)
