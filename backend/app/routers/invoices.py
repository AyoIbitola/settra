import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import get_session
from app.models.invoice import InvoiceStatus
from app.models.user import User
from app.schemas.invoice import InvoiceCreateRequest, InvoiceResponse, PaginatedInvoiceResponse
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    data: InvoiceCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Create a new invoice. The status will default to DRAFT.
    """
    invoice = await InvoiceService.create_invoice(db=db, user_id=current_user.id, data=data)
    return invoice


@router.get("", response_model=PaginatedInvoiceResponse)
async def list_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: InvoiceStatus | None = Query(None, description="Filter by invoice status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    List invoices for the authenticated user, with optional filtering by status.
    """
    items, total = await InvoiceService.list_invoices(
        db=db, user_id=current_user.id, status=status, page=page, page_size=page_size
    )
    return PaginatedInvoiceResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Get expanded details for a specific invoice.
    """
    invoice = await InvoiceService.get_invoice_by_id(db=db, invoice_id=invoice_id, user_id=current_user.id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/receipt")
async def get_invoice_receipt(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Get the generated PDF receipt for the owner, or queue generation for paid invoices.
    """
    from fastapi.responses import JSONResponse, RedirectResponse
    from sqlalchemy import select

    from app.models.payment import Payment
    from app.models.receipt import Receipt
    from app.workers.tasks import generate_receipt

    # Ensure ownership
    invoice = await InvoiceService.get_invoice_by_id(db=db, invoice_id=invoice_id, user_id=current_user.id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    result = await db.execute(
        select(Receipt).where(Receipt.invoice_id == invoice_id).order_by(Receipt.generated_at.desc())
    )
    receipt = result.scalars().first()
    if not receipt:
        if invoice.status in [
            InvoiceStatus.PAID,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.OVERPAID,
        ]:
            payment_result = await db.execute(
                select(Payment)
                .where(Payment.invoice_id == invoice_id)
                .order_by(Payment.received_at.desc())
                .limit(1)
            )
            payment = payment_result.scalar_one_or_none()
            generate_receipt.delay(str(invoice_id), str(payment.id) if payment else None)
            return JSONResponse(status_code=202, content={"detail": "Receipt generation queued"})

        raise HTTPException(status_code=404, detail="Receipt not yet generated")

    if not receipt.pdf_path.startswith("http"):
        # For legacy records if any, or gracefully degrade
        raise HTTPException(status_code=404, detail="Receipt file not available remotely.")

    # Redirect to the S3 URL
    return RedirectResponse(url=receipt.pdf_path)


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
async def cancel_invoice(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Cancel a draft or pending invoice.
    Rejected (409) if any payments have been recorded against it.
    """
    from sqlalchemy import select
    from app.models.payment import Payment

    invoice = await InvoiceService.get_invoice_by_id(db=db, invoice_id=invoice_id, user_id=current_user.id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if invoice.status not in [InvoiceStatus.DRAFT, InvoiceStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel invoice in '{invoice.status.value}' state"
        )

    # Guard: reject if any payments exist
    payment_result = await db.execute(
        select(Payment).where(Payment.invoice_id == invoice_id).limit(1)
    )
    if payment_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel invoice that has received payments"
        )

    invoice.status = InvoiceStatus.CANCELLED
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_invoice(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Re-send the payment link email to the client.
    Rate-limited to 1 call per 5 minutes per invoice to prevent abuse.
    """
    import redis as redis_lib
    from app.config import settings
    from app.workers.tasks import send_email

    invoice = await InvoiceService.get_invoice_by_id(db=db, invoice_id=invoice_id, user_id=current_user.id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if invoice.status in [InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only resend for pending or partially paid invoices"
        )

    # Rate limit: max 1 resend per invoice per 5 minutes using Redis
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        rate_key = f"resend_ratelimit:{invoice_id}"
        if r.get(rate_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait 5 minutes before resending"
            )
        r.setex(rate_key, 300, "1")  # 300 seconds = 5 minutes
    except HTTPException:
        raise
    except Exception:
        pass  # If Redis is down, allow the send (fail open)

    send_email.delay(
        template_id="payment_link",
        recipient=invoice.client_email,
        subject=f"Payment link for invoice {invoice.busha_reference}",
        data={
            "client_name": invoice.client_name,
            "amount_usd": str(invoice.amount_usd),
            "invoice_url": f"{settings.FRONTEND_BASE_URL}/pay/{invoice.id}",
        }
    )

    return {"detail": "Payment link email queued for delivery"}

