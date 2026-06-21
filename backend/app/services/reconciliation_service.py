from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateTransitionError
from app.models.invoice import Invoice, InvoiceStatus
from app.models.overpayment_credit import OverpaymentCredit
from app.models.payment import Payment

# Absolute floor: covers genuine rounding/dust regardless of invoice size.
MIN_TOLERANCE_USD = Decimal("0.05")

# Relative ceiling: scales with invoice size so large invoices aren't
# falsely flagged paid/overpaid from proportionally larger crypto rounding.
TOLERANCE_BPS = Decimal("10")  # 0.10%


def compute_tolerance_usd(amount_usd: Decimal) -> Decimal:
    relative = amount_usd * TOLERANCE_BPS / Decimal("10000")
    return max(MIN_TOLERANCE_USD, relative)


ALLOWED_TRANSITIONS = {
    InvoiceStatus.DRAFT: {InvoiceStatus.PENDING, InvoiceStatus.CANCELLED},
    InvoiceStatus.PENDING: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERPAID,
        InvoiceStatus.EXPIRED,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.PARTIALLY_PAID: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERPAID,
    },
    InvoiceStatus.EXPIRED: {
        InvoiceStatus.PAID,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.OVERPAID,
    },
    InvoiceStatus.PAID: {InvoiceStatus.OVERPAID},
    InvoiceStatus.OVERPAID: {InvoiceStatus.REFUNDED},
    InvoiceStatus.CANCELLED: set(),
    InvoiceStatus.REFUNDED: set(),
}


class ReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile(self, invoice_id: str) -> Invoice:
        """
        Must be called with the invoice row locked (SELECT ... FOR UPDATE)
        to prevent concurrent webhook events from racing on the same invoice.
        This is the ONLY method permitted to change invoice.status.
        """
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id).with_for_update()
        )
        invoice = result.scalar_one()

        # Recompute the running total from the payments ledger — never trust
        # an incrementally-updated counter, always re-sum from source rows.
        payments_result = await self.db.execute(
            select(Payment).where(Payment.invoice_id == invoice_id)
        )
        payments = payments_result.scalars().all()
        total_received = sum(
            (p.amount_received_usd_equiv for p in payments), Decimal("0")
        )

        tolerance = compute_tolerance_usd(invoice.amount_usd)
        delta = invoice.amount_usd - total_received  # positive = still short

        if total_received <= Decimal("0"):
            new_status = invoice.status  # no payment yet, no transition triggered here
        elif delta > tolerance:
            new_status = InvoiceStatus.PARTIALLY_PAID
        elif delta >= -tolerance:
            new_status = InvoiceStatus.PAID
        else:
            new_status = InvoiceStatus.OVERPAID

        if new_status != invoice.status:
            self._assert_valid_transition(invoice.status, new_status)
            invoice.status = new_status

        invoice.amount_received_usd_equiv = total_received

        if new_status == InvoiceStatus.OVERPAID:
            overpaid_amount = total_received - invoice.amount_usd
            invoice.overpaid_amount_usd = overpaid_amount
            await self._ensure_overpayment_credit_recorded(invoice, overpaid_amount)

        await self.db.commit()
        return invoice

    def _assert_valid_transition(
        self, current: InvoiceStatus, target: InvoiceStatus
    ) -> None:
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition invoice from {current.value} to {target.value}"
            )

    async def _ensure_overpayment_credit_recorded(
        self, invoice: Invoice, amount: Decimal
    ) -> None:
        existing = await self.db.execute(
            select(OverpaymentCredit).where(
                OverpaymentCredit.source_invoice_id == invoice.id,
                OverpaymentCredit.status == "unresolved",
            )
        )
        if existing.scalar_one_or_none() is None:
            self.db.add(
                OverpaymentCredit(
                    user_id=invoice.user_id,
                    source_invoice_id=invoice.id,
                    amount_usd=amount,
                    status="unresolved",
                )
            )
