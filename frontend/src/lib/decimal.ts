import { Decimal } from "decimal.js";

// Set precision for crypto (8 for BTC, but USDT/USDC might be 6 or 18)
// For display math, default to 8 decimal places for crypto, 2 for USD
Decimal.set({ precision: 20, rounding: Decimal.ROUND_HALF_UP });

export function formatUSD(amount: string | number): string {
  return new Decimal(amount).toFixed(2);
}

export function formatCrypto(amount: string | number, decimals = 8): string {
  return new Decimal(amount).toFixed(decimals);
}

export function toDecimal(amount: string | number): Decimal {
  return new Decimal(amount);
}
