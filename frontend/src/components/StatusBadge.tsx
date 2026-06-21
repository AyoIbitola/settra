import * as React from "react";
import { cn } from "../lib/utils";

export type InvoiceStatus =
  | 'draft' | 'pending' | 'partially_paid' | 'paid'
  | 'overpaid' | 'expired' | 'cancelled' | 'refunded';

interface StatusBadgeProps {
  status: InvoiceStatus;
  className?: string;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  const config: Record<InvoiceStatus, { label: string; classes: string }> = {
    paid: {
      label: "Paid",
      classes: "bg-signal-dim/30 text-signal border-signal/20",
    },
    overpaid: {
      label: "Overpaid",
      classes: "bg-signal-dim/30 text-signal border-signal/20",
    },
    pending: {
      label: "Awaiting payment",
      classes: "bg-amber-dim/30 text-amber border-amber/20",
    },
    partially_paid: {
      label: "Partially paid",
      classes: "bg-amber-dim/30 text-amber border-amber/20",
    },
    draft: {
      label: "Draft",
      classes: "bg-silver-dim/10 text-silver-dim border-silver-dim/20",
    },
    cancelled: {
      label: "Cancelled",
      classes: "bg-silver-dim/10 text-silver-dim border-silver-dim/20",
    },
    expired: {
      label: "Expired",
      classes: "bg-silver-dim/10 text-silver-dim border-silver-dim/20",
    },
    refunded: {
      label: "Refunded",
      classes: "bg-silver-dim/10 text-silver-dim border-silver-dim/20",
    },
  };

  const { label, classes } = config[status];

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center px-2.5 py-1 rounded-sm text-[11px] font-medium uppercase tracking-wider border leading-none whitespace-nowrap",
        classes,
        className
      )}
    >
      {label}
    </span>
  );
};

export default StatusBadge;
export { StatusBadge };
