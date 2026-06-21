from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.invoice import InvoiceStatus


class PublicInvoiceResponse(BaseModel):
    client_name: str
    business_name: Optional[str]
    description: Optional[str]
    amount_usd: Decimal
    status: InvoiceStatus
    due_date: Optional[date]

    model_config = ConfigDict(from_attributes=True)


class PaymentTargetResponse(BaseModel):
    target_value: str
    amount_expected_crypto: Decimal
    expires_at: datetime
    method: str
    network: str
    payment_request_id: str

    model_config = ConfigDict(from_attributes=True)


class PublicInvoiceStatusResponse(BaseModel):
    status: InvoiceStatus
    amount_received_usd_equiv: Decimal
    remaining_usd: Optional[Decimal] = None
    overpaid_amount_usd: Decimal
    active_target_expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
