import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { Card } from "./ui/Card";
import { CountdownRing } from "./CountdownRing";
import { HashReveal } from "./HashReveal";
import { cn } from "../lib/utils";

export function HeroInvoiceDemo() {
  const cardRef = useRef<HTMLDivElement>(null);
  const statusPillRef = useRef<HTMLDivElement>(null);
  const amountRef = useRef<HTMLDivElement>(null);
  const qrRef = useRef<HTMLDivElement>(null);
  const hashContainerRef = useRef<HTMLDivElement>(null);
  const checkmarkPathRef = useRef<SVGPathElement>(null);
  
  // Internal state to switch content types that aren't easily handled by pure GSAP CSS transforms
  const [beat, setBeat] = useState<1 | 2 | 3>(1);
  const [triggerHash, setTriggerHash] = useState(0);

  useEffect(() => {
    if (!cardRef.current) return;

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ repeat: -1, repeatDelay: 1 });

      // Beat 1: Created (0.0s - 1.5s)
      tl.addLabel("beat1")
        .fromTo(cardRef.current, 
          { scale: 0.96, opacity: 0 },
          { scale: 1, opacity: 1, duration: 0.4, ease: "power2.out" }
        )
        .set({}, { onComplete: () => setBeat(1) }, 0);

      // Beat 2: Quoted (1.5s - 3.8s)
      tl.addLabel("beat2", 1.5)
        .to(statusPillRef.current, { opacity: 0, duration: 0.2 })
        .set({}, { onComplete: () => setBeat(2) })
        .to(statusPillRef.current, { opacity: 1, duration: 0.2 })
        .fromTo(qrRef.current, { opacity: 0, x: 20 }, { opacity: 1, x: 0, duration: 0.4 }, "-=0.2");

      // Beat 3: Paid (3.8s - 5.8s)
      tl.addLabel("beat3", 3.8)
        .to(statusPillRef.current, { opacity: 0, duration: 0.2 })
        .set({}, { onComplete: () => {
            setBeat(3);
            setTriggerHash(h => h + 1);
        } })
        .to(statusPillRef.current, { opacity: 1, duration: 0.2 })
        .to(hashContainerRef.current, { opacity: 1, y: 0, duration: 0.4 })
        .fromTo(checkmarkPathRef.current, 
            { strokeDashoffset: 20 }, 
            { strokeDashoffset: 0, duration: 0.35, ease: "power1.inOut" }, "-=0.2")
        .to(cardRef.current, { boxShadow: "0 0 30px rgba(124, 255, 155, 0.08)", duration: 0.5 }, "-=0.5");

      // Hold at end
      tl.to({}, { duration: 1 });
    }, cardRef);

    return () => ctx.revert();
  }, []);

  return (
    <Card ref={cardRef} className="max-w-md mx-auto p-8 space-y-8 relative overflow-hidden transition-all duration-500">
      <div className="flex justify-between items-start">
        <div ref={amountRef} className="space-y-1">
          <p className="text-display-md text-white">$500.00</p>
          <p className="text-mono-sm text-silver-dim uppercase tracking-wider">Invoice INV-0492</p>
        </div>
        
        <div ref={statusPillRef}>
          {beat === 1 && (
            <div className="bg-amber-dim/20 text-amber border border-amber/20 px-3 py-1 rounded-sm flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
              <span className="text-[10px] font-bold uppercase tracking-wider">Awaiting payment</span>
            </div>
          )}
          {beat === 2 && (
            <div className="bg-amber-dim/20 text-amber border border-amber/20 px-3 py-1 rounded-sm flex items-center gap-2">
              <CountdownRing duration={2.3} size={14} className="text-amber" />
              <span className="text-mono-sm font-bold">0.00071 BTC</span>
            </div>
          )}
          {beat === 3 && (
            <div className="bg-signal-dim/20 text-signal border border-signal/20 px-3 py-1 rounded-sm flex items-center gap-2">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-signal">
                <path 
                    ref={checkmarkPathRef}
                    d="M5 13l4 4L19 7" 
                    stroke="currentColor" 
                    strokeWidth="3" 
                    strokeLinecap="round" 
                    strokeLinejoin="round"
                    strokeDasharray="20"
                />
              </svg>
              <span className="text-[10px] font-bold uppercase tracking-wider font-display">Paid</span>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex justify-between text-body-sm pb-4 border-b border-line">
          <span className="text-silver-dim">Client</span>
          <span className="text-white">Design Studio Inc.</span>
        </div>
        {beat >= 2 && (
            <div className="flex justify-between text-body-sm pb-4 border-b border-line animate-in fade-in slide-in-from-left-2 transition-all">
                <span className="text-silver-dim">Network</span>
                <span className="text-white font-mono">{beat === 3 ? "Bitcoin Mainnet" : "Lightning Network"}</span>
            </div>
        )}
      </div>

      <div className="flex gap-6 items-center">
        {beat === 2 && (
          <div ref={qrRef} className="relative group">
            <div className="w-24 h-24 bg-white p-1 rounded-md">
                {/* Fake QR pattern */}
                <div className="w-full h-full bg-ink grid grid-cols-4 gap-0.5">
                    {Array.from({length: 16}).map((_, i) => (
                        <div key={i} className={cn("w-full h-full bg-white", Math.random() > 0.5 ? "opacity-100" : "opacity-0")} />
                    ))}
                </div>
            </div>
            {/* Specular highlight sweep */}
            <div className="absolute inset-0 overflow-hidden rounded-md pointer-events-none">
                <div className="absolute -inset-[100%] bg-gradient-to-tr from-transparent via-white/40 to-transparent transform -skew-x-12 translate-x-[-150%] animate-[sweep_2s_ease-in-out_infinite]" />
            </div>
          </div>
        )}

        {beat === 3 && (
          <div ref={hashContainerRef} className="space-y-2 flex-grow">
            <p className="text-[10px] text-silver-dim font-mono uppercase">On-chain transaction hash</p>
            <HashReveal 
                key={triggerHash}
                value="7f3a91c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d" 
                size="sm"
            />
          </div>
        )}
      </div>

      {/* Decorative glow for Beat 3 */}
      {beat === 3 && (
        <div className="absolute -z-10 inset-0 blur-3xl opacity-10 bg-signal rounded-full scale-150 transform translate-y-1/2 transition-opacity duration-1000" />
      )}
    </Card>
  );
}
