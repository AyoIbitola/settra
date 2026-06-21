import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.exceptions import InvalidStateTransitionError
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.payment_target import PaymentTarget
from app.models.overpayment_credit import OverpaymentCredit
from app.services.reconciliation_service import compute_tolerance_usd, ReconciliationService


def test_compute_tolerance_usd():
    assert compute_tolerance_usd(Decimal("10.00")) == Decimal("0.05")
    assert compute_tolerance_usd(Decimal("10000.00")) == Decimal("10.00")


@pytest.mark.asyncio
async def test_reconciliation_exact_payment(test_session, temp_invoice):
    temp_invoice.status = InvoiceStatus.PENDING
    test_session.add(temp_invoice)
    await test_session.commit()

    target = PaymentTarget(
        invoice_id=temp_invoice.id,
        method="usdc",
        network="polygon",
        target_value="test_address",
        rate_locked_usd_to_crypto=Decimal("1.00"),
        amount_expected_crypto=Decimal("1500.50"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        bitnob_response_raw={},
        is_active=True
    )
    test_session.add(target)
    await test_session.commit()
    await test_session.refresh(target)

    payment = Payment(
        invoice_id=temp_invoice.id,
        payment_target_id=target.id,
        tx_hash="tx123",
        amount_received_crypto=Decimal("1500.50"),
        amount_received_usd_equiv=Decimal("1500.50"),
        method="usdc",
        bitnob_event_id="evt_123"
    )
    test_session.add(payment)
    await test_session.commit()

    service = ReconciliationService(test_session)
    invoice = await service.reconcile(temp_invoice.id)
    
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.amount_received_usd_equiv == Decimal("1500.50")
    assert invoice.overpaid_amount_usd == Decimal("0.00")


@pytest.mark.asyncio
async def test_reconciliation_underpayment(test_session, temp_invoice):
    temp_invoice.status = InvoiceStatus.PENDING
    test_session.add(temp_invoice)
    await test_session.commit()

    target = PaymentTarget(
        invoice_id=temp_invoice.id,
        method="usdc",
        network="polygon",
        target_value="test_address_2",
        rate_locked_usd_to_crypto=Decimal("1.00"),
        amount_expected_crypto=Decimal("1500.50"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        bitnob_response_raw={},
        is_active=True
    )
    test_session.add(target)
    await test_session.commit()
    await test_session.refresh(target)

    payment = Payment(
        invoice_id=temp_invoice.id,
        payment_target_id=target.id,
        tx_hash="tx456",
        amount_received_crypto=Decimal("500.00"),
        amount_received_usd_equiv=Decimal("500.00"),
        method="usdc",
        bitnob_event_id="evt_456"
    )
    test_session.add(payment)
    await test_session.commit()

    service = ReconciliationService(test_session)
    invoice = await service.reconcile(temp_invoice.id)
    
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert invoice.amount_received_usd_equiv == Decimal("500.00")


@pytest.mark.asyncio
async def test_reconciliation_overpayment(test_session, temp_invoice):
    temp_invoice.status = InvoiceStatus.PENDING
    test_session.add(temp_invoice)
    await test_session.commit()

    target = PaymentTarget(
        invoice_id=temp_invoice.id,
        method="usdc",
        network="polygon",
        target_value="test_address_3",
        rate_locked_usd_to_crypto=Decimal("1.00"),
        amount_expected_crypto=Decimal("1500.50"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        is_active=True
    )
    test_session.add(target)
    await test_session.commit()
    await test_session.refresh(target)

    payment = Payment(
        invoice_id=temp_invoice.id,
        payment_target_id=target.id,
        tx_hash="tx789",
        amount_received_crypto=Decimal("2000.00"),
        amount_received_usd_equiv=Decimal("2000.00"),
        method="usdc",
        bitnob_event_id="evt_789"
    )
    test_session.add(payment)
    await test_session.commit()

    service = ReconciliationService(test_session)
    invoice = await service.reconcile(temp_invoice.id)
    
    assert invoice.status == InvoiceStatus.OVERPAID
    assert invoice.amount_received_usd_equiv == Decimal("2000.00")
    assert invoice.overpaid_amount_usd == Decimal("499.50")
    
    credits_res = await test_session.execute(select(OverpaymentCredit).where(OverpaymentCredit.source_invoice_id == invoice.id))
    over_credit = credits_res.scalar_one()
    assert over_credit.amount_usd == Decimal("499.50")


@pytest.mark.asyncio
async def test_reconciliation_forbidden_transition(test_session, temp_invoice):
    temp_invoice.status = InvoiceStatus.PAID
    temp_invoice.amount_received_usd_equiv = temp_invoice.amount_usd
    test_session.add(temp_invoice)
    await test_session.commit()

    service = ReconciliationService(test_session)
    
    invoice = await service.reconcile(temp_invoice.id)
    assert invoice.status == InvoiceStatus.PAID

    with pytest.raises(InvalidStateTransitionError):
        service._assert_valid_transition(InvoiceStatus.PAID, InvoiceStatus.PENDING)
