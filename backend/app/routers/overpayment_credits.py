import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db import get_session
from app.models.overpayment_credit import OverpaymentCredit, OverpaymentStatus
from app.models.user import User
from app.schemas.overpayment import OverpaymentCreditResponse, ResolveOverpaymentRequest

router = APIRouter(prefix="/overpayment-credits", tags=["Overpayment Credits"])


@router.get("", response_model=list[OverpaymentCreditResponse])
async def list_overpayment_credits(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """List all overpayment credits associated with the freelancer's invoices."""
    result = await db.execute(
        select(OverpaymentCredit)
        .where(OverpaymentCredit.user_id == current_user.id)
        .order_by(OverpaymentCredit.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{credit_id}/resolve", response_model=OverpaymentCreditResponse)
async def resolve_overpayment_credit(
    credit_id: uuid.UUID,
    body: ResolveOverpaymentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Mark an overpayment credit as resolved.
    action: 'acknowledged_keep' = freelancer keeps the extra funds.
    action: 'refunded' = manual refund was performed outside the system.
    """
    result = await db.execute(
        select(OverpaymentCredit).where(
            OverpaymentCredit.id == credit_id,
            OverpaymentCredit.user_id == current_user.id,
        )
    )
    credit = result.scalar_one_or_none()
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Overpayment credit not found")

    if credit.status != OverpaymentStatus.UNRESOLVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Credit is already resolved (status: {credit.status.value})"
        )

    credit.status = OverpaymentStatus(body.action)
    credit.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(credit)
    return credit
