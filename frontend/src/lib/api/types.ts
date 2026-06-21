export type InvoiceStatus =
  | 'draft' | 'pending' | 'partially_paid' | 'paid'
  | 'overpaid' | 'expired' | 'cancelled' | 'refunded';

export type PaymentMethod = 'btc_onchain' | 'btc' | 'usdc' | 'usdt';

export interface Invoice {
  id: string;
  user_id: string;
  client_name: string;
  client_email: string;
  description: string | null;
  amount_usd: string;             // Decimal as string
  status: InvoiceStatus;
  bitnob_reference: string;
  amount_received_usd_equiv: string;
  overpaid_amount_usd: string;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PaymentTarget {
  target_value: string;            // Crypto deposit address
  amount_expected_crypto: string;  // Amount customer must send
  expires_at: string;              // ISO timestamp
  method: string;                  // e.g. "usdc", "usdt", "btc"
  network: string;                 // e.g. "MATIC", "TRX", "BTC"
  payment_request_id: string;      // Busha payment request ID
}

export interface PublicInvoice {
  client_name: string;
  business_name: string | null;
  description: string | null;
  amount_usd: string;
  status: InvoiceStatus;
  due_date: string | null;
}

export interface PublicInvoiceStatus {
  status: InvoiceStatus;
  amount_received_usd_equiv: string;
  remaining_usd: string | null;     // present only if partially_paid
  overpaid_amount_usd: string;
  active_target_expires_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  business_name: string | null;
  created_at: string;
  updated_at: string;
}
