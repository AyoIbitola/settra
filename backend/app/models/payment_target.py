import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class PaymentMethod:
    BTC_ONCHAIN = "btc_onchain"
    LIGHTNING = "lightning"
    USDC = "usdc"
    USDT = "usdt"


class PaymentTarget(Base):
    __tablename__ = "payment_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    network: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_value: Mapped[str] = mapped_column(Text, nullable=False)
    rate_locked_usd_to_crypto: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False
    )
    amount_expected_crypto: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False
    )
    bitnob_response_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
