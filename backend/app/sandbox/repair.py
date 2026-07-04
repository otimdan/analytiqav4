import re
import asyncio
from e2b_code_interpreter import Sandbox

from app.config import MAX_RETRY_ATTEMPTS
from app.sandbox.executor import execute_code

KNOWN_PATTERNS = [
    (r"KeyError", "A column name is wrong or doesn't exist. Use df.columns.tolist() to check available columns before accessing them."),
    (r"ValueError.*could not convert string to float", "A column contains non-numeric values like '$' or ',' characters. Clean the column first: df['col'] = df['col'].str.replace(',','').str.replace('$','').astype(float)"),
    (r"ModuleNotFoundError", "An import failed. Only standard data science libraries are available: pandas, numpy, matplotlib, seaborn, scipy, statsmodels."),
    (r"MemoryError", "The operation ran out of memory. Try sampling the dataframe first: df = df.sample(n=10000) before running this operation."),
]


def extract_error_summary(stderr: str) -> str:
    lines = stderr.strip().split("\n")
    exception_line = ""
    for line in reversed(lines):
        if line.strip():
            exception_line = line.strip()
            break

    user_code_line = ""
    for i, line in enumerate(lines):
        if 'File "/home/user/' in line and i + 1 < len(lines):
            user_code_line = lines[i + 1].strip()

    if user_code_line:
        return f"{exception_line} (at: {user_code_line})"
    return exception_line


def check_known_patterns(error_summary: str, code: str) -> str | None:
    for pattern, hint in KNOWN_PATTERNS:
        if re.search(pattern, error_summary, re.IGNORECASE):
            return hint
    return None


async def attempt_repair(sbx: Sandbox, original_code: str, stderr: str, llm_repair_fn, attempt: int = 1) -> dict:
    if attempt > MAX_RETRY_ATTEMPTS:
        return {"stdout": "", "stderr": stderr, "images": [], "success": False, "repair_exhausted": True}

    error_summary = extract_error_summary(stderr)
    hint = check_known_patterns(error_summary, original_code)
    temperature = [0.1, 0.3, 0.6][min(attempt - 1, 2)]

    fixed_code = await llm_repair_fn(
        original_code=original_code,
        error_summary=error_summary,
        hint=hint,
        temperature=temperature,
    )

    result = await execute_code(sbx, fixed_code)

    if result["success"]:
        result["repaired_code"] = fixed_code
        return result

    return await attempt_repair(
        sbx=sbx,
        original_code=fixed_code,
        stderr=result["stderr"],
        llm_repair_fn=llm_repair_fn,
        attempt=attempt + 1,
    )
