import { useEffect, useState } from "react";
import { cn } from "../lib/utils";

interface CountdownRingProps {
  expiresAt?: string; // If null, it's a fixed demo ring
  duration?: number; // In seconds, for fixed demo
  onExpire?: () => void;
  className?: string;
  size?: number;
}

export function CountdownRing({
  expiresAt,
  onExpire,
  className,
  size = 16,
}: CountdownRingProps) {
  const [progress, setProgress] = useState(1);

  useEffect(() => {
    if (!expiresAt) return;

    const start = Date.now();
    const end = new Date(expiresAt).getTime();
    const total = end - start;

    if (total <= 0) {
      setProgress(0);
      onExpire?.();
      return;
    }

    const timer = setInterval(() => {
      const now = Date.now();
      const remaining = end - now;
      const nextProgress = Math.max(remaining / total, 0);
      
      setProgress(nextProgress);
      
      if (nextProgress <= 0) {
        clearInterval(timer);
        onExpire?.();
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [expiresAt, onExpire]);

  // If used for the demo (no expiresAt), parent will likely control progress or it just shows a static state
  // Beat 2 spec says "animates around a small clock glyph, depleting over the beat's duration"
  
  const radius = size / 2 - 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - progress);

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth="1.5"
          fill="transparent"
          className="text-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth="1.5"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="text-amber transition-all duration-1000 ease-linear"
        />
      </svg>
    </div>
  );
}
