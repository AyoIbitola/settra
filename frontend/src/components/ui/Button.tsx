import * as React from "react";
import { cn } from "../../lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "secondary";
  size?: "sm" | "md" | "lg";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    const variants = {
      primary: "bg-ink-raised text-white border border-line hover:border-silver-dim transition-colors",
      secondary: "bg-white text-ink hover:opacity-90 transition-opacity", // For marketing CTA where white is primary
      ghost: "bg-transparent text-silver hover:text-white transition-colors",
      danger: "bg-transparent text-danger border border-danger/20 hover:bg-danger/10 transition-all",
    };

    const sizes = {
      sm: "px-3 py-1.5 text-body-sm rounded-sm",
      md: "px-5 py-2.5 text-body rounded-md",
      lg: "px-8 py-4 text-body-lg rounded-lg font-semibold",
    };

    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-signal/50 disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
