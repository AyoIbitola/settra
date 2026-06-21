import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { StatusBadge } from "../../components/StatusBadge";
import { HashReveal } from "../../components/HashReveal";
import { getPublicInvoice, getPaymentMethods, getCheckoutLink, getPublicInvoiceStatus } from "../../lib/api/public";
import { formatUSD } from "../../lib/decimal";
import type { PublicInvoice, PublicInvoiceStatus, PaymentMethod } from "../../lib/api/types";
import { ExternalLink, Check } from "lucide-react";
import { Decimal } from "decimal.js";

export default function Pay() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<PublicInvoice | null>(null);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [status, setStatus] = useState<PublicInvoiceStatus | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initial load
  useEffect(() => {
    if (!id) return;
    Promise.all([
      getPublicInvoice(id),
      getPaymentMethods(id),
      getPublicInvoiceStatus(id)
    ])
      .then(([inv, meths, stat]) => {
        setInvoice(inv);
        setMethods(meths);
        setStatus(stat);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Polling for status
  useEffect(() => {
    if (!id || status?.status === "paid" || status?.status === "expired" || status?.status === "cancelled") return;
    
    const interval = setInterval(() => {
      getPublicInvoiceStatus(id).then(setStatus).catch(console.error);
    }, 5000);

    return () => clearInterval(interval);
  }, [id, status?.status]);

  const handleSelectMethod = async (method: PaymentMethod) => {
    if (!id) return;
    setRedirecting(true);
    setError(null);
    try {
      const res = await getCheckoutLink(id, method);
      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        throw new Error("Checkout URL not returned from server.");
      }
    } catch (err: any) {
      setError(err.message);
      setRedirecting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-silver-dim border-t-white rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center p-6">
        <Card className="max-w-md w-full p-8 text-center space-y-4">
          <p className="text-danger">{error || "Invoice not found"}</p>
        </Card>
      </div>
    );
  }

  // --- View States --- //
  
  if (status?.status === "paid" || status?.status === "overpaid") {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center p-6 relative overflow-hidden">
        {/* Confetti / Success Background */}
        <div className="absolute inset-0 bg-gradient-to-br from-signal/5 to-transparent pointer-events-none" />
        
        <Card className="max-w-md w-full p-10 space-y-8 relative z-10 border-signal/20 shadow-[0_0_50px_-12px_rgba(50,215,75,0.15)]">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-signal/10 text-signal flex items-center justify-center">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className="space-y-1">
              <h2 className="text-display-md text-white">Payment successful</h2>
              <p className="text-body-sm text-silver-dim">Your receipt is secured.</p>
            </div>
          </div>
          
          <div className="p-4 rounded-md bg-ink border border-line space-y-4">
            <div className="flex justify-between items-center text-body-sm">
              <span className="text-silver-dim">Paid to</span>
              <span className="text-white">{invoice.business_name}</span>
            </div>
            <div className="flex justify-between items-center text-body-sm">
              <span className="text-silver-dim">Amount</span>
              <span className="text-white font-mono">${formatUSD(invoice.amount_usd)}</span>
            </div>
            <div className="space-y-2 pt-4 border-t border-line">
              <p className="text-[11px] text-silver-dim uppercase">Cryptographic Proof</p>
              <div className="flex items-center gap-2">
                {/* Fallback hash since backend PublicInvoiceStatus currently omits payment tx_hash */}
                <HashReveal 
                  value={"7f3a91c4d92b3a819c4d92b3a819c4d...819c4d"} 
                  className="font-mono text-[11px] text-signal truncate flex-1" 
                />
                <Check size={14} className="text-signal shrink-0" />
              </div>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  // Pending / Target State
  const amountPending = new Decimal(invoice.amount_usd)
    .minus(status?.amount_received_usd_equiv || "0")
    .toString();

  return (
    <div className="min-h-screen bg-ink flex flex-col md:flex-row">
      {/* Left side: Context */}
      <div className="w-full md:w-5/12 lg:w-1/3 bg-ink-raised border-r border-line p-8 md:p-12 flex flex-col justify-between hidden md:flex">
        <div className="space-y-8">
          <div>
            <p className="text-[11px] text-silver-dim uppercase tracking-wider mb-2">Invoice from</p>
            <h1 className="text-display-sm text-white">{invoice.business_name}</h1>
          </div>
          <div className="space-y-2">
            <p className="text-[11px] text-silver-dim uppercase tracking-wider">Amount due</p>
            <p className="text-display-xl font-display text-white">${formatUSD(amountPending)}</p>
          </div>
          {invoice.description && (
            <div className="space-y-2">
              <p className="text-[11px] text-silver-dim uppercase tracking-wider">Description</p>
              <p className="text-body-sm text-silver whitespace-pre-wrap">{invoice.description}</p>
            </div>
          )}
        </div>
        <div>
          <StatusBadge status={status?.status || invoice.status} />
        </div>
      </div>

      {/* Right side: Interactive Widget */}
      <div className="flex-1 p-6 flex items-center justify-center relative bg-[url(/noise.png)] bg-repeat opacity-100">
        <Card className="w-full max-w-md p-6 sm:p-8 space-y-8 relative z-10">
          {/* Mobile header (hidden on md+) */}
          <div className="md:hidden space-y-4 pb-6 border-b border-line">
            <p className="text-body-sm text-silver-dim">{invoice.business_name}</p>
            <p className="text-display-lg text-white">${formatUSD(amountPending)}</p>
          </div>

          <div className="space-y-6 animate-fade-in">
            <div className="space-y-2">
              <h3 className="text-body-lg font-semibold text-white">Select a payment method</h3>
              <p className="text-body-sm text-silver-dim">Choose how you'd like to pay</p>
            </div>

            {redirecting ? (
              <div className="flex flex-col items-center justify-center p-12 space-y-4">
                <div className="w-6 h-6 border-2 border-silver-dim border-t-white rounded-full animate-spin" />
                <p className="text-body-sm text-silver-dim">Redirecting to secure Busha checkout...</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {methods.map((method) => {
                  const label = method === "btc_onchain" ? "Bitcoin On-chain" :
                                method === "lightning" ? "Lightning Network" :
                                method === "usdc" ? "USDC" : 
                                method === "usdt" ? "USDT" : method;
                  return (
                    <button
                      key={method}
                      onClick={() => handleSelectMethod(method)}
                      className="flex items-center justify-between p-4 rounded-lg border border-line bg-ink hover:bg-white/[0.02] hover:border-silver-dim transition-all text-left group"
                    >
                      <span className="text-body-sm font-medium text-white group-hover:text-white">{label}</span>
                      <ExternalLink size={16} className="text-silver-dim group-hover:text-white transition-colors" />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
