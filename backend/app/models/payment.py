"""Payment model — append-only ledger of confirmed fund receipts."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Payment(Base):
    """
    Append-only ledger of every confirmed receipt of funds against an invoice.
    Never delete or update rows except the 'confirmations' field (for BTC on-chain,
    if Busha surfaces confirmation counts — see PRD Section 16 item 4).

    Note: confirmations is treated as a 0/1 flag rather than a true count for now,
    since Busha's webhook granularity (processing → completed) may be the only
    granularity available. Revisit once confirmed against sandbox per Section 16 item 4.
    """

    __tablename__ = "payments"
    __table_args__ = (
        # Prevents the same on-chain tx from being recorded twice against one invoice.
        # Second layer of defense beyond webhook deduplication.
        UniqueConstraint("tx_hash", "invoice_id", name="uq_payments_tx_invoice"),
        Index("idx_payments_invoice_id", "invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False
    )
    payment_target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_targets.id"), nullable=True
    )
    # On-chain tx hash from Busha's pay_in.blockchain_hash webhook field.
    # [CONFIRM] at what stage (processing vs completed) this field is populated — PRD Section 16 item 4.
    tx_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    # Raw crypto amount as reported by Busha's source_amount field
    amount_received_crypto: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    # USD equivalent computed using the payment target's locked rate, never a live rate.
    # See PRD Section 6.3 and 6.5.
    amount_received_usd_equiv: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # btc_onchain | usdc | usdt — no lightning
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    network: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 0 = unconfirmed, 1 = confirmed (or raw count if Busha exposes it — see PRD Section 16 item 4)
    confirmations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Traceability: the Busha payment request ID that produced this payment row.
    busha_payment_request_id: Mapped[str] = mapped_column(String(256), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
