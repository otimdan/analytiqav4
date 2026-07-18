import re
import asyncio
from e2b_code_interpreter import Sandbox

from app.config import MAX_RETRY_ATTEMPTS
from app.sandbox.executor import execute_code

KNOWN_PATTERNS = [
    (r"KeyError", "A column name is wrong or doesn't exist. Use df.columns.tolist() to check available columns before accessing them. Match the exact case and spelling."),
    (r"ValueError.*(could not convert string to float|invalid literal for int)", "A column contains non-numeric characters (e.g. '$', ',', '%', or blanks). Clean it first, e.g. df['col'] = pd.to_numeric(df['col'].astype(str).str.replace(r'[^0-9.\\-]', '', regex=True), errors='coerce'), then dropna()."),
    (r"ModuleNotFoundError|ImportError", "An import failed. Available libraries: pandas, numpy, scipy, scikit-learn, matplotlib, seaborn. statsmodels is NOT available — for regression use scipy.stats or scikit-learn instead. Do NOT pip install anything."),
    (r"MemoryError", "The operation ran out of memory. Try sampling the dataframe first: df = df.sample(n=10000) before running this operation."),
    # Empty / degenerate data — very common after dropna() or an over-narrow filter.
    (r"(zero-size array|empty|need at least|0 sample|Length of values|all-?NaN|cannot convert float NaN)", "After dropping missing values a column or group is empty (or all-NaN). Print the non-null counts per column/group first (df[cols].dropna().shape, df.groupby(g).size()) and only proceed if each has enough rows."),
    # pandas API drift (removed methods across versions) — deterministic fix.
    (r"AttributeError.*(append|iteritems|is_categorical_dtype|get_dtype_counts)", "That pandas method was removed in recent versions. Use the current API: pd.concat instead of .append, .items() instead of .iteritems(), isinstance(dtype, pd.CategoricalDtype) instead of is_categorical_dtype."),
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
