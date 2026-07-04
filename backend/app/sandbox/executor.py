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


def build_tool_result_string(exec_result: dict) -> str:
    parts = []
    if exec_result["stdout"]:
        parts.append(exec_result["stdout"])
    if exec_result["stderr"]:
        parts.append("[execution produced an error]")
    if exec_result["images"]:
        count = len(exec_result["images"])
        parts.append(f"[{count} chart{'s' if count > 1 else ''} generated]")
    return "\n".join(parts) if parts else "(no output)"
