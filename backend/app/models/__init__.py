"""SQLAlchemy declarative base and model registry.

Import all models here so Alembic can discover them via Base.metadata.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models after Base is defined so they register with metadata.
# These imports are intentionally at the bottom to avoid circular imports.
from app.models.user import User  # noqa: E402, F401
from app.models.invoice import Invoice  # noqa: E402, F401
from app.models.payment_target import PaymentTarget  # noqa: E402, F401
from app.models.payment import Payment  # noqa: E402, F401
from app.models.webhook_event import WebhookEvent  # noqa: E402, F401
from app.models.overpayment_credit import OverpaymentCredit  # noqa: E402, F401
from app.models.receipt import Receipt  # noqa: E402, F401
