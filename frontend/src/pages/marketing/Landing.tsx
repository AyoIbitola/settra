import { Link } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { HeroInvoiceDemo } from "../../components/HeroInvoiceDemo";
import { Card } from "../../components/ui/Card";

export default function Landing() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Section 1: Hero */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          <div className="space-y-8 text-center lg:text-left">
            <h1 className="text-display-xl leading-tight">
              Invoice in dollars.<br />
              Get paid in crypto.
            </h1>
            <p className="text-body-lg text-silver max-w-xl">
              Lock a USD rate the moment your client opens the link. They pay with Bitcoin, Lightning, or a stablecoin — you get a cryptographic receipt either way.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
              <Link to="/login">
                <Button size="lg" variant="primary" className="bg-white text-ink hover:bg-silver transition-colors">
                  Get started
                </Button>
              </Link>
            </div>
          </div>
          
          <div className="relative">
            <HeroInvoiceDemo />
          </div>
        </div>
      </section>

      {/* Section 2: How it works */}
      <section id="how-it-works" className="py-32 px-6 border-t border-line">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            <div className="space-y-4">
              <span className="text-display-md text-silver-dim font-mono">01</span>
              <h3 className="text-display-md text-white underline underline-offset-8 decoration-line">Create</h3>
              <p className="text-body text-silver">
                Set an amount in USD. We lock today's rate the moment your client opens the link.
              </p>
            </div>
            <div className="space-y-4">
              <span className="text-display-md text-silver-dim font-mono">02</span>
              <h3 className="text-display-md text-white underline underline-offset-8 decoration-line">Pay</h3>
              <p className="text-body text-silver">
                Client pays with Bitcoin, Lightning, or a stablecoin. No wallet lecture required.
              </p>
            </div>
            <div className="space-y-4">
              <span className="text-display-md text-silver-dim font-mono">03</span>
              <h3 className="text-display-md text-white underline underline-offset-8 decoration-line">Prove</h3>
              <p className="text-body text-silver">
                A receipt with the transaction hash lands in both inboxes automatically.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: The receipt */}
      <section className="py-32 px-6 bg-ink-raised border-y border-line">
        <div className="max-w-3xl mx-auto text-center space-y-8">
          <h2 className="text-display-lg text-white">Proof that doesn't ask to be trusted.</h2>
          <p className="text-body-lg text-silver">
            Every receipt carries the on-chain transaction hash — verifiable by anyone, on any block explorer.
          </p>
          <Card className="p-12 text-left bg-ink border border-line shadow-2xl relative overflow-hidden group">
             {/* Simple receipt visual */}
             <div className="space-y-8 opacity-80 group-hover:opacity-100 transition-opacity">
                <div className="flex justify-between items-center border-b border-line pb-6">
                  <span className="text-display-md text-white font-bold tracking-tighter italic">SETTRA</span>
                  <div className="text-right">
                    <p className="text-[10px] text-silver-dim uppercase">Receipt #</p>
                    <p className="text-mono-sm text-white">REC-0492-710</p>
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-body-sm text-silver-dim">Paid by Design Studio Inc. on June 20, 2026</p>
                  <p className="text-display-lg text-white">$500.00 USD</p>
                </div>
                <div className="space-y-2 pt-6 border-t border-line">
                  <p className="text-[10px] text-silver-dim uppercase font-mono">Transaction Hash</p>
                  <p className="text-mono-md text-signal break-all">7f3a91c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d</p>
                </div>
             </div>
             <div className="absolute top-0 right-0 w-32 h-32 bg-signal/5 blur-3xl rounded-full" />
          </Card>
        </div>
      </section>

      {/* Section 4: Payment Methods */}
      <section className="py-32 px-6">
        <div className="max-w-7xl mx-auto">
           <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card className="p-8 space-y-4 hover:border-silver-dim transition-colors cursor-default">
                <div className="w-12 h-12 bg-white/5 rounded-md flex items-center justify-center text-white font-bold font-mono">B</div>
                <h4 className="text-body-lg font-semibold text-white">BTC On-chain</h4>
                <p className="text-body-sm text-silver">Best for: larger amounts. High security, 10-60 min confirmation.</p>
              </Card>
              <Card className="p-8 space-y-4 hover:border-silver-dim transition-colors cursor-default">
                <div className="w-12 h-12 bg-white/5 rounded-md flex items-center justify-center text-white font-bold font-mono">L</div>
                <h4 className="text-body-lg font-semibold text-white">Lightning</h4>
                <p className="text-body-sm text-silver">Best for: instant, small payments. Sub-second and near-zero fee.</p>
              </Card>
              <Card className="p-8 space-y-4 hover:border-silver-dim transition-colors cursor-default">
                <div className="w-12 h-12 bg-white/5 rounded-md flex items-center justify-center text-white font-bold font-mono">S</div>
                <h4 className="text-body-lg font-semibold text-white">USDC / USDT</h4>
                <p className="text-body-sm text-silver">Best for: zero volatility. Stable value, widely supported.</p>
              </Card>
           </div>
        </div>
      </section>

      {/* Section 5: Final CTA */}
      <section className="py-32 px-6 border-t border-line text-center bg-ink">
        <div className="max-w-xl mx-auto space-y-8">
          <h2 className="text-display-lg text-white">Get paid the way you actually want to</h2>
          <Link to="/login">
            <Button size="lg" variant="primary" className="bg-white text-ink hover:bg-silver transition-colors">
              Get started for free
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
