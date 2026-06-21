import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import async_session_factory
from app.models.invoice import InvoiceStatus
from app.models.payment import Payment
from app.models.payment_target import PaymentTarget
from app.models.webhook_event import WebhookEvent
from app.services.reconciliation_service import ReconciliationService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

async def handle_stablecoin_received(db, event_id: str, payload: dict) -> None:
    data = payload.get("data", {})
    reference = data.get("reference")
    if not reference:
        logger.warning(f"No reference in stablecoin webhook payload {event_id}")
        return

    crypto_received = str(data.get("amount", "0.00"))
    tx_hash = data.get("hash") or data.get("tx_hash") or payload.get("id")

    if not tx_hash:
        logger.warning(f"No tx_hash found for stablecoin payload {event_id}")
        return

    target_result = await db.execute(
        select(PaymentTarget).where(PaymentTarget.target_value == data.get("address"))
    )
    target = target_result.scalar_one_or_none()
    
    if not target:
        invoice_ref = reference.rsplit("-", 1)[0]
        pass
    
    raise NotImplementedError("Requires sandbox webhook payload inspection to finish safely.")


async def _process_webhook_event(webhook_event_id: str):
    async with async_session_factory() as db:
        result = await db.execute(select(WebhookEvent).where(WebhookEvent.id == webhook_event_id))
        webhook_row = result.scalar_one_or_none()
        if not webhook_row:
            logger.error(f"WebhookEvent {webhook_event_id} not found in DB.")
            return

        payload = webhook_row.raw_payload
        event_type = webhook_row.event_type

        if event_type in ["stablecoin.usdc.received.success", "stablecoin.usdt.received.success"]:
            logger.info(f"Received stablecoin webhook: {webhook_row.event_id}")
            pass
        elif event_type == "btc.received.success":
            logger.info(f"Received BTC webhook: {webhook_row.event_id}")
            pass
        elif event_type == "ln.invoice.paid":
            logger.info(f"Received Lightning webhook: {webhook_row.event_id}")
            pass
        else:
            logger.info(f"Ignoring unhandled webhook event type: {event_type}")
            return
            
        # Placeholder for exactly evaluating reconciliation
        # e.g.:
        # invoice = await ReconciliationService.reconcile(invoice_id)
        # if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERPAID]:
        #     generate_receipt.delay(str(invoice.id), str(payment_id))
        pass


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_webhook_event(self, webhook_event_id: str):
    try:
        asyncio.run(_process_webhook_event(webhook_event_id))
    except Exception as exc:
        logger.exception("Error processing webhook")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3)
def send_email(self, template_id: str, recipient: str, subject: str, data: dict, attachment_path: str = None):
    # Implemented Resend integration
    import resend
    from app.config import settings

    if not settings.RESEND_API_KEY:
        logger.warning(f"RESEND_API_KEY not set. Skipping email '{subject}' to {recipient}")
        return

    resend.api_key = settings.RESEND_API_KEY

    # Build simple HTML body dynamically based on template_id
    html_body = f"<h2>{subject}</h2><p>Hello,</p>"
    if template_id == "receipt":
        html_body += f"<p>Attached is the receipt for {data.get('amount')} USD from {data.get('business_name')} for your payment.</p>"
    elif template_id == "payment_link":
        html_body += f"<p>Please complete your payment via this link: <a href='{data.get('invoice_url')}'>Pay Now</a></p>"
    else:
        html_body += "<p>You have a new message from the invoicing platform.</p>"

    # Download attachment if it's an S3 link (Resend attachment expects bytes)
    attachments = []
    if attachment_path and attachment_path.startswith("http"):
        try:
            import httpx
            with httpx.Client() as client:
                r = client.get(attachment_path)
                r.raise_for_status()
                # Determine filename
                filename = "receipt.pdf"
                if "receipts/" in attachment_path:
                    filename = attachment_path.split("/")[-1]
                
                attachments.append({
                    "filename": filename,
                    "content": list(r.content) # Resend sometimes wants bytes passed as an array for attachments
                })
        except Exception as e:
            logger.error(f"Failed to fetch attachment from S3 for email: {e}")

    try:
        params = {
            "from": settings.EMAIL_FROM_ADDRESS,
            "to": [recipient],
            "subject": subject,
            "html": html_body,
        }
        if attachments:
            params["attachments"] = attachments

        email_res = resend.Emails.send(params)
        logger.info(f"Successfully sent email via Resend to {recipient}. ID: {email_res.get('id')}")
    except Exception as exc:
        logger.exception("Error sending email via Resend")
        raise self.retry(exc=exc)


async def _generate_receipt(invoice_id: str, payment_id: str = None):
    from app.services.receipt_service import ReceiptService
    import uuid
    from sqlalchemy import select
    from app.models.invoice import Invoice

    async with async_session_factory() as db:
        receipt = await ReceiptService.generate_receipt_pdf(
            db, uuid.UUID(invoice_id), uuid.UUID(payment_id) if payment_id else None
        )
        
        # Load invoice for email dispatch routing
        result = await db.execute(select(Invoice).where(Invoice.id == uuid.UUID(invoice_id)))
        invoice = result.scalar_one()
        await db.refresh(invoice, ["user"])

        send_email.delay(
            template_id="receipt",
            recipient=invoice.client_email,
            subject=f"Receipt for Invoice {invoice.bitnob_reference}",
            data={
                "business_name": invoice.user.business_name if invoice.user else "Freelancer", 
                "amount": str(invoice.amount_received_usd_equiv)
            },
            attachment_path=receipt.pdf_path
        )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_receipt(self, invoice_id: str, payment_id: str = None):
    try:
        asyncio.run(_generate_receipt(invoice_id, payment_id))
    except Exception as exc:
        logger.exception("Error generating receipt")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# Milestone 8 — Celery Beat periodic jobs
# ─────────────────────────────────────────────────────────────────────────────

async def _expire_stale_payment_targets():
    """
    PRD 9.1 — runs every 1 minute.
    Marks all active PaymentTargets whose expires_at has passed as is_active=False.
    If the linked invoice has zero successful payments AND no remaining active
    targets, transitions it to EXPIRED via ReconciliationService.
    """
    from datetime import datetime, timezone
    from decimal import Decimal
    from sqlalchemy import update

    from app.models.invoice import Invoice
    from app.services.reconciliation_service import InvalidStateTransitionError

    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        # 1. Fetch all stale-but-still-active targets
        stale_result = await db.execute(
            select(PaymentTarget).where(
                PaymentTarget.is_active == True,
                PaymentTarget.expires_at < now,
            )
        )
        stale_targets = stale_result.scalars().all()

        if not stale_targets:
            return

        affected_invoice_ids = set()
        for target in stale_targets:
            target.is_active = False
            affected_invoice_ids.add(target.invoice_id)

        await db.commit()
        logger.info(f"[expiry] Deactivated {len(stale_targets)} stale payment targets.")

        # 2. For each affected invoice, check whether it should be expired
        for invoice_id in affected_invoice_ids:
            invoice_result = await db.execute(
                select(Invoice).where(Invoice.id == invoice_id).with_for_update()
            )
            invoice = invoice_result.scalar_one_or_none()
            if not invoice:
                continue

            # Only act on invoices that are still in a transient state
            if invoice.status not in [InvoiceStatus.PENDING, InvoiceStatus.DRAFT]:
                continue

            # Check if any Payment rows exist at all
            payment_result = await db.execute(
                select(Payment).where(Payment.invoice_id == invoice_id).limit(1)
            )
            has_payments = payment_result.scalar_one_or_none() is not None

            if has_payments:
                # Payments exist; reconciliation already handled status
                continue

            # Check remaining active targets
            active_result = await db.execute(
                select(PaymentTarget).where(
                    PaymentTarget.invoice_id == invoice_id,
                    PaymentTarget.is_active == True,
                ).limit(1)
            )
            has_active = active_result.scalar_one_or_none() is not None

            if not has_active:
                try:
                    invoice.status = InvoiceStatus.EXPIRED
                    await db.commit()
                    logger.info(f"[expiry] Invoice {invoice_id} transitioned to EXPIRED.")
                except Exception:
                    logger.exception(f"[expiry] Failed to expire invoice {invoice_id}")
                    await db.rollback()


@celery_app.task
def expire_stale_payment_targets():
    """Celery Beat entry-point — every 1 minute."""
    asyncio.run(_expire_stale_payment_targets())


async def _reconciliation_sweep():
    """
    PRD 9.2 — runs every 5 minutes.
    For every PENDING / PARTIALLY_PAID invoice with at least one active target,
    calls BitnobClient.list_transactions(reference=...) to detect payments
    whose inbound webhook was dropped. Any discovered transactions not already
    present in the local `payments` table are inserted and the exact same
    ReconciliationService.reconcile() path is triggered.
    """
    from decimal import Decimal
    from app.models.invoice import Invoice
    from app.services.bitnob_client import BitnobClient
    from app.services.reconciliation_service import ReconciliationService

    async with async_session_factory() as db:
        # Find all invoices in transient states that have at least one active target
        pending_result = await db.execute(
            select(Invoice).where(
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID])
            )
        )
        invoices = pending_result.scalars().all()

        if not invoices:
            return

        client = BitnobClient()
        try:
            for invoice in invoices:
                # Confirm at least one active target (not worth sweeping if no target)
                active_target_res = await db.execute(
                    select(PaymentTarget).where(
                        PaymentTarget.invoice_id == invoice.id,
                        PaymentTarget.is_active == True,
                    ).limit(1)
                )
                if not active_target_res.scalar_one_or_none():
                    continue

                try:
                    tx_resp = await client.list_transactions(
                        reference=invoice.bitnob_reference
                    )
                except Exception:
                    logger.warning(f"[sweep] Failed to fetch transactions for invoice {invoice.id}.")
                    continue

                transactions = tx_resp.get("data", [])
                if not isinstance(transactions, list):
                    transactions = [transactions] if transactions else []

                for tx in transactions:
                    tx_hash = tx.get("hash") or tx.get("tx_hash") or tx.get("id")
                    if not tx_hash:
                        continue

                    # Check if this payment already exists locally
                    existing = await db.execute(
                        select(Payment).where(Payment.tx_hash == tx_hash)
                    )
                    if existing.scalar_one_or_none():
                        continue  # Already recorded — no action needed

                    # New payment found via sweep — record it + reconcile
                    logger.info(f"[sweep] Discovered missed payment {tx_hash} for invoice {invoice.id}.")
                    amount_crypto = Decimal(str(tx.get("amount", "0")))
                    usd_equiv = Decimal(str(tx.get("amountUsd") or tx.get("amount_usd") or "0"))
                    method = tx.get("type", "unknown").lower()

                    new_payment = Payment(
                        invoice_id=invoice.id,
                        tx_hash=tx_hash,
                        method=method,
                        amount_received_crypto=amount_crypto,
                        amount_received_usd_equiv=usd_equiv,
                    )
                    db.add(new_payment)
                    try:
                        await db.flush()
                        svc = ReconciliationService(db)
                        updated_invoice = await svc.reconcile(invoice.id)
                        logger.info(
                            f"[sweep] Invoice {invoice.id} reconciled via sweep → {updated_invoice.status.value}"
                        )
                        if updated_invoice.status in [
                            InvoiceStatus.PAID,
                            InvoiceStatus.PARTIALLY_PAID,
                            InvoiceStatus.OVERPAID,
                        ]:
                            generate_receipt.delay(str(invoice.id), str(new_payment.id))
                    except Exception:
                        logger.exception(f"[sweep] Reconciliation failed for invoice {invoice.id}.")
                        await db.rollback()
        finally:
            await client.close()


@celery_app.task
def reconciliation_sweep():
    """Celery Beat entry-point — every 5 minutes."""
    asyncio.run(_reconciliation_sweep())

