import { apiRequest } from "./client";
import type { PublicInvoice, PaymentMethod, PaymentTarget, PublicInvoiceStatus } from "./types";

export async function getPublicInvoice(id: string): Promise<PublicInvoice> {
  return apiRequest<PublicInvoice>(`/public/invoices/${id}`);
}

export async function getPaymentMethods(id: string): Promise<PaymentMethod[]> {
  return apiRequest<PaymentMethod[]>(`/public/invoices/${id}/payment-methods`);
}

export async function createPaymentTarget(id: string, method: PaymentMethod): Promise<PaymentTarget> {
  return apiRequest<PaymentTarget>(`/public/invoices/${id}/payment-target?method=${method}`, {
    method: "POST",
  });
}

export async function getPublicInvoiceStatus(id: string): Promise<PublicInvoiceStatus> {
  return apiRequest<PublicInvoiceStatus>(`/public/invoices/${id}/status`);
}
