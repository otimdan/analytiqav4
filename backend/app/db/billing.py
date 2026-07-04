"""Billing state on `profiles` + applying Dodo Payments webhook events.

The backend uses the Supabase service_role client. All functions are synchronous
(call via `run_db`). Plan enforcement lives in the pipeline/usage layer — this
module only records what Dodo tells us about a user's subscription.
"""
from typing import Any, Optional

from app.db.supabase_client import get_client
from app.logging_config import logger

# Dodo event types that grant / revoke Pro. Names kept broad to tolerate slight
# variations across Dodo's event vocabulary.
_ACTIVATE = {"subscription.active", "subscription.renewed", "payment.succeeded"}
_DEACTIVATE = {
    "subscription.cancelled", "subscription.canceled", "subscription.expired",
    "subscription.on_hold", "subscription.failed", "subscription.paused",
}


def set_plan(
    user_id: str,
    plan: str,
    status: Optional[str] = None,
    subscription_id: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> None:
    updates: dict[str, Any] = {"plan": plan}
    if status is not None:
        updates["subscription_status"] = status
    if subscription_id is not None:
        updates["dodo_subscription_id"] = subscription_id
    if customer_id is not None:
        updates["dodo_customer_id"] = customer_id
    client = get_client()
    # upsert so a profile row exists even if the signup trigger hasn't run
    client.table("profiles").upsert({"id": user_id, **updates}).execute()


def _lookup_user(subscription_id: Optional[str], customer_id: Optional[str]) -> Optional[str]:
    client = get_client()
    if subscription_id:
        res = client.table("profiles").select("id").eq("dodo_subscription_id", subscription_id).limit(1).execute()
        if res.data:
            return res.data[0]["id"]
    if customer_id:
        res = client.table("profiles").select("id").eq("dodo_customer_id", customer_id).limit(1).execute()
        if res.data:
            return res.data[0]["id"]
    return None


def _dig(data: dict, *keys: str) -> Optional[str]:
    """First non-empty value among top-level keys or nested customer/subscription."""
    for k in keys:
        v = data.get(k)
        if v:
            return v
    for nested in ("customer", "subscription", "data"):
        sub = data.get(nested)
        if isinstance(sub, dict):
            for k in keys:
                v = sub.get(k)
                if v:
                    return v
    return None


def apply_event(event_type: str, data: dict) -> None:
    """Map a verified Dodo webhook event to a plan change on the right user."""
    metadata = data.get("metadata") or {}
    user_id = metadata.get("user_id")
    subscription_id = _dig(data, "subscription_id", "id")
    customer_id = _dig(data, "customer_id")

    if not user_id:
        user_id = _lookup_user(subscription_id, customer_id)
    if not user_id:
        logger.warning("Dodo webhook %s: could not map to a user (sub=%s cust=%s)",
                       event_type, subscription_id, customer_id)
        return

    if event_type in _ACTIVATE:
        set_plan(user_id, "pro", status="active",
                 subscription_id=subscription_id, customer_id=customer_id)
        logger.info("Billing: user %s -> pro (%s)", user_id, event_type)
    elif event_type in _DEACTIVATE:
        set_plan(user_id, "free", status=event_type.split(".")[-1],
                 subscription_id=subscription_id, customer_id=customer_id)
        logger.info("Billing: user %s -> free (%s)", user_id, event_type)
    else:
        logger.info("Billing: ignoring event %s", event_type)
