from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.invoice import InvoiceStatus


class InvoiceCreateRequest(BaseModel):
    client_name: str = Field(..., min_length=2, max_length=255)
    client_email: EmailStr
    description: Optional[str] = Field(None, max_length=1000)
    amount_usd: Decimal = Field(..., gt=0, decimal_places=2)
    due_date: Optional[date] = None


class InvoiceResponse(BaseModel):
    id: UUID
    user_id: UUID
    client_name: str
    client_email: EmailStr
    description: Optional[str]
    amount_usd: Decimal
    status: InvoiceStatus
    bitnob_reference: str
    amount_received_usd_equiv: Decimal
    overpaid_amount_usd: Decimal
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedInvoiceResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int
