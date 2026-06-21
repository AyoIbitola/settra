import hashlib
import hmac
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import settings
from app.db import get_session
from app.main import app
from app.models.webhook_event import WebhookEvent


@pytest.mark.asyncio
async def test_webhook_valid_signature(test_session):
    settings.BITNOB_WEBHOOK_SECRET = "testsecret123"
    
    # Override FastAPI dependency to use our test session
    async def override_get_session():
        yield test_session
        
    app.dependency_overrides[get_session] = override_get_session
    
    try:
        payload = {
            "event": "stablecoin.usdc.received.success",
            "data": {
                "event_id": f"evt_{uuid.uuid4()}",
                "amount": "100.00"
            }
        }
        raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        signature = hmac.new(
            settings.BITNOB_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha512
        ).hexdigest()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/webhooks/bitnob",
                content=raw_body,
                headers={"x-bitnob-signature": signature}
            )
            
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        # Test session is same as app session, so we can do the DB assertion properly.
        result = await test_session.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == payload["data"]["event_id"])
        )
        event_row = result.scalar_one_or_none()
        assert event_row is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_invalid_signature():
    settings.BITNOB_WEBHOOK_SECRET = "testsecret123"
    
    payload = {
        "event": "stablecoin.usdc.received.success",
        "data": {
            "event_id": "evt_fraud"
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    # Tampered signature
    signature = "bad_signature_string"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/webhooks/bitnob",
            content=raw_body,
            headers={"x-bitnob-signature": signature}
        )
        
    assert response.status_code == 401
    assert "Invalid signature" in response.text
