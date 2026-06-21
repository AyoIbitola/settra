import * as React from "react";
import { cn } from "../../lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "raised" | "outline";
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "raised", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-lg",
          variant === "raised" && [
            "bg-ink-raised border border-line",
            "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]", // subtle top edge highlight
          ],
          variant === "outline" && "border border-line bg-transparent",
          className
        )}
        {...props}
      />
    );
  }
);
Card.displayName = "Card";

export { Card };
