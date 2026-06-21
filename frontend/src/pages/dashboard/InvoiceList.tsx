import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { StatusBadge } from "../../components/StatusBadge";
import { getInvoices } from "../../lib/api/invoices";
import { formatUSD } from "../../lib/decimal";
import type { Invoice, InvoiceStatus } from "../../lib/api/types";
import { Plus } from "lucide-react";

const FILTER_OPTIONS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Paid", value: "paid" },
  { label: "Overpaid", value: "overpaid" },
  { label: "Expired", value: "expired" },
  { label: "Cancelled", value: "cancelled" },
];

export default function InvoiceList() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    getInvoices({ status: filter || undefined })
      .then((res) => setInvoices(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-display-md">Invoices</h1>
        <Link to="/dashboard/invoices/new">
          <Button variant="primary" className="bg-white text-ink hover:bg-silver gap-2">
            <Plus size={16} /> New Invoice
          </Button>
        </Link>
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap gap-2">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            className={`px-3 py-1.5 rounded-sm text-body-sm font-medium border transition-colors ${
              filter === opt.value
                ? "bg-white/10 text-white border-white/20"
                : "text-silver-dim border-line hover:text-white hover:border-silver-dim"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-ink-raised rounded-lg border border-line animate-pulse" />
          ))}
        </div>
      ) : invoices.length === 0 ? (
        <Card className="p-12 text-center space-y-4">
          <p className="text-silver-dim">No invoices found.</p>
          <Link to="/dashboard/invoices/new">
            <Button variant="primary" className="bg-white text-ink hover:bg-silver">Create your first invoice</Button>
          </Link>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          {/* Header */}
          <div className="hidden md:grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 px-4 py-3 border-b border-line text-[11px] text-silver-dim uppercase tracking-wider font-medium">
            <span>Client</span>
            <span className="w-28 text-right">Amount</span>
            <span className="w-32">Status</span>
            <span className="w-28">Created</span>
            <span className="w-20" />
          </div>
          {/* Rows */}
          {invoices.map((inv) => (
            <Link
              key={inv.id}
              to={`/dashboard/invoices/${inv.id}`}
              className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto_auto] gap-2 md:gap-4 px-4 py-4 border-b border-line last:border-b-0 hover:bg-white/[0.02] transition-colors items-center"
            >
              <div>
                <p className="text-body-sm text-white font-medium">{inv.client_name}</p>
                <p className="text-[11px] text-silver-dim truncate max-w-xs">{inv.description || "No description"}</p>
              </div>
              <span className="w-28 text-right text-body-sm text-white font-mono">${formatUSD(inv.amount_usd)}</span>
              <span className="w-32"><StatusBadge status={inv.status} /></span>
              <span className="w-28 text-body-sm text-silver-dim">{new Date(inv.created_at).toLocaleDateString()}</span>
              <span className="w-20 text-body-sm text-silver-dim text-right">View →</span>
            </Link>
          ))}
        </Card>
      )}
    </div>
  );
}
