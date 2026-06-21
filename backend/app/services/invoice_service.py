import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_target import PaymentTarget
from app.schemas.invoice import InvoiceCreateRequest
class InvoiceService:
    @staticmethod
    async def create_invoice(
        db: AsyncSession, user_id: uuid.UUID, data: InvoiceCreateRequest
    ) -> Invoice:
        # Create a new draft invoice.
        temp_reference = f"INV_{uuid.uuid4().hex[:16].upper()}"

        invoice = Invoice(
            user_id=user_id,
            client_name=data.client_name,
            client_email=data.client_email,
            description=data.description,
            amount_usd=data.amount_usd,
            status=InvoiceStatus.DRAFT,
            busha_reference=temp_reference,
            amount_received_usd_equiv=Decimal("0.00"),
            overpaid_amount_usd=Decimal("0.00"),
            due_date=data.due_date,
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return invoice

    @staticmethod
    async def get_invoice_by_id(
        db: AsyncSession, invoice_id: uuid.UUID, user_id: uuid.UUID
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
        )
        return result.scalar_one_or_none()
        
    @staticmethod
    async def get_public_invoice(
        db: AsyncSession, invoice_id: uuid.UUID
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice)
            .options(joinedload(Invoice.user))
            .where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_invoices(
        db: AsyncSession,
        user_id: uuid.UUID,
        status: InvoiceStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[Invoice], int]:
        query = select(Invoice).where(Invoice.user_id == user_id)
        
        if status is not None:
            query = query.where(Invoice.status == status)
            
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(Invoice.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        return items, total

    @staticmethod
    async def get_active_payment_target(
        db: AsyncSession, invoice_id: uuid.UUID
    ) -> PaymentTarget | None:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(PaymentTarget).where(
                PaymentTarget.invoice_id == invoice_id,
                PaymentTarget.is_active,
                PaymentTarget.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_checkout_link(
        db: AsyncSession, invoice_id: uuid.UUID, method: str
    ) -> str:
        """Returns a Busha Checkout URL. Updates invoice with the link_id."""
        from app.services.busha_client import BushaClient

        if method not in ["usdc", "usdt", "btc"]:
            raise HTTPException(status_code=400, detail="Unsupported payment method")

        # 1. Load invoice with lock to prevent concurrent link generation
        result = await db.execute(
            select(Invoice)
            .options(joinedload(Invoice.user))
            .where(Invoice.id == invoice_id)
            .with_for_update()
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]:
            raise HTTPException(status_code=409, detail=f"Cannot generate link for invoice in {invoice.status.value} state")

        # 2a. If draft, transition to pending
        if invoice.status == InvoiceStatus.DRAFT:
            invoice.status = InvoiceStatus.PENDING

        # 2b. Determine amount to quote
        amount_to_quote_usd = invoice.amount_usd
        if invoice.status == InvoiceStatus.PARTIALLY_PAID:
            amount_to_quote_usd = invoice.amount_usd - invoice.amount_received_usd_equiv
            if amount_to_quote_usd <= 0:
                raise HTTPException(status_code=409, detail="Invoice is completely paid")

        # Normalize method to Busha currency code (BTC, USDC, USDT)
        target_currency = method.upper()

        # 3. Call Busha to create a link
        async with BushaClient() as client:
            link_data = await client.create_one_time_payment_link(
                name=f"Invoice {invoice.busha_reference}",
                title=f"Invoice {invoice.client_name}",
                description=invoice.description or "",
                quote_amount=str(amount_to_quote_usd),
                quote_currency="USD",
                target_currency=target_currency,
                customer_email=invoice.client_email,
            )

        link_id = link_data.get("data", {}).get("id")
        if not link_id:
            raise HTTPException(status_code=502, detail="Failed to retrieve link ID from Busha")

        # 4. Save link_id on invoice (overwrites if they picked a new currency)
        invoice.busha_link_id = link_id
        db.add(invoice)
        await db.commit()

        # 5. Return Checkout URL
        return f"https://pay.busha.co/{link_id}"
