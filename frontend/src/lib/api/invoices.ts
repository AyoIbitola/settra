import { apiRequest } from "./client";
import type { Invoice, PaginatedResponse } from "./types";

export interface CreateInvoiceData {
  client_name: string;
  client_email: string;
  description?: string;
  amount_usd: string;
  due_date?: string;
}

export async function getInvoices(params: { status?: string; page?: number; page_size?: number } = {}): Promise<PaginatedResponse<Invoice>> {
  const query = new URLSearchParams();
  if (params.status) query.append("status", params.status);
  if (params.page) query.append("page", params.page.toString());
  if (params.page_size) query.append("page_size", params.page_size.toString());
  
  const queryString = query.toString();
  return apiRequest<PaginatedResponse<Invoice>>(`/invoices${queryString ? `?${queryString}` : ""}`);
}

export async function getInvoice(id: string): Promise<Invoice> {
  return apiRequest<Invoice>(`/invoices/${id}`);
}

export async function createInvoice(data: CreateInvoiceData): Promise<Invoice> {
  return apiRequest<Invoice>("/invoices", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function cancelInvoice(id: string): Promise<void> {
  return apiRequest<void>(`/invoices/${id}/cancel`, { method: "POST" });
}

export async function resendInvoice(id: string): Promise<void> {
  return apiRequest<void>(`/invoices/${id}/resend`, { method: "POST" });
}
