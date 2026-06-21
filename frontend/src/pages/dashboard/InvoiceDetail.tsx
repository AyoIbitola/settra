import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { StatusBadge } from "../../components/StatusBadge";
import { getInvoice, cancelInvoice, resendInvoice } from "../../lib/api/invoices";
import { formatUSD } from "../../lib/decimal";
import type { Invoice } from "../../lib/api/types";
import { Copy, Check, ExternalLink } from "lucide-react";
import { Decimal } from "decimal.js";

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getInvoice(id)
      .then(setInvoice)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const payLink = `${window.location.origin}/pay/${id}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(payLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCancel = async () => {
    if (!id || !confirm("Cancel this invoice? This cannot be undone.")) return;
    try {
      await cancelInvoice(id);
      const updated = await getInvoice(id);
      setInvoice(updated);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleResend = async () => {
    if (!id) return;
    try {
      await resendInvoice(id);
      alert("Payment link has been resent.");
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-ink-raised rounded" />
        <div className="h-64 bg-ink-raised rounded-lg border border-line" />
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <Card className="p-8 text-center space-y-4">
        <p className="text-danger">{error || "Invoice not found"}</p>
        <Button variant="ghost" onClick={() => navigate("/dashboard/invoices")}>Back to invoices</Button>
      </Card>
    );
  }

  const received = new Decimal(invoice.amount_received_usd_equiv);
  const total = new Decimal(invoice.amount_usd);
  const progressPercent = total.gt(0) ? Math.min(received.div(total).mul(100).toNumber(), 100) : 0;
  const isOverpaid = new Decimal(invoice.overpaid_amount_usd).gt(0);

  return (
    <div className="space-y-8 max-w-3xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="text-display-md">{invoice.client_name}</h1>
            <StatusBadge status={invoice.status} />
          </div>
          <p className="text-body-sm text-silver-dim">{invoice.description || "No description"}</p>
        </div>
        <p className="text-display-md text-white font-mono">${formatUSD(invoice.amount_usd)}</p>
      </div>

      {/* Shareable link */}
      <Card className="p-4 flex items-center gap-3">
        <span className="text-body-sm text-silver-dim shrink-0">Pay link:</span>
        <input
          readOnly
          value={payLink}
          className="flex-1 bg-transparent text-mono-sm text-white outline-none truncate"
        />
        <Button variant="ghost" size="sm" onClick={handleCopy} className="shrink-0 gap-1.5">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </Card>

      {/* Payment progress */}
      <Card className="p-6 space-y-4">
        <h2 className="text-body-lg font-semibold text-white">Payment Ledger</h2>
        <div className="space-y-2">
          <div className="flex justify-between text-body-sm">
            <span className="text-silver-dim">Received</span>
            <span className="text-white font-mono">
              ${formatUSD(invoice.amount_received_usd_equiv)} of ${formatUSD(invoice.amount_usd)}
            </span>
          </div>
          <div className="w-full h-2 bg-line rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(progressPercent + (isOverpaid ? 5 : 0), 105)}%`,
                backgroundColor: isOverpaid ? "var(--color-signal)" : progressPercent >= 100 ? "var(--color-signal)" : "var(--color-amber)",
              }}
            />
          </div>
          {isOverpaid && (
            <p className="text-body-sm text-danger">
              Overpaid by ${formatUSD(invoice.overpaid_amount_usd)}
            </p>
          )}
        </div>
      </Card>

      {/* Details */}
      <Card className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-1">
            <p className="text-[11px] text-silver-dim uppercase">Client Email</p>
            <p className="text-body-sm text-white">{invoice.client_email}</p>
          </div>
          <div className="space-y-1">
            <p className="text-[11px] text-silver-dim uppercase">Invoice Reference</p>
            <p className="text-mono-sm text-white">{invoice.bitnob_reference}</p>
          </div>
          <div className="space-y-1">
            <p className="text-[11px] text-silver-dim uppercase">Created</p>
            <p className="text-body-sm text-white">{new Date(invoice.created_at).toLocaleString()}</p>
          </div>
          <div className="space-y-1">
            <p className="text-[11px] text-silver-dim uppercase">Due Date</p>
            <p className="text-body-sm text-white">{invoice.due_date || "None"}</p>
          </div>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <Button variant="ghost" onClick={handleResend}>Resend link</Button>
        {(invoice.status === "draft" || invoice.status === "pending") && (
          <Button variant="danger" onClick={handleCancel}>Cancel invoice</Button>
        )}
      </div>
    </div>
  );
}
