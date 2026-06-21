import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class OverpaymentStatusEnum(str, Enum):
    unresolved = "unresolved"
    refunded = "refunded"
    acknowledged_keep = "acknowledged_keep"


class OverpaymentCreditResponse(BaseModel):
    id: uuid.UUID
    source_invoice_id: uuid.UUID
    amount_usd: Decimal
    status: OverpaymentStatusEnum
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class ResolveOverpaymentRequest(BaseModel):
    action: Literal["acknowledged_keep", "refunded"]
