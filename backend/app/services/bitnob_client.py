"""Bitnob API client — the only place in the codebase that constructs HTTP
requests to Bitnob. All signing, base URLs, and retry behavior live here.

Auth scheme (confirmed from https://bitnob.dev/api-reference/):
  HMAC-SHA256 over "CLIENT_ID:TIMESTAMP:NONCE:PAYLOAD"
  Headers: X-Auth-Client, X-Auth-Timestamp, X-Auth-Nonce, X-Auth-Signature
"""

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BitnobAPIError, PaymentTargetGenerationError


class BitnobClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ):
        self.base_url = base_url or settings.BITNOB_BASE_URL
        self.client_id = client_id or settings.BITNOB_CLIENT_ID
        self.client_secret = client_secret or settings.BITNOB_CLIENT_SECRET
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15.0,
        )

    def _sign(self, timestamp: str, nonce: str, payload: str) -> str:
        """Compute HMAC-SHA256 signature over CLIENT_ID:TIMESTAMP:NONCE:PAYLOAD."""
        message = f"{self.client_id}:{timestamp}:{nonce}:{payload}"
        return hmac.new(
            self.client_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self, payload: str) -> dict[str, str]:
        """Build the four required authentication headers for every request."""
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex  # 32-char hex, cryptographically random
        signature = self._sign(timestamp, nonce, payload)
        return {
            "X-Auth-Client": self.client_id,
            "X-Auth-Timestamp": timestamp,
            "X-Auth-Nonce": nonce,
            "X-Auth-Signature": signature,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Send an authenticated request to Bitnob and return the parsed JSON."""
        # Serialize the body exactly as it will be sent on the wire (no extra whitespace)
        payload_str = json.dumps(json_body, separators=(",", ":")) if json_body else ""
        headers = self._headers(payload_str)

        try:
            response = await self._http.request(
                method,
                path,
                headers=headers,
                json=json_body,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise BitnobAPIError(
                f"Bitnob API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise BitnobAPIError("Bitnob API request timed out") from exc

    async def close(self) -> None:
        await self._http.aclose()

    # ──────────────────────────────────────────────
    # Confirmed endpoints (from bitnob.dev/api-reference)
    # ──────────────────────────────────────────────

    async def whoami(self) -> dict:
        """Validate credentials. Use for sandbox connectivity verification."""
        return await self._request("GET", "/api/whoami")

    async def get_balances(self) -> dict:
        """Retrieve all wallet balances (BTC, USDT, USDC, NGN)."""
        return await self._request("GET", "/api/balances")

    async def get_balance(self, currency: str) -> dict:
        """Get balance for a specific currency (BTC, USDT, USDC, NGN)."""
        return await self._request("GET", f"/api/balances/{currency}")

    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> dict:
        """Get live exchange rate between two currencies.
        
        e.g. get_exchange_rate('USD', 'BTC') → buy_rate, sell_rate, mid_rate
        """
        return await self._request(
            "GET",
            "/api/exchange-rates",
            params={"from": from_currency, "to": to_currency},
        )

    async def list_exchange_rates(self, base: str) -> dict:
        """List all exchange rates for a single base currency."""
        return await self._request(
            "GET",
            "/api/exchange-rates",
            params={"base": base},
        )

    async def get_stablecoin_chains(self) -> dict:
        """List all supported blockchain networks with tokens and stablecoins.
        
        Call this early to discover which chains/tokens are available in the
        current environment (sandbox vs live) before building payment targets.
        """
        return await self._request("GET", "/api/stablecoins/supported-chains")

    async def generate_address(
        self,
        chain: str,
        customer_email: str,
        reference: str,
        label: str = "",
    ) -> dict:
        """Generate a new deposit address on the given chain.
        
        Supported chains: avalanche, base, bitcoin, ethereum, optimism, 
                          polygon, solana, stellar.
        """
        try:
            return await self._request(
                "POST",
                "/api/addresses",
                json_body={
                    "chain": chain,
                    "customerEmail": customer_email,
                    "reference": reference,
                    "label": label or reference,
                },
            )
        except BitnobAPIError as exc:
            raise PaymentTargetGenerationError(
                f"Failed to generate {chain} deposit address: {exc}"
            ) from exc

    async def generate_btc_address(self, customer_email: str, label: str = "") -> dict:
        """Generate an on-chain BTC address."""
        try:
            return await self._request(
                "POST",
                "/api/addresses/generate",
                json_body={
                    "customerEmail": customer_email,
                    "label": label,
                },
            )
        except BitnobAPIError as exc:
            raise PaymentTargetGenerationError(f"Failed to generate BTC address: {exc}") from exc

    async def create_lightning_invoice(
        self,
        satoshis: int,
        description: str,
        reference: str,
        expiry_seconds: int = 86400,
        customer_id: str | None = None,
    ) -> dict:
        """Create a Lightning BOLT11 invoice to receive payment.
        
        Returns: id, payment_hash, payment_request (BOLT11 string), status, expires_at
        """
        body: dict[str, Any] = {
            "satoshis": satoshis,
            "description": description,
            "reference": reference,
            "expirySeconds": expiry_seconds,
        }
        if customer_id:
            body["customerId"] = customer_id
        try:
            return await self._request("POST", "/api/lightning/invoices", json_body=body)
        except BitnobAPIError as exc:
            raise PaymentTargetGenerationError(
                f"Failed to create Lightning invoice: {exc}"
            ) from exc

    async def get_lightning_invoice(self, invoice_id: str) -> dict:
        """Check the status of a Lightning invoice (pending/paid/expired)."""
        return await self._request("GET", f"/api/lightning/invoices/{invoice_id}")

    async def list_transactions(self, reference: str) -> dict:
        """List all Bitnob transactions matching a given invoice reference.

        Used by the reconciliation_sweep fallback to detect payments that
        arrived but whose webhook was dropped before delivery.
        """
        return await self._request(
            "GET",
            "/api/transactions",
            params={"reference": reference},
        )
