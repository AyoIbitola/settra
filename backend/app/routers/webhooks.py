import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.config import settings
from app.db import get_session
from app.models.webhook_event import WebhookEvent

# NOTE: The import below assumes celery is running and tasks are available.
# We will use .delay() to trigger Celery.
from app.workers.tasks import process_webhook_event

router = APIRouter(tags=["Webhooks"])

@router.post("/webhooks/bitnob")
async def bitnob_webhook(request: Request):
    """
    Fast-ack webhook receiver for Bitnob.
    Verifies HMAC-SHA512 signature, dedupes, persists event, and hands off to Celery.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-bitnob-signature", "")

    if not settings.BITNOB_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    expected = hmac.new(
        settings.BITNOB_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event")
    data = payload.get("data", {})
    
    # Confirm field name consistency: Check event_id then fallback to id
    event_id = data.get("event_id") or data.get("id")

    if not event_id:
        # Cannot deduplicate without an ID. We ack to prevent infinite retries.
        return {"status": "ok", "detail": "Missing event ID, ignored."}

    # Use a fresh context manager for DB
    async for db in get_session():
        existing = await db.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        )
        if existing.scalar_one_or_none() is not None:
            return {"status": "ok"}  # already processed, ack without reprocessing

        webhook_row = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            raw_payload=payload,
            signature_valid=True,
        )
        db.add(webhook_row)
        await db.commit()
        await db.refresh(webhook_row)

        # Hand off to Celery processing queue.
        process_webhook_event.delay(str(webhook_row.id))

        return {"status": "ok"}
