"""
Webhook receiver for Busha payment notifications.
PRD Section 8 — fast-ack, HMAC-SHA256 (base64) signature verification,
dedup via composite key, hand-off to Celery.
"""
import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.config import settings
from app.db import get_session
from app.models.webhook_event import WebhookEvent
from app.workers.tasks import process_webhook_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Webhooks"])


@router.post("/webhooks/busha")
async def busha_webhook(request: Request):
    """
    Fast-ack webhook receiver for Busha.
    Verifies HMAC-SHA256 (base64-encoded) signature, dedupes via composite key,
    persists raw event row, and hands off to Celery — all synchronous work done
    before returning 200 is intentionally minimal.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-bu-signature", "")

    if not settings.BUSHA_WEBHOOK_SECRET:
        logger.error("BUSHA_WEBHOOK_SECRET is not configured.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    # PRD §8.2: HMAC-SHA256 over the raw bytes, base64-encoded (NOT hex).
    mac = hmac.new(
        settings.BUSHA_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    )
    expected = base64.b64encode(mac.digest()).decode()

    # Constant-time comparison — prevents timing-side-channel attacks.
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event")
    data = payload.get("data", {})

    # PRD §8.1: composite dedup key — no single canonical event_id in Busha payloads.
    object_id = data.get("id")
    timestamp = data.get("updated_at") or data.get("created_at")

    if not object_id:
        logger.warning("Busha webhook received with no data.id — cannot deduplicate. Acking to prevent retries.")
        return {"status": "ok"}

    dedup_key = f"{object_id}:{event_type}:{timestamp}"

    async for db in get_session():
        existing = await db.execute(
            select(WebhookEvent).where(WebhookEvent.event_dedup_key == dedup_key)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info(f"Duplicate webhook ignored: {dedup_key}")
            return {"status": "ok"}

        webhook_row = WebhookEvent(
            event_dedup_key=dedup_key,
            event_type=event_type,
            raw_payload=payload,
            signature_valid=True,
        )
        db.add(webhook_row)
        await db.commit()
        await db.refresh(webhook_row)

        # Hand off to Celery — do not process synchronously.
        process_webhook_event.delay(str(webhook_row.id))
        logger.info(f"Busha webhook '{event_type}' queued. dedup_key={dedup_key}")

    return {"status": "ok"}
