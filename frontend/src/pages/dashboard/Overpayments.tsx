import { useEffect, useState } from "react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { apiRequest } from "../../lib/api/client";
import { formatUSD } from "../../lib/decimal";

interface OverpaymentCredit {
  id: string;
  invoice_id: string;
  amount_usd: string;
  status: string;
  created_at: string;
}

export default function Overpayments() {
  const [credits, setCredits] = useState<OverpaymentCredit[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiRequest<OverpaymentCredit[]>("/overpayment-credits")
      .then(setCredits)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const resolveCredit = async (id: string, action: "acknowledged_keep" | "refunded") => {
    try {
      await apiRequest(`/overpayment-credits/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      setCredits((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      console.error("Failed to resolve credit:", err);
    }
  };

  const daysSince = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-ink-raised rounded" />
        {[1, 2].map((i) => <div key={i} className="h-20 bg-ink-raised rounded-lg border border-line" />)}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-display-md">Overpayments</h1>

      {credits.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-silver-dim text-body-sm">No unresolved overpayments.</p>
        </Card>
      ) : (
        <Card className="divide-y divide-line">
          {credits.map((credit) => {
            const age = daysSince(credit.created_at);
            const isOld = age > 7;
            return (
              <div key={credit.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-body-sm text-white font-medium">
                    Invoice: <span className="font-mono text-silver">{credit.invoice_id.slice(0, 8)}…</span>
                  </p>
                  <div className="flex items-center gap-4 text-body-sm">
                    <span className="text-white font-mono">${formatUSD(credit.amount_usd)}</span>
                    <span className={isOld ? "text-danger" : "text-silver-dim"}>
                      {age}d ago {isOld && "⚠"}
                    </span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => resolveCredit(credit.id, "acknowledged_keep")}>
                    Mark as kept
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => resolveCredit(credit.id, "refunded")}>
                    Mark as refunded
                  </Button>
                </div>
              </div>
            );
          })}
        </Card>
      )}
    </div>
  );
}
