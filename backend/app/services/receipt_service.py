import os
import uuid
from datetime import datetime

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.receipt import Receipt


class ReceiptPDF(FPDF):
    """Custom PDF class for professional receipt generation."""

    def header(self):
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(44, 62, 80)
        self.cell(0, 12, self._business_name, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(127, 140, 141)
        self.cell(0, 6, f"Reference: {self._invoice_reference}", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6, f"Date: {self._timestamp}", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(220, 220, 220)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(8)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(220, 220, 220)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(149, 165, 166)
        self.cell(0, 10, "Thank you for your payment!", align="C")


class ReceiptService:
    @staticmethod
    async def generate_receipt_pdf(
        db: AsyncSession, invoice_id: uuid.UUID, payment_id: uuid.UUID | None = None
    ) -> Receipt:
        invoice_res = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = invoice_res.scalar_one_or_none()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found.")

        await db.refresh(invoice, ["user"])

        # Attempt to load the specific payment to derive tx_hash
        payment_info = {}
        if payment_id:
            payment_res = await db.execute(select(Payment).where(Payment.id == payment_id))
            payment = payment_res.scalar_one_or_none()
            if payment:
                payment_info = {
                    "method": payment.method.upper() if payment.method else "Crypto",
                    "tx_hash": payment.tx_hash or "N/A",
                    "amount_crypto": str(payment.amount_received_crypto),
                    "amount_usd": str(payment.amount_received_usd_equiv),
                    "explorer_link": (
                        f"https://tronscan.org/#/transaction/{payment.tx_hash}" if payment.method == "usdt"
                        else f"https://etherscan.io/tx/{payment.tx_hash}" if payment.method == "usdc"
                        else f"https://mempool.space/tx/{payment.tx_hash}"
                    )
                }
        if not payment_info:
            payment_info = {
                "method": "Multiple/Aggregate",
                "tx_hash": "N/A",
                "amount_crypto": "N/A",
                "amount_usd": str(invoice.amount_received_usd_equiv),
                "explorer_link": "#"
            }

        business_name = invoice.user.business_name if invoice.user else "Freelancer"
        invoice_reference = invoice.busha_reference
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Build the PDF
        pdf = ReceiptPDF()
        pdf._business_name = business_name
        pdf._invoice_reference = invoice_reference
        pdf._timestamp = timestamp
        pdf.set_auto_page_break(auto=True, margin=30)
        pdf.add_page()

        # "RECEIPT" title on right side
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(127, 140, 141)
        pdf.cell(0, 10, "RECEIPT", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # Billed To section
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 8, "Billed To", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(238, 238, 238)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(51, 51, 51)
        pdf.cell(0, 6, invoice.client_name, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # Description section
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 8, "Description", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(238, 238, 238)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 51, 51)
        pdf.multi_cell(0, 6, invoice.description or "Invoice Payment")
        pdf.ln(8)

        # Payment Details Table
        col_widths = [40, 60, 40, 40]
        headers = ["Method", "Transaction Hash", "Amount Paid", "USD Equivalent"]

        # Table header
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(127, 140, 141)
        pdf.set_fill_color(245, 245, 245)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 10, header, border=0, fill=True)
        pdf.ln()

        # Table row
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(44, 62, 80)
        values = [
            payment_info["method"],
            (payment_info["tx_hash"][:20] + "...") if len(payment_info["tx_hash"]) > 20 else payment_info["tx_hash"],
            payment_info["amount_crypto"],
            f"${payment_info['amount_usd']}",
        ]
        for i, val in enumerate(values):
            pdf.cell(col_widths[i], 10, str(val), border=0)
        pdf.ln()

        # Generate PDF bytes
        pdf_bytes = pdf.output()

        # Upload to S3
        filename = f"receipts/{invoice.busha_reference}_{uuid.uuid4().hex[:6]}.pdf"
        from app.services.s3_service import S3Service
        s3_url = S3Service.upload_file(pdf_bytes, filename)

        # Persist receipt record
        receipt = Receipt(
            invoice_id=invoice.id,
            payment_id=payment_id,
            pdf_path=s3_url
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt)

        return receipt
