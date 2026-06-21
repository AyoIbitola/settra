"""PaymentTarget model — one row per Busha payment request created against an invoice."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


# Supported payment methods — no 'lightning' value; Busha does not offer Lightning.
# See PRD Section 1.1 and 5.3.
PAYMENT_METHODS = ("btc_onchain", "usdc", "usdt")


class PaymentTarget(Base):
    """
    One row per Busha payment request created against an invoice's payment link.
    Multiple targets can exist per invoice (e.g. different methods, or a top-up
    target after partial payment). Only one per (invoice, method) should be
    is_active=True at a time.
    """

    __tablename__ = "payment_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    # btc_onchain | usdc | usdt — no lightning
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    # e.g. BASE, TRX, BTC — validated against SUPPORTED_NETWORKS in config.py
    network: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The deposit address returned in Busha's pay_in.address field
    target_value: Mapped[str] = mapped_column(Text, nullable=False)
    # Busha's payment request ID (e.g. PAYR_...) — this is the correlation key:
    # Busha echoes it back as 'reference' on every webhook event for this payment.
    busha_payment_request_id: Mapped[str] = mapped_column(
        String(256), unique=True, nullable=False
    )
    # Extracted from Busha's rate.rate field at payment-request creation time.
    # Immutable once written — this is what ReconciliationService uses to convert
    # crypto amounts to USD-equivalent, even for late payments (PRD Section 6.5).
    rate_locked_usd_to_crypto: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False
    )
    # Extracted from Busha's source_amount field on payment request creation.
    amount_expected_crypto: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False
    )
    # Full raw Busha payment-request response for debugging/audit
    busha_response_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # From Busha's pay_in.expires_at — when this rate lock expires
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_payment_targets_invoice_id", "invoice_id"),
        Index("idx_payment_targets_invoice_active", "invoice_id", "is_active"),
    )
