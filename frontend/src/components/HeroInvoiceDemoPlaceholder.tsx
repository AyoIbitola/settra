import { Card } from "./ui/Card";
import { StatusBadge } from "./StatusBadge";

export function HeroInvoiceDemoPlaceholder() {
  return (
    <Card className="max-w-md mx-auto p-8 space-y-8 animate-in fade-in zoom-in duration-700">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <p className="text-display-md text-white">$500.00</p>
          <p className="text-mono-sm text-silver-dim uppercase tracking-wider">Invoice INV-0492</p>
        </div>
        <StatusBadge status="paid" />
      </div>

      <div className="space-y-4">
        <div className="flex justify-between text-body-sm pb-4 border-b border-line">
          <span className="text-silver-dim">Client</span>
          <span className="text-white">Design Studio Inc.</span>
        </div>
        <div className="flex justify-between text-body-sm pb-4 border-b border-line">
          <span className="text-silver-dim">Payment Method</span>
          <span className="text-white font-mono">Bitcoin (Lightning)</span>
        </div>
      </div>

      <div className="space-y-2 pt-4 bg-ink/50 p-4 rounded-md border border-line/50">
        <div className="flex items-center gap-2 text-signal">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-body-sm font-semibold uppercase tracking-tight">Payment Confirmed</span>
        </div>
        <div className="space-y-1 overflow-hidden">
          <p className="text-[10px] text-silver-dim font-mono uppercase">Proof of Payment (TX Hash)</p>
          <p className="text-mono-sm text-white break-all">7f3a91c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d</p>
        </div>
      </div>
      
      <div className="absolute -z-10 inset-0 blur-3xl opacity-20 bg-signal rounded-full scale-150 transform translate-y-1/2" />
    </Card>
  );
}
