"""SQLAlchemy model for invoices and InvoiceStatus enum."""

import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.receipt import Receipt
    from app.models.user import User


from app.models import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice lifecycle states — PRD Section 4.2.1. See state machine there for allowed transitions."""

    DRAFT = "draft"                  # created, no payment target generated yet
    PENDING = "pending"              # payment target generated, awaiting payment
    PARTIALLY_PAID = "partially_paid"  # some funds received, less than expected
    PAID = "paid"                    # funds received within tolerance of expected
    OVERPAID = "overpaid"            # funds received exceed expected beyond tolerance
    EXPIRED = "expired"              # payment target/rate lock expired with zero payment
    CANCELLED = "cancelled"          # freelancer manually cancelled
    REFUNDED = "refunded"            # manual refund recorded (v1: record-keeping only)


def _generate_busha_reference() -> str:
    """Generate a unique Busha reference like INV_<short uuid>."""
    return f"INV_{uuid.uuid4().hex[:12].upper()}"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_name: Mapped[str] = mapped_column(String, nullable=False)
    client_email: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        PgEnum(InvoiceStatus, name="invoice_status", create_type=True),
        nullable=False,
        default=InvoiceStatus.DRAFT,
    )
    # Passed to Busha wherever a reference field is accepted.
    # Also used to correlate incoming webhooks back to this invoice.
    busha_reference: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, default=_generate_busha_reference
    )
    # The Busha one-time payment link ID (created lazily on first payment target request).
    # Nullable until the link is created. PRD Section 4.2.
    busha_link_id: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True, default=None
    )
    # Running total in USD-equivalent — only recalculated by ReconciliationService.
    amount_received_usd_equiv: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    # Only non-zero when status = overpaid.
    overpaid_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    receipts: Mapped[list["Receipt"]] = relationship(
        "Receipt", back_populates="invoice", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User", back_populates="invoices", lazy="noload")

    __table_args__ = (
        Index("idx_invoices_user_id", "user_id"),
        Index("idx_invoices_busha_reference", "busha_reference", unique=True),
        Index("idx_invoices_status", "status"),
    )
