import json
import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from uuid import uuid4
from datetime import datetime, timezone

from app.db.models import Session, QueryRequest
from app.db.sessions import get_session
from app.deps import get_current_session
from app.orchestrator.pipeline import process_message
from app.db.supabase_client import get_client

router = APIRouter(prefix="/query", tags=["query"])


@router.post("")
async def handle_query(req: QueryRequest, session: Session = Depends(get_current_session)) -> StreamingResponse:
    message_id = str(uuid4())
    now = datetime.now(timezone.utc)

    get_client().table("messages").insert({
        "id": message_id, "session_id": str(session.id),
        "role": "user", "content": req.message, "created_at": now.isoformat(),
    }).execute()

    recent_result = (
        get_client().table("messages").select("*")
        .eq("session_id", str(session.id)).order("created_at", desc=False).limit(20).execute()
    )

    from app.db.models import Message
    recent_messages = [Message(**row) for row in recent_result.data]
    user_messages = [m for m in recent_messages if m.role == "user"]
    is_first_reply = len(user_messages) == 1

    stream_buffer = _StreamingLeakBuffer()
    assistant_message_id = str(uuid4())

    async def event_stream():
        assembled_text = []
        assembled_regime = "exploratory"
        executions: list[dict] = []

        try:
            async for chunk in process_message(
                message=req.message, session=session, recent_messages=recent_messages,
                source_message_id=message_id, is_first_reply=is_first_reply,
            ):
                chunk_type = chunk.get("type", "text")
                if chunk_type == "text":
                    raw_text = chunk.get("content", "")
                    clean_text = stream_buffer.feed(raw_text)
                    if clean_text:
                        assembled_text.append(clean_text)
                        assembled_regime = chunk.get("regime", assembled_regime)
                        yield _sse_event({**chunk, "content": clean_text})
                else:
                    if chunk_type == "code_execution":
                        executions.append({"code": chunk.get("code", ""), "output": chunk.get("output", "")})
                    yield _sse_event(chunk)

            remaining = stream_buffer.flush()
            if remaining:
                assembled_text.append(remaining)
                yield _sse_event({"type": "text", "content": remaining, "regime": assembled_regime, "show_feedback": False})

        except Exception as e:
            yield _sse_event({"type": "error", "content": "Something went wrong processing your request. Please try again."})
            print(f"[query] Pipeline error: {e}")

        finally:
            if assembled_text or executions:
                full_response = "".join(assembled_text)
                get_client().table("messages").insert({
                    "id": assistant_message_id,
                    "session_id": str(session.id), "role": "assistant",
                    "content": full_response, "regime": assembled_regime,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
                # Persist executions in a separate update so a missing `executions`
                # column (before the migration is applied) can't break message saving.
                if executions:
                    try:
                        get_client().table("messages").update({"executions": executions}).eq("id", assistant_message_id).execute()
                    except Exception as e:
                        print(f"[query] Could not persist executions (apply the migration to enable): {e}")
            yield _sse_event({"type": "done", "message_id": assistant_message_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


class _StreamingLeakBuffer:
    _OPEN_MARKERS = ["<think>", "<thinking>", "[thinking]"]
    _CLOSE_MARKERS = ["</think>", "</thinking>", "[/thinking]"]

    def __init__(self):
        self._in_think = False
        self._held = ""

    def feed(self, chunk: str) -> str:
        self._held += chunk
        output = []
        while self._held:
            if not self._in_think:
                marker_pos, marker = self._find_marker(self._held, self._OPEN_MARKERS)
                if marker_pos == -1:
                    safe_len = max(0, len(self._held) - 20)
                    output.append(self._held[:safe_len])
                    self._held = self._held[safe_len:]
                    break
                else:
                    output.append(self._held[:marker_pos])
                    self._held = self._held[marker_pos + len(marker):]
                    self._in_think = True
            else:
                marker_pos, marker = self._find_marker(self._held, self._CLOSE_MARKERS)
                if marker_pos == -1:
                    break
                else:
                    self._held = self._held[marker_pos + len(marker):]
                    self._in_think = False
        return "".join(output)

    def flush(self) -> str:
        if self._in_think:
            self._held = ""
            self._in_think = False
            return ""
        result = self._held
        self._held = ""
        return result

    @staticmethod
    def _find_marker(text: str, markers: list[str]) -> tuple[int, str]:
        earliest_pos = -1
        earliest_marker = ""
        for marker in markers:
            pos = text.lower().find(marker.lower())
            if pos != -1 and (earliest_pos == -1 or pos < earliest_pos):
                earliest_pos = pos
                earliest_marker = marker
        return earliest_pos, earliest_marker
