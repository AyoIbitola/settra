import { mockInvoices, mockUser } from "./fixtures";

// Simple state to track polling simulation for Milestone 6
let pollCount = 0;
const POLLING_THRESHOLD = 3;

export async function mockRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  // Simulate network delay
  const delay = Math.floor(Math.random() * 250) + 150;
  await new Promise((resolve) => setTimeout(resolve, delay));

  const method = options.method || "GET";

  // Auth routes
  if (path === "/auth/login") {
    return { token: "fake-jwt-token", user: mockUser } as T;
  }
  if (path === "/auth/register") {
    return { token: "fake-jwt-token", user: mockUser } as T;
  }
  if (path === "/auth/me") {
    return mockUser as T;
  }

  // Invoice routes
  if (path.split("?")[0] === "/invoices" && method === "GET") {
    return {
      items: mockInvoices,
      total: mockInvoices.length,
      page: 1,
      page_size: 10,
    } as T;
  }

  if (path.startsWith("/invoices/") && method === "GET") {
    const id = path.split("/")[2];
    const invoice = mockInvoices.find((i) => i.id === id) || mockInvoices[0];
    return invoice as T;
  }

  // Public payment page routes
  if (path.startsWith("/public/invoices/") && path.endsWith("/status")) {
    const isMockSuccessSimulation = path.includes("inv-002"); // Use inv-002 for polling demo
    
    if (isMockSuccessSimulation) {
      pollCount++;
      if (pollCount >= POLLING_THRESHOLD) {
        return {
          status: "paid",
          amount_received_usd_equiv: "1200.00",
          remaining_usd: "0",
          overpaid_amount_usd: "0",
          active_target_expires_at: null,
          payment: {
            tx_hash: "7f3a91c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d92b3a819c4d",
            method: "btc_onchain",
            confirmations: 2
          }
        } as T;
      }
    }
    
    return {
      status: "pending",
      amount_received_usd_equiv: "0.00",
      overpaid_amount_usd: "0.00",
      active_target_expires_at: new Date(Date.now() + 15 * 60000).toISOString(),
    } as T;
  }

  if (path.startsWith("/public/invoices/") && !path.includes("/status")) {
    const id = path.split("/")[3];
    const invoice = mockInvoices.find((i) => i.id === id) || mockInvoices[1];
    return {
      client_name: invoice.client_name,
      business_name: "Settra Labs",
      description: invoice.description,
      amount_usd: invoice.amount_usd,
      status: invoice.status,
      due_date: invoice.due_date,
    } as T;
  }

  if (path.includes("/payment-methods")) {
    return ["btc_onchain", "lightning", "usdc", "usdt"] as T;
  }

  if (path.includes("/payment-target")) {
    pollCount = 0; // Reset poll count when a new target is requested
    return {
      target_value: "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
      amount_expected_crypto: "0.00071",
      rate_locked_usd_to_crypto: "65000.00",
      expires_at: new Date(Date.now() + 15 * 60000).toISOString(),
      method: "btc_onchain",
      network: "bitcoin",
    } as T;
  }

  throw new Error(`Mock not implemented for ${method} ${path}`);
}
