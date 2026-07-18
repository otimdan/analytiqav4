"""Run sandbox scripts locally (no E2B) so golden tests exercise the REAL code.

The profiler, the assumption-check script, and the test templates all read
'/home/user/data.csv' and print their results. Here we write a fixture DataFrame
to a temp CSV, swap that path into the script, exec it, and capture stdout —
i.e. the exact same code that runs inside E2B, minus the network. This lets the
golden suite validate profiling → typing → assumption checks → test selection →
execution end to end, deterministically, in CI.
"""
import io
import os
import json
import tempfile
import contextlib

import pandas as pd

_DATA_PATH = "/home/user/data.csv"


def write_csv(df: pd.DataFrame) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    df.to_csv(path, index=False)
    return path


def run_script(script: str, csv_path: str) -> str:
    """Exec a sandbox script locally with the data path swapped; return stdout."""
    local = script.replace(_DATA_PATH, csv_path)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(local, "<sandbox>", "exec"), {})
    return buf.getvalue()


def profile_locally(df: pd.DataFrame) -> dict:
    """Run the REAL profiler script (app.profiling.profiler.PROFILE_SCRIPT)."""
    from app.profiling.profiler import PROFILE_SCRIPT
    path = write_csv(df)
    try:
        out = run_script(PROFILE_SCRIPT, path)
        return json.loads(out.strip().splitlines()[-1])
    finally:
        os.remove(path)


def live_checks_locally(df: pd.DataFrame, var_a: str, var_b: str, type_a: str, type_b: str) -> dict:
    """Run the REAL live assumption-check script and parse it (no E2B)."""
    from app.stats_engine.assumption_checks import build_check_script_for, parse_checks, _blank_checks
    script = build_check_script_for(var_a, var_b, type_a, type_b)
    if script is None:
        return _blank_checks()
    path = write_csv(df)
    try:
        return parse_checks(run_script(script, path))
    finally:
        os.remove(path)


def run_template_locally(df: pd.DataFrame, template_key: str, col_a: str, col_b: str) -> str:
    """Render and execute a REAL deterministic test template; return its stdout."""
    from app.stats_engine.registry import render_template
    code = render_template(template_key, col_a=col_a, col_b=col_b)
    path = write_csv(df)
    try:
        return run_script(code, path)
    finally:
        os.remove(path)


def live_select(df: pd.DataFrame, var_a: str, var_b: str) -> dict:
    """The full production selection chain on real data: profile → resolve →
    live assumption checks → decide. Returns the selection result dict."""
    from app.stats_engine.test_selector import resolve_pair, decide_test
    profile = profile_locally(df)
    resolved = resolve_pair(var_a, var_b, profile)
    if not resolved.get("ok"):
        return resolved
    checks = live_checks_locally(df, resolved["var_a"], resolved["var_b"], resolved["type_a"], resolved["type_b"])
    return decide_test(resolved, checks)
