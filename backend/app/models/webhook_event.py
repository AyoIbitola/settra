"""WebhookEvent model — deduplication and audit log for all incoming Busha webhooks."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class WebhookEvent(Base):
    """
    Deduplication table for incoming Busha webhook events.

    Busha's webhook payloads do not expose a single dedicated event_id field
    (unlike the original Bitnob-based design assumed). Instead we build a
    composite dedup key: "{data.id}:{event_type}:{data.updated_at|created_at}"

    This means:
    - Two different status transitions on the same object (e.g. pending → completed)
      produce two distinct dedup keys → both are processed correctly.
    - The same payload delivered twice is caught by the unique constraint → ack'd and skipped.

    See PRD Section 4.5 and 8.1 for the full rationale.
    [CONFIRM] against real sandbox payloads whether a cleaner dedicated event_id field
    exists — see Section 16 item 3.
    """

    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Composite key: "{object_id}:{event_type}:{timestamp}" — PRD Section 4.5
    event_dedup_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Recorded even if invalid — useful for security audit logs (logged-and-rejected events)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_webhook_events_event_type", "event_type"),
    )
