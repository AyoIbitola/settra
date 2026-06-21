import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Awaitable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import async_session_factory, engine
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.payment_target import PaymentTarget
from app.models.webhook_event import WebhookEvent
from app.services.reconciliation_service import ReconciliationService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_and_dispose(coro: Awaitable[Any]) -> Any:
    """
    Celery tasks are sync functions, so each task uses asyncio.run().
    Dispose pooled asyncpg connections before that per-task event loop closes;
    otherwise the next task can reuse a connection bound to the wrong loop.
    """
    try:
        return await coro
    finally:
        await engine.dispose()


def run_async_task(coro: Awaitable[Any]) -> Any:
    return asyncio.run(_run_and_dispose(coro))


# ---------------------------------------------------------------------------
# Busha Event Handlers
# ---------------------------------------------------------------------------

async def handle_payment_request_completed(db, webhook_row: WebhookEvent) -> None:
    """
    PRD §8.4 — triggered when `payment_request.completed` arrives.
    Maps the payment request back to the original invoice via `busha_link_id`,
    records a Payment row, and runs ReconciliationService.
    """
    payload = webhook_row.raw_payload
    data = payload.get("data", {})

    # ── 1. Resolve invoice by the payment link id ──────────────────────────
    # Busha's payment_request.completed carries the parent link_id.
    # We stored invoice.busha_link_id when generating the checkout link in M4.
    link_id = (
        data.get("payment_link_id")
        or data.get("link_id")
        or data.get("payment_link", {}).get("id")
    )
    if not link_id:
        logger.warning(
            f"[webhook] Cannot resolve invoice — no link_id in payload. "
            f"dedup_key={webhook_row.event_dedup_key}"
        )
        return

    invoice_result = await db.execute(
        select(Invoice)
        .where(Invoice.busha_link_id == link_id)
        .with_for_update()
    )
    invoice = invoice_result.scalar_one_or_none()
    if not invoice:
        logger.error(
            f"[webhook] No invoice found for busha_link_id={link_id}. "
            f"Possible test event or reference mismatch — not retrying."
        )
        return

    # ── 2. Extract amounts ─────────────────────────────────────────────────
    # Busha may return `source_amount` (crypto) and a `quote_amount` (USD).
    # We use target/quote as the USD-equivalent since we always quote in USD.
    amount_crypto = Decimal(str(data.get("source_amount", "0") or "0"))
    # USD equivalent: prefer target_amount (quote), fall back to source_amount
    amount_usd_raw = (
        data.get("target_amount")
        or data.get("quote_amount")
        or data.get("source_amount")
        or "0"
    )
    amount_usd_equiv = Decimal(str(amount_usd_raw))
    method = (data.get("source_currency", "unknown") or "unknown").lower()
    network = data.get("network", None)

    # Busha may include a blockchain hash for on-chain payments.
    tx_hash = (
        data.get("pay_in", {}).get("blockchain_hash")
        or data.get("blockchain_hash")
        or data.get("id")  # fallback: use the payment request id as tx_hash
    )
    if not tx_hash:
        logger.error(
            f"[webhook] No tx_hash in Busha payload for invoice {invoice.id}. Cannot record payment."
        )
        return

    # ── 3. Record Payment row (idempotent) ─────────────────────────────────
    existing_payment = await db.execute(
        select(Payment).where(
            Payment.invoice_id == invoice.id,
            Payment.tx_hash == tx_hash,
        )
    )
    if existing_payment.scalar_one_or_none():
        logger.info(f"[webhook] Payment {tx_hash} already recorded for invoice {invoice.id}. Skipping.")
        return

    new_payment = Payment(
        invoice_id=invoice.id,
        tx_hash=tx_hash,
        method=method,
        network=network,
        amount_received_crypto=amount_crypto,
        amount_received_usd_equiv=amount_usd_equiv,
        confirmations=1,  # completed = confirmed by Busha
        busha_payment_request_id=data.get("id", ""),
        received_at=datetime.now(timezone.utc),
    )
    db.add(new_payment)

    try:
        await db.flush()
    except IntegrityError:
        logger.warning(f"[webhook] Duplicate payment tx_hash={tx_hash} — IntegrityError caught, skipping.")
        await db.rollback()
        return

    # ── 4. Reconcile invoice ledger ────────────────────────────────────────
    svc = ReconciliationService(db)
    updated_invoice = await svc.reconcile(invoice.id)
    logger.info(
        f"[webhook] Invoice {invoice.id} reconciled → {updated_invoice.status.value}"
    )

    # ── 5. Trigger receipt generation if payment event warrants it ─────────
    if updated_invoice.status in [
        InvoiceStatus.PAID,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.OVERPAID,
    ]:
        generate_receipt.delay(str(invoice.id), str(new_payment.id))


# Map Busha event types to handlers. Unrecognised events are silently ack'd.
_EVENT_HANDLERS = {
    "payment_request.completed": handle_payment_request_completed,
    # Informational-only events — log and ack, do NOT reconcile.
    "payment_request.pending":    None,
    "payment_request.processing": None,
    "payment_request.expired":    None,
    "payment_request.failed":     None,
    "payment_request.cancelled":  None,
}


async def _process_webhook_event(webhook_event_id: str):
    async with async_session_factory() as db:
        result = await db.execute(
            select(WebhookEvent).where(WebhookEvent.id == webhook_event_id)
        )
        webhook_row = result.scalar_one_or_none()
        if not webhook_row:
            logger.error(f"WebhookEvent {webhook_event_id} not found in DB.")
            return

        event_type = webhook_row.event_type
        logger.info(f"[webhook] Processing event_type={event_type} id={webhook_event_id}")

        handler = _EVENT_HANDLERS.get(event_type)
        if handler is None:
            if event_type not in _EVENT_HANDLERS:
                logger.info(f"[webhook] Unrecognised event type '{event_type}' — ignoring.")
            else:
                logger.debug(f"[webhook] Informational event '{event_type}' — no-op.")
            webhook_row.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        try:
            await handler(db, webhook_row)
            webhook_row.processed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as exc:
            webhook_row.processing_error = str(exc)
            await db.commit()
            raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_webhook_event(self, webhook_event_id: str):
    try:
        run_async_task(_process_webhook_event(webhook_event_id))
    except Exception as exc:
        logger.exception("Error processing webhook")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Email Task
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3)
def send_email(self, template_id: str, recipient: str, subject: str, data: dict, attachment_path: str = None):
    import resend
    from app.config import settings

    if not settings.RESEND_API_KEY:
        logger.warning(f"RESEND_API_KEY not set. Skipping email '{subject}' to {recipient}")
        return

    resend.api_key = settings.RESEND_API_KEY

    html_body = f"<h2>{subject}</h2><p>Hello,</p>"
    if template_id == "receipt":
        html_body += f"<p>Attached is the receipt for {data.get('amount')} USD from {data.get('business_name')} for your payment.</p>"
    elif template_id == "payment_link":
        html_body += f"<p>Please complete your payment via this link: <a href='{data.get('invoice_url')}'>Pay Now</a></p>"
    else:
        html_body += "<p>You have a new message from the invoicing platform.</p>"

    attachments = []
    if attachment_path and attachment_path.startswith("http"):
        try:
            import boto3
            bucket = settings.AWS_S3_BUCKET_NAME
            # Parse the S3 key out of the Amazon URL
            key = attachment_path.split(".amazonaws.com/")[-1]
            
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            response = s3.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()
            
            filename = "receipt.pdf"
            if "receipts/" in attachment_path:
                filename = attachment_path.split("/")[-1]
            attachments.append({"filename": filename, "content": list(content)})
        except Exception as e:
            logger.error(f"Failed to fetch attachment from S3 for email using boto3: {e}")

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
        logger.info(f"Email sent via Resend to {recipient}. ID: {email_res.get('id')}")
    except Exception as exc:
        logger.exception("Error sending email via Resend")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Receipt Generation
# ---------------------------------------------------------------------------

async def _generate_receipt(invoice_id: str, payment_id: str = None):
    import uuid
    from app.models.invoice import Invoice
    from app.services.receipt_service import ReceiptService

    async with async_session_factory() as db:
        receipt = await ReceiptService.generate_receipt_pdf(
            db, uuid.UUID(invoice_id), uuid.UUID(payment_id) if payment_id else None
        )
        result = await db.execute(select(Invoice).where(Invoice.id == uuid.UUID(invoice_id)))
        invoice = result.scalar_one()
        await db.refresh(invoice, ["user"])

        send_email.delay(
            template_id="receipt",
            recipient=invoice.client_email,
            subject=f"Receipt for Invoice {invoice.busha_reference}",
            data={
                "business_name": invoice.user.business_name if invoice.user else "Freelancer",
                "amount": str(invoice.amount_received_usd_equiv),
            },
            attachment_path=receipt.pdf_path,
        )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_receipt(self, invoice_id: str, payment_id: str = None):
    try:
        run_async_task(_generate_receipt(invoice_id, payment_id))
    except Exception as exc:
        logger.exception("Error generating receipt")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# M8 — Celery Beat periodic jobs
# ---------------------------------------------------------------------------

async def _expire_stale_payment_targets():
    """PRD §9.1 — runs every 1 minute. Marks stale PaymentTargets inactive."""
    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        stale_result = await db.execute(
            select(PaymentTarget).where(
                PaymentTarget.is_active,
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

        for invoice_id in affected_invoice_ids:
            invoice_result = await db.execute(
                select(Invoice).where(Invoice.id == invoice_id).with_for_update()
            )
            invoice = invoice_result.scalar_one_or_none()
            if not invoice:
                continue
            if invoice.status not in [InvoiceStatus.PENDING, InvoiceStatus.DRAFT]:
                continue

            payment_result = await db.execute(
                select(Payment).where(Payment.invoice_id == invoice_id).limit(1)
            )
            if payment_result.scalar_one_or_none():
                continue

            active_result = await db.execute(
                select(PaymentTarget).where(
                    PaymentTarget.invoice_id == invoice_id,
                    PaymentTarget.is_active,
                ).limit(1)
            )
            if not active_result.scalar_one_or_none():
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
    run_async_task(_expire_stale_payment_targets())


async def _reconciliation_sweep():
    """
    PRD §9.2 — runs every 5 minutes.
    For every PENDING / PARTIALLY_PAID invoice with a busha_link_id,
    fetches payment requests from Busha to find any missed webhook payments.
    """
    from app.services.busha_client import BushaClient

    async with async_session_factory() as db:
        pending_result = await db.execute(
            select(Invoice).where(
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID]),
                Invoice.busha_link_id.isnot(None),
            )
        )
        invoices = pending_result.scalars().all()

        if not invoices:
            return

        async with BushaClient() as client:
            for invoice in invoices:
                try:
                    # Fetch payment requests made against this checkout link
                    resp = await client.get(
                        f"/v1/payments/links/{invoice.busha_link_id}/requests"
                    )
                    requests_data = resp.get("data", [])
                    if not isinstance(requests_data, list):
                        requests_data = [requests_data] if requests_data else []
                except Exception:
                    logger.warning(f"[sweep] Failed to fetch payment requests for invoice {invoice.id}.")
                    continue

                for pr in requests_data:
                    if pr.get("status") != "completed":
                        continue

                    tx_hash = (
                        pr.get("pay_in", {}).get("blockchain_hash")
                        or pr.get("blockchain_hash")
                        or pr.get("id")
                    )
                    if not tx_hash:
                        continue

                    existing = await db.execute(
                        select(Payment).where(
                            Payment.invoice_id == invoice.id,
                            Payment.tx_hash == tx_hash,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    logger.info(f"[sweep] Missed payment {tx_hash} for invoice {invoice.id}.")
                    amount_usd = Decimal(str(pr.get("target_amount") or pr.get("quote_amount") or "0"))
                    amount_crypto = Decimal(str(pr.get("source_amount", "0")))
                    method = (pr.get("source_currency", "unknown") or "unknown").lower()

                    new_payment = Payment(
                        invoice_id=invoice.id,
                        tx_hash=tx_hash,
                        method=method,
                        amount_received_crypto=amount_crypto,
                        amount_received_usd_equiv=amount_usd,
                        confirmations=1,
                        busha_payment_request_id=pr.get("id", ""),
                        received_at=datetime.now(timezone.utc),
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


@celery_app.task
def reconciliation_sweep():
    """Celery Beat entry-point — every 5 minutes."""
    run_async_task(_reconciliation_sweep())
