"""Usage metering + plan lookups for tiered caps.

A "metered analysis" is one exploratory or confirmatory run (the compute-heavy
regimes that hit the LLM + sandbox). Each is one row in `usage_events`; a user's
monthly usage is the count of their rows since the start of the current calendar
month (UTC). Plans and their limits live in config.

All functions are synchronous (Supabase client); call them via `run_db`.
"""
from datetime import datetime, timezone

from app.db.supabase_client import get_client
from app.config import PLAN_LIMITS, DEFAULT_PLAN


def _month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def get_plan(user_id: str) -> str:
    client = get_client()
    res = client.table("profiles").select("plan").eq("id", user_id).limit(1).execute()
    if res.data:
        return res.data[0].get("plan") or DEFAULT_PLAN
    return DEFAULT_PLAN


def count_usage_this_month(user_id: str) -> int:
    client = get_client()
    res = (
        client.table("usage_events")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("created_at", _month_start_iso())
        .execute()
    )
    return res.count or 0


def record_usage(user_id: str, kind: str) -> None:
    client = get_client()
    client.table("usage_events").insert({"user_id": user_id, "kind": kind}).execute()


def get_usage_summary(user_id: str) -> dict:
    plan = get_plan(user_id)
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS[DEFAULT_PLAN])
    used = count_usage_this_month(user_id)
    return {"plan": plan, "used": used, "limit": limit, "remaining": max(0, limit - used)}
