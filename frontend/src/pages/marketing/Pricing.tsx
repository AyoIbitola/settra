export default function Pricing() {
  return (
    <main className="flex-grow pt-32 pb-20 px-6 max-w-7xl mx-auto w-full text-center space-y-12">
        <h1 className="text-display-lg text-white">Simple, transparent pricing.</h1>
        <p className="text-body-lg text-silver max-w-2xl mx-auto">
          Settra is currently in early access. We charge a flat fee of 0.5% per processed invoice. No monthly subscriptions, no hidden gas fees for you.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto text-left">
           <div className="p-8 border border-line rounded-lg bg-ink-raised space-y-4">
              <h3 className="text-display-md text-white">Free</h3>
              <p className="text-body-sm text-silver">For individual freelancers testing the waters.</p>
              <div className="text-display-md text-white">$0<span className="text-body text-silver-dim">/mo</span></div>
              <ul className="space-y-2 text-body-sm text-silver">
                <li>• Up to 3 invoices / month</li>
                <li>• All payment methods</li>
                <li>• 1% processing fee</li>
              </ul>
           </div>
           <div className="p-8 border border-signal/20 rounded-lg bg-ink-raised space-y-4 relative overflow-hidden">
              <div className="absolute top-4 right-4 bg-signal/10 text-signal text-[10px] uppercase px-2 py-1 rounded-sm border border-signal/20">Popular</div>
              <h3 className="text-display-md text-white">Pro</h3>
              <p className="text-body-sm text-silver">For full-time digital nomads and businesses.</p>
              <div className="text-display-md text-white">$19<span className="text-body text-silver-dim">/mo</span></div>
              <ul className="space-y-2 text-body-sm text-silver">
                <li>• Unlimited invoices</li>
                <li>• Custom branding</li>
                <li>• 0.5% processing fee</li>
              </ul>
           </div>
        </div>
      </main>
  );
}
