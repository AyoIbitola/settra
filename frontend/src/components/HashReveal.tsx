import { useState, useEffect, useRef } from "react";
import { cn } from "../lib/utils";

interface HashRevealProps {
  value: string;
  trigger?: "mount" | "inView" | "manual";
  size?: "sm" | "md" | "lg";
  className?: string;
  onComplete?: () => void;
}

const CHARS = "0123456789abcdef";

export function HashReveal({
  value,
  trigger = "mount",
  size = "md",
  className,
  onComplete,
}: HashRevealProps) {
  const [displayText, setDisplayText] = useState(
    value.split("").map(() => CHARS[Math.floor(Math.random() * CHARS.length)]).join("")
  );
  const [isResolved, setIsResolved] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  const resolve = () => {
    if (hasAnimated.current) return;
    hasAnimated.current = true;

    const iterations = 10;
    const duration = 600;
    const startTime = Date.now();

    const animate = () => {
      const now = Date.now();
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);

      const nextText = value.split("").map((char, i) => {
        // Stagger the resolution from left to right
        const staggerThreshold = (i / value.length) * 0.8; 
        if (progress > staggerThreshold) {
            return char;
        }
        return CHARS[Math.floor(Math.random() * CHARS.length)];
      }).join("");

      setDisplayText(nextText);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setIsResolved(true);
        onComplete?.();
      }
    };

    requestAnimationFrame(animate);
  };

  useEffect(() => {
    if (trigger === "mount") {
      resolve();
    } else if (trigger === "inView") {
      const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            resolve();
            observer.disconnect();
        }
      });
      if (containerRef.current) observer.observe(containerRef.current);
      return () => observer.disconnect();
    }
  }, [trigger]);

  // Handle manual trigger if exposed via ref or prop change
  useEffect(() => {
    if (trigger === "manual" && !hasAnimated.current && value) {
        // Could be triggered by parent
    }
  }, [trigger, value]);

  const sizes = {
    sm: "text-mono-sm",
    md: "text-mono",
    lg: "text-mono-lg",
  };

  return (
    <span
      ref={containerRef}
      className={cn(
        "font-mono tabular-nums break-all transition-colors duration-300",
        sizes[size],
        isResolved ? "text-white" : "text-silver-dim",
        className
      )}
    >
      {displayText}
    </span>
  );
}
