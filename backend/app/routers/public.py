import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PaymentTargetGenerationError
from app.db import get_session
from app.models.invoice import InvoiceStatus
from app.schemas.public import PaymentTargetResponse, PublicInvoiceResponse, PublicInvoiceStatusResponse
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/public/invoices", tags=["Public"])

# Public endpoints are the attack surface — rate-limit aggressively per IP
limiter = Limiter(key_func=get_remote_address)


@router.get("/{invoice_id}", response_model=PublicInvoiceResponse)
@limiter.limit("60/minute")
async def get_public_invoice(
    request: Request,
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Get publicly viewable details of an invoice."""
    invoice = await InvoiceService.get_public_invoice(db=db, invoice_id=invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    return PublicInvoiceResponse(
        client_name=invoice.client_name,
        business_name=invoice.user.business_name if invoice.user else None,
        description=invoice.description,
        amount_usd=invoice.amount_usd,
        status=invoice.status,
        due_date=invoice.due_date,
    )


@router.get("/{invoice_id}/payment-methods")
@limiter.limit("30/minute")
async def get_payment_methods(
    request: Request,
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Get supported payment methods for this invoice."""
    invoice = await InvoiceService.get_public_invoice(db=db, invoice_id=invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    return ["usdc", "usdt", "btc", "lightning"]


@router.post("/{invoice_id}/payment-target", response_model=PaymentTargetResponse)
@limiter.limit("10/minute")
async def create_payment_target(
    request: Request,
    invoice_id: uuid.UUID,
    method: str = Query(..., description="Payment method: usdc | usdt | btc"),
    db: AsyncSession = Depends(get_session),
):
    """
    Generate or retrieve a Busha payment request target for an invoice.
    Rate-limited to 10/min per IP.
    """
    try:
        target_info = await InvoiceService.create_payment_target(db=db, invoice_id=invoice_id, method=method)
        return PaymentTargetResponse(**target_info)
    except PaymentTargetGenerationError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{invoice_id}/status", response_model=PublicInvoiceStatusResponse)
@limiter.limit("120/minute")
async def get_invoice_status(
    request: Request,
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Lightweight polling endpoint — frontend polls every ~5 seconds.
    Higher rate limit (120/min) than other public endpoints to support frequent polling.
    """
    invoice = await InvoiceService.get_public_invoice(db=db, invoice_id=invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    remaining = None
    if invoice.status == InvoiceStatus.PARTIALLY_PAID:
        remaining = invoice.amount_usd - invoice.amount_received_usd_equiv

    return PublicInvoiceStatusResponse(
        status=invoice.status,
        amount_received_usd_equiv=invoice.amount_received_usd_equiv,
        remaining_usd=remaining,
        overpaid_amount_usd=invoice.overpaid_amount_usd,
        active_target_expires_at=None,
    )


@router.get("/{invoice_id}/receipt")
@limiter.limit("20/minute")
async def get_public_invoice_receipt(
    request: Request,
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Get the generated PDF receipt if it exists."""
    from sqlalchemy import select
    from app.models.receipt import Receipt

    result = await db.execute(
        select(Receipt).where(Receipt.invoice_id == invoice_id).order_by(Receipt.generated_at.desc())
    )
    receipt = result.scalars().first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not yet generated")

    if not receipt.pdf_path.startswith("http"):
        raise HTTPException(status_code=404, detail="Receipt file not available remotely.")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=receipt.pdf_path)
