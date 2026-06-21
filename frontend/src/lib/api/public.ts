import { apiRequest } from "./client";
import type { PublicInvoice, PaymentMethod, PublicInvoiceStatus } from "./types";

export async function getPublicInvoice(id: string): Promise<PublicInvoice> {
  return apiRequest<PublicInvoice>(`/public/invoices/${id}`);
}

export async function getPaymentMethods(id: string): Promise<PaymentMethod[]> {
  return apiRequest<PaymentMethod[]>(`/public/invoices/${id}/payment-methods`);
}

export async function getCheckoutLink(id: string, method: PaymentMethod): Promise<{ checkout_url: string }> {
  return apiRequest<{ checkout_url: string }>(`/public/invoices/${id}/checkout-link?method=${method}`, {
    method: "POST",
  });
}

export async function getPublicInvoiceStatus(id: string): Promise<PublicInvoiceStatus> {
  return apiRequest<PublicInvoiceStatus>(`/public/invoices/${id}/status`);
}
