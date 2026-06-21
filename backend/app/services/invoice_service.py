import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import InvalidStateTransitionError
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_target import PaymentTarget
from app.schemas.invoice import InvoiceCreateRequest
from app.services.bitnob_client import BitnobClient


class InvoiceService:
    @staticmethod
    async def create_invoice(
        db: AsyncSession, user_id: uuid.UUID, data: InvoiceCreateRequest
    ) -> Invoice:
        # Create a new draft invoice.
        # Generate a unique bitnob_reference using uuid4
        temp_reference = f"INV_{uuid.uuid4().hex[:16].upper()}"

        invoice = Invoice(
            user_id=user_id,
            client_name=data.client_name,
            client_email=data.client_email,
            description=data.description,
            amount_usd=data.amount_usd,
            status=InvoiceStatus.DRAFT,
            bitnob_reference=temp_reference,
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
                PaymentTarget.is_active == True,
                PaymentTarget.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def generate_payment_target(
        db: AsyncSession, invoice_id: uuid.UUID, method: str
    ) -> PaymentTarget:
        """Implements PRD 7.3.1 - Generate payment target for invoice."""
        
        if method not in ["usdc", "usdt", "btc", "lightning"]:
            raise HTTPException(status_code=400, detail="Unsupported payment method")

        # 1. Load invoice with lock to prevent concurrent target generation
        result = await db.execute(
            select(Invoice)
            .options(joinedload(Invoice.user))
            .where(Invoice.id == invoice_id)
            .with_for_update()
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.EXPIRED]:
            raise HTTPException(status_code=409, detail=f"Cannot generate payment target for invoice in {invoice.status.value} state")

        now = datetime.now(timezone.utc)

        # 2. Check for existing active payment target
        existing_result = await db.execute(
            select(PaymentTarget).where(
                PaymentTarget.invoice_id == invoice.id,
                PaymentTarget.method == method,
                PaymentTarget.is_active == True,
                PaymentTarget.expires_at > now,
            )
        )
        active_target = existing_result.scalar_one_or_none()
        if active_target:
            return active_target

        # 3a. If draft, transition to pending
        if invoice.status == InvoiceStatus.DRAFT:
            invoice.status = InvoiceStatus.PENDING
            db.add(invoice)

        # 3b. Determine amount to quote
        if invoice.status in [InvoiceStatus.PENDING, InvoiceStatus.DRAFT, InvoiceStatus.EXPIRED]:
            amount_to_quote_usd = invoice.amount_usd
        elif invoice.status == InvoiceStatus.PARTIALLY_PAID:
            amount_to_quote_usd = invoice.amount_usd - invoice.amount_received_usd_equiv
            if amount_to_quote_usd <= 0:
                raise HTTPException(status_code=409, detail="Invoice is completely paid")
        else:
            raise HTTPException(status_code=409, detail="Unexpected invoice status")

        # 3c-d. Bitnob integration
        client = BitnobClient()
        try:
            # Determine correct API rate mapping and request type
            bitnob_raw = {}
            target_value = ""
            network = method

            if method in ["usdc", "usdt"]:
                rate_response = await client.get_exchange_rate("USD", method.upper())
                rate_data = rate_response.get("data", {})
                rate_locked = Decimal(str(rate_data.get("sell_rate", "1.00")))
                amount_expected_crypto = amount_to_quote_usd * rate_locked

                network = "polygon"
                address_res = await client.generate_address(
                    chain=network,
                    customer_email=invoice.client_email,
                    reference=f"{invoice.bitnob_reference}-{int(now.timestamp())}"
                )
                target_value = address_res.get("data", {}).get("address")
                bitnob_raw = address_res.get("data", {})

            elif method == "btc":
                rate_response = await client.get_exchange_rate("USD", "BTC")
                rate_data = rate_response.get("data", {})
                # E.g. Bitnob returns 1 USD = 0.000015 BTC in sell_rate
                rate_locked = Decimal(str(rate_data.get("sell_rate", "0.000015")))
                amount_expected_crypto = amount_to_quote_usd * rate_locked

                network = "bitcoin"
                address_res = await client.generate_btc_address(
                    customer_email=invoice.client_email,
                    label=f"Invoice {invoice.bitnob_reference}"
                )
                # Fallback data extraction considering standard formats
                data_obj = address_res.get("data", address_res)
                target_value = data_obj.get("address")
                bitnob_raw = data_obj

            elif method == "lightning":
                rate_response = await client.get_exchange_rate("USD", "BTC")
                rate_data = rate_response.get("data", {})
                rate_locked = Decimal(str(rate_data.get("sell_rate", "0.000015")))
                
                amount_expected_btc = amount_to_quote_usd * rate_locked
                satoshis = int(amount_expected_btc * Decimal("100000000"))
                amount_expected_crypto = Decimal(str(satoshis))

                network = "lightning"
                ln_res = await client.create_lightning_invoice(
                    satoshis=satoshis,
                    description=f"Invoice {invoice.bitnob_reference}",
                    reference=f"{invoice.bitnob_reference}-{int(now.timestamp())}"
                )
                data_obj = ln_res.get("data", ln_res)
                target_value = data_obj.get("paymentRequest") or data_obj.get("payment_request") or data_obj.get("request")
                bitnob_raw = data_obj

            if not target_value:
                raise HTTPException(status_code=502, detail=f"Invalid payload/address returned by upstream for {method}")
            
        finally:
            await client.close()

        # 3e. Mark old targets inactive
        await db.execute(
            select(PaymentTarget).where(
                PaymentTarget.invoice_id == invoice.id,
                PaymentTarget.method == method,
                PaymentTarget.is_active == True,
            )
        )
        # Using simple UPDATE for any active
        for old_targ in (await db.execute(
            select(PaymentTarget).where(
                PaymentTarget.invoice_id == invoice.id,
                PaymentTarget.is_active == True,
            )
        )).scalars().all():
            old_targ.is_active = False

        # 3f. Persist new target
        new_target = PaymentTarget(
            invoice_id=invoice.id,
            method=method,
            network=network,
            target_value=target_value,
            rate_locked_usd_to_crypto=rate_locked,
            amount_expected_crypto=amount_expected_crypto,
            expires_at=now + timedelta(hours=24),  # Standard 24h expiry
            bitnob_response_raw=bitnob_raw,
            is_active=True,
        )
        db.add(new_target)
        await db.commit()
        await db.refresh(new_target)
        
        return new_target
