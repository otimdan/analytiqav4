import base64
import asyncio
from e2b_code_interpreter import Sandbox


async def execute_code(sbx: Sandbox, code: str) -> dict:
    execution = await asyncio.to_thread(sbx.run_code, code)
    result = {"stdout": "", "stderr": "", "images": [], "success": True}

    logs = execution.logs
    if hasattr(logs, "stdout") and logs.stdout:
        result["stdout"] = "".join(logs.stdout)
    if hasattr(logs, "stderr") and logs.stderr:
        result["stderr"] = "".join(logs.stderr)
        result["success"] = False

    for r in execution.results:
        if hasattr(r, "png") and r.png:
            result["images"].append(r.png)

    if not result["images"]:
        try:
            img_bytes = await asyncio.to_thread(sbx.files.read, "/home/user/output.png", format="bytes")
            result["images"].append(base64.b64encode(img_bytes).decode())
            await asyncio.to_thread(sbx.run_code, "import os; os.remove('/home/user/output.png')")
        except Exception:
            pass

    return result


# Tool results are re-sent with every subsequent model call, so an unbounded
# `print(df.to_string())` compounds: one 40-column dump early in a session is
# paid for on every later step, crowds out the conversation, and degrades the
# model's replies to the point of returning nothing. Only the model's copy is
# capped — the user still sees full output via _format_execution_output.
_MAX_TOOL_OUTPUT_CHARS = 3000


def _truncate_for_model(text: str, limit: int = _MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit * 3 // 4]
    tail = text[-(limit // 4):]
    dropped = len(text) - len(head) - len(tail)
    return (
        f"{head}\n\n[... {dropped:,} characters truncated. Print summaries "
        f"(shape, head, aggregates) rather than whole tables ...]\n\n{tail}"
    )


def build_tool_result_string(exec_result: dict) -> str:
    parts = []
    if exec_result["stdout"]:
        parts.append(_truncate_for_model(exec_result["stdout"]))
    if exec_result["stderr"]:
        parts.append("[execution produced an error]")
    if exec_result["images"]:
        count = len(exec_result["images"])
        parts.append(f"[{count} chart{'s' if count > 1 else ''} generated]")
    return "\n".join(parts) if parts else "(no output)"
