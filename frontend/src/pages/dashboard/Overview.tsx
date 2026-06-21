import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { StatusBadge } from "../../components/StatusBadge";
import { getInvoices } from "../../lib/api/invoices";
import { formatUSD } from "../../lib/decimal";
import type { Invoice } from "../../lib/api/types";
import { Decimal } from "decimal.js";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Clock, AlertTriangle, ArrowRight } from "lucide-react";

export default function Overview() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getInvoices({ page_size: 50 })
      .then((res) => setInvoices(res.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const outstanding = invoices
    .filter((i) => i.status === "pending" || i.status === "partially_paid")
    .reduce((sum, i) => sum.plus(i.amount_usd), new Decimal(0));

  const paidTotal = invoices
    .filter((i) => i.status === "paid" || i.status === "overpaid")
    .reduce((sum, i) => sum.plus(i.amount_received_usd_equiv), new Decimal(0));

  const unresolvedOverpayments = invoices.filter((i) => i.status === "overpaid").length;
  const pendingCount = invoices.filter((i) => i.status === "pending").length;

  // Generate chart data from invoices (group by month)
  const chartData = useMemo(() => {
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const now = new Date();
    const data = [];

    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const monthLabel = months[d.getMonth()];
      const monthInvoices = invoices.filter((inv) => {
        const invDate = new Date(inv.created_at);
        return invDate.getMonth() === d.getMonth() && invDate.getFullYear() === d.getFullYear();
      });
      const revenue = monthInvoices
        .filter((inv) => inv.status === "paid" || inv.status === "overpaid")
        .reduce((sum, inv) => sum.plus(inv.amount_received_usd_equiv), new Decimal(0));
      const invoiced = monthInvoices.reduce((sum, inv) => sum.plus(inv.amount_usd), new Decimal(0));

      data.push({
        month: monthLabel,
        revenue: revenue.toNumber(),
        invoiced: invoiced.toNumber(),
      });
    }
    return data;
  }, [invoices]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-ink-raised rounded" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => <div key={i} className="h-32 bg-ink-raised rounded-lg border border-line" />)}
        </div>
        <div className="h-64 bg-ink-raised rounded-lg border border-line" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-display-md">Overview</h1>
        <Link
          to="/dashboard/invoices/new"
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-white text-ink font-medium text-body-sm hover:bg-silver transition-colors"
        >
          New Invoice <ArrowRight size={14} />
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="relative p-6 space-y-3 overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-signal/[0.04] to-transparent pointer-events-none" />
          <div className="flex items-center justify-between relative">
            <p className="text-body-sm text-silver-dim">Total received</p>
            <div className="w-8 h-8 rounded-md bg-signal/10 flex items-center justify-center">
              <TrendingUp size={16} className="text-signal" />
            </div>
          </div>
          <p className="text-display-md text-white font-display relative" style={{ color: "var(--color-signal)" }}>
            ${formatUSD(paidTotal.toString())}
          </p>
          <p className="text-[11px] text-silver-dim relative">Lifetime revenue</p>
        </Card>

        <Card className="relative p-6 space-y-3 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-amber/[0.04] to-transparent pointer-events-none" />
          <div className="flex items-center justify-between relative">
            <p className="text-body-sm text-silver-dim">Outstanding</p>
            <div className="w-8 h-8 rounded-md bg-amber/10 flex items-center justify-center">
              <Clock size={16} className="text-amber" />
            </div>
          </div>
          <p className="text-display-md text-white font-display relative">
            ${formatUSD(outstanding.toString())}
          </p>
          <p className="text-[11px] text-silver-dim relative">{pendingCount} pending invoice{pendingCount !== 1 ? "s" : ""}</p>
        </Card>

        <Card className="relative p-6 space-y-3 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-danger/[0.04] to-transparent pointer-events-none" />
          <div className="flex items-center justify-between relative">
            <p className="text-body-sm text-silver-dim">Overpayments</p>
            <div className={`w-8 h-8 rounded-md flex items-center justify-center ${unresolvedOverpayments > 0 ? "bg-danger/10" : "bg-silver-dim/10"}`}>
              <AlertTriangle size={16} className={unresolvedOverpayments > 0 ? "text-danger" : "text-silver-dim"} />
            </div>
          </div>
          <p className={`text-display-md font-display relative ${unresolvedOverpayments > 0 ? "text-danger" : "text-silver-dim"}`}>
            {unresolvedOverpayments}
          </p>
          {unresolvedOverpayments > 0 && (
            <Link to="/dashboard/overpayments" className="text-[11px] text-danger hover:underline relative">
              Needs attention →
            </Link>
          )}
          {unresolvedOverpayments === 0 && (
            <p className="text-[11px] text-silver-dim relative">All resolved</p>
          )}
        </Card>
      </div>

      {/* Revenue chart */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-body-lg font-semibold text-white">Revenue (6 months)</h2>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-signal" /> Received
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-silver-dim" /> Invoiced
            </span>
          </div>
        </div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-signal)" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="var(--color-signal)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="invoicedGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7a7a85" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#7a7a85" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="month"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#7a7a85", fontSize: 11 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#7a7a85", fontSize: 11 }}
                tickFormatter={(v) => `$${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`}
                width={50}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a2e",
                  border: "1px solid #2a2a3e",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#fff",
                }}
                formatter={(value: number) => [`$${formatUSD(value.toString())}`, ""]}
                labelStyle={{ color: "#7a7a85" }}
              />
              <Area
                type="monotone"
                dataKey="invoiced"
                stroke="#7a7a85"
                strokeWidth={1.5}
                fill="url(#invoicedGrad)"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="var(--color-signal)"
                strokeWidth={2}
                fill="url(#revenueGrad)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Recent activity */}
      <Card className="space-y-0">
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <h2 className="text-body-lg font-semibold text-white">Recent activity</h2>
          <Link to="/dashboard/invoices" className="text-body-sm text-silver-dim hover:text-white transition-colors">
            View all →
          </Link>
        </div>
        <div className="divide-y divide-line">
          {invoices.slice(0, 5).map((inv) => (
            <Link
              key={inv.id}
              to={`/dashboard/invoices/${inv.id}`}
              className="flex items-center justify-between px-6 py-4 hover:bg-white/[0.02] transition-colors"
            >
              <div className="space-y-1">
                <p className="text-body-sm text-white font-medium">{inv.client_name}</p>
                <p className="text-[11px] text-silver-dim">{new Date(inv.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-body-sm text-white font-mono">${formatUSD(inv.amount_usd)}</span>
                <StatusBadge status={inv.status} />
              </div>
            </Link>
          ))}
          {invoices.length === 0 && (
            <div className="px-6 py-12 text-center text-silver-dim text-body-sm">
              No invoices yet. <Link to="/dashboard/invoices/new" className="text-white hover:underline">Create your first</Link>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
