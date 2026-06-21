import uuid
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User


@pytest_asyncio.fixture
async def test_session() -> AsyncSession:
    """Provide a transactional scoped async session for tests."""
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def temp_user(test_session: AsyncSession) -> User:
    user = User(
        email=f"test-{uuid.uuid4()}@example.com",
        password_hash="testhash",
        business_name="Test Business"
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def temp_invoice(test_session: AsyncSession, temp_user: User) -> Invoice:
    invoice = Invoice(
        user_id=temp_user.id,
        client_name="Test Client",
        client_email="client@example.com",
        amount_usd=Decimal("1500.50"),
        status=InvoiceStatus.DRAFT,
        bitnob_reference=f"INV_{uuid.uuid4().hex[:16]}",
    )
    test_session.add(invoice)
    await test_session.commit()
    await test_session.refresh(invoice)
    return invoice
