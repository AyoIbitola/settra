import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Payment(Base):
    """Append-only ledger of every confirmed receipt of funds against an invoice."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tx_hash", "invoice_id", name="uq_payments_tx_invoice"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    payment_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_targets.id"), nullable=False
    )
    tx_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    amount_received_crypto: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False
    )
    # USD equivalent computed using the *target's locked rate*, not a live rate
    amount_received_usd_equiv: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    network: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # FK to the webhook_events table for full traceability
    bitnob_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
