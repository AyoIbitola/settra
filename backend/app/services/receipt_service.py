import os
import uuid
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.receipt import Receipt

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "receipts")


class ReceiptService:
    @staticmethod
    async def generate_receipt_pdf(
        db: AsyncSession, invoice_id: uuid.UUID, payment_id: uuid.UUID | None = None
    ) -> Receipt:
        # Load invoice and related user. Use scalar_one_or_none. 
        # (Assuming the relations are loaded or simply query join)
        invoice_res = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = invoice_res.scalar_one_or_none()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found.")
            
        # Manually load the user business name and client details.
        await db.refresh(invoice, ["user"])

        # Attempt to load the specific payment to derive tx_hash
        payment_info = {}
        if payment_id:
            payment_res = await db.execute(select(Payment).where(Payment.id == payment_id))
            payment = payment_res.scalar_one_or_none()
            if payment:
                payment_info = {
                    "method": payment.method.upper() if payment.method else "Crypto",
                    "tx_hash": payment.tx_hash,
                    "amount_crypto": payment.amount_received_crypto,
                    "amount_usd": payment.amount_received_usd_equiv,
                    # PRD 11.2: Compute explorer link
                    "explorer_link": f"https://polygonscan.com/tx/{payment.tx_hash}" if payment.method in ["usdc", "usdt"] else f"https://mempool.space/tx/{payment.tx_hash}"
                }
        else:
            # Fallback if no specific payment provided (e.g., aggregate receipt)
            payment_info = {
                "method": "Multiple/Aggregate",
                "tx_hash": "N/A",
                "amount_crypto": "N/A",
                "amount_usd": invoice.amount_received_usd_equiv,
                "explorer_link": "#"
            }

        # Setup Jinja
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template("receipt.html")
        
        # Render HTML
        html_out = template.render(
            business_name=invoice.user.business_name if invoice.user else "Freelancer",
            invoice_reference=invoice.bitnob_reference,
            timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            client_name=invoice.client_name,
            description=invoice.description or "Invoice Payment",
            **payment_info
        )

        # Generate unique object key for S3
        filename = f"receipts/{invoice.bitnob_reference}_{uuid.uuid4().hex[:6]}.pdf"

        # WeasyPrint PDF generation -> Memory bytes
        pdf_bytes = HTML(string=html_out).write_pdf()

        # Upload to S3
        from app.services.s3_service import S3Service
        s3_url = S3Service.upload_file(pdf_bytes, filename)

        # Persist standard record
        receipt = Receipt(
            invoice_id=invoice.id,
            payment_id=payment_id,
            pdf_path=s3_url  # Storing the S3 URL instead of a local path
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        return receipt
