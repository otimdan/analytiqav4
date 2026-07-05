import json

from fastapi import APIRouter, Depends, Request, HTTPException

from app.auth import get_current_user, AuthUser
from app.config import (
    DODO_API_KEY, DODO_WEBHOOK_KEY, DODO_ENVIRONMENT, DODO_PRO_PRODUCT_ID, APP_URL,
)
from app.db.aio import run_db
from app.db import billing
from app.logging_config import logger

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout")
async def create_checkout(user: AuthUser = Depends(get_current_user)) -> dict:
    """Create a Dodo hosted checkout session for the Pro plan and return its URL."""
    if not DODO_API_KEY or not DODO_PRO_PRODUCT_ID:
        raise HTTPException(status_code=503, detail="Billing is not configured on the server.")

    def _create() -> str:
        try:
            from dodopayments import DodoPayments  # lazy: app boots without the SDK
        except ImportError:
            raise HTTPException(status_code=503, detail="Billing SDK is not installed.")
        client = DodoPayments(bearer_token=DODO_API_KEY, environment=DODO_ENVIRONMENT or "test_mode")
        session = client.checkout_sessions.create(
            product_cart=[{"product_id": DODO_PRO_PRODUCT_ID, "quantity": 1}],
            customer={"email": user.email or "", "name": user.email or "User"},
            return_url=f"{APP_URL}/app?checkout=success",
            metadata={"user_id": user.id},
        )
        url = getattr(session, "checkout_url", None)
        if not url and isinstance(session, dict):
            url = session.get("checkout_url")
        if not url:
            raise HTTPException(status_code=502, detail="Checkout session had no URL.")
        return url

    try:
        checkout_url = await run_db(_create)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Dodo checkout failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")

    return {"checkout_url": checkout_url}


@router.post("/portal")
async def customer_portal(user: AuthUser = Depends(get_current_user)) -> dict:
    """Create a Dodo customer-portal session so the user can manage/cancel their plan."""
    if not DODO_API_KEY:
        raise HTTPException(status_code=503, detail="Billing is not configured on the server.")

    customer_id = await run_db(billing.get_customer_id, user.id)
    if not customer_id:
        raise HTTPException(status_code=409, detail="No subscription found for this account.")

    def _create() -> str:
        try:
            from dodopayments import DodoPayments  # lazy import
        except ImportError:
            raise HTTPException(status_code=503, detail="Billing SDK is not installed.")
        client = DodoPayments(bearer_token=DODO_API_KEY, environment=DODO_ENVIRONMENT or "test_mode")
        session = client.customers.customer_portal.create(customer_id, return_url=f"{APP_URL}/app")
        url = getattr(session, "link", None)
        if not url:
            raise HTTPException(status_code=502, detail="Portal session had no link.")
        return url

    try:
        portal_url = await run_db(_create)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Dodo portal failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not open the billing portal. Please try again.")

    return {"portal_url": portal_url}


@router.post("/webhook")
async def dodo_webhook(request: Request) -> dict:
    """Verify a Dodo webhook (Standard Webhooks) and apply the plan change."""
    if not DODO_WEBHOOK_KEY:
        raise HTTPException(status_code=503, detail="Billing webhook is not configured.")

    raw = await request.body()
    headers = {
        "webhook-id": request.headers.get("webhook-id", ""),
        "webhook-timestamp": request.headers.get("webhook-timestamp", ""),
        "webhook-signature": request.headers.get("webhook-signature", ""),
    }

    try:
        from standardwebhooks import Webhook  # lazy import
    except ImportError:
        raise HTTPException(status_code=503, detail="Webhook verification library not installed.")

    try:
        wh = Webhook(DODO_WEBHOOK_KEY)
        payload = wh.verify(raw, headers)  # raises on bad signature
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Rejected Dodo webhook: %s", e)
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    if isinstance(payload, (bytes, str)):
        payload = json.loads(payload)

    event_type = (payload or {}).get("type", "")
    data = (payload or {}).get("data", {}) or {}
    await run_db(billing.apply_event, event_type, data)
    return {"ok": True}
