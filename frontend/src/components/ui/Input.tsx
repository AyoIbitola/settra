import * as React from "react";
import { cn } from "../../lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  isMono?: boolean;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, isMono, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-12 w-full rounded-md border border-line bg-ink px-4 py-2 text-body text-white ring-offset-ink file:border-0 file:bg-transparent file:text-body-sm file:font-medium placeholder:text-silver-dim focus-visible:outline-none focus-visible:border-silver-dim disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
          isMono && "font-mono",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
