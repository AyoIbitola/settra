import httpx
from typing import Any

from app.config import settings, DEFAULT_NETWORKS


class BushaAPIError(Exception):
    def __init__(self, message: str, status_code: int, response_data: dict):
        super().__init__(f"Busha API error {status_code}: {message}")
        self.status_code = status_code
        self.response_data = response_data
        self.message = message


# Method → (source_currency, target_currency, network) mapping
METHOD_MAP: dict[str, tuple[str, str, str]] = {
    "usdc": ("USDC", "USDC", DEFAULT_NETWORKS.get("usdc", "MATIC")),
    "usdt": ("USDT", "USDT", DEFAULT_NETWORKS.get("usdt", "TRX")),
    "btc":  ("BTC",  "BTC",  DEFAULT_NETWORKS.get("btc_onchain", "BTC")),
}


class BushaClient:
    """Wrapper for the Busha Business API."""

    def __init__(self):
        self.base_url = settings.BUSHA_BASE_URL.rstrip('/')
        self.secret_key = settings.BUSHA_SECRET_KEY.strip('"').strip("'")
        self.public_key = settings.BUSHA_PUBLIC_KEY.strip('"').strip("'")

        # Secret-key headers (for admin endpoints like currencies)
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Public-key headers (for customer-facing Payment Requests)
        self.public_headers = {
            "X-BU-PUBLIC-KEY": self.public_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=15.0
        )

    async def get_currencies(self) -> dict[str, Any]:
        """Test endpoint to fetch supported currencies and verify authentication."""
        response = await self.client.get("/v1/currencies")
        await self._handle_response(response)
        return response.json()

    async def create_payment_request(
        self,
        method: str,
        quote_amount: str,
        customer_email: str,
        reference: str,
    ) -> dict[str, Any]:
        """
        Create a Payment Request per Busha docs.
        Uses the Public API Key and returns a crypto deposit address.
        """
        if method not in METHOD_MAP:
            raise BushaAPIError(f"Unsupported method: {method}", 400, {})

        source_currency, target_currency, network = METHOD_MAP[method]

        payload = {
            "quote_amount": str(quote_amount),
            "quote_currency": "USD",
            "source_currency": source_currency,
            "target_currency": target_currency,
            "pay_in": {
                "type": "address",
                "network": network,
            },
            "additional_info": {
                "email": customer_email,
            },
            "reference": reference,
        }

        # Use public-key headers for this request
        response = await self.client.post(
            "/v1/payments/requests",
            json=payload,
            headers=self.public_headers,
        )
        await self._handle_response(response)
        return response.json()

    async def get_payment_request(self, request_id: str) -> dict[str, Any]:
        """Retrieve a payment request by ID."""
        response = await self.client.get(f"/v1/payments/requests/{request_id}")
        await self._handle_response(response)
        return response.json()

    async def _handle_response(self, response: httpx.Response):
        """Raises BushaAPIError for non-2xx responses."""
        if not response.is_success:
            err_data = {}
            try:
                err_data = response.json()
            except Exception:
                err_data = {"raw": response.text}

            message = err_data.get("message", "Unknown error")
            if "error" in err_data and isinstance(err_data["error"], dict):
                message = err_data["error"].get("message", message)

            raise BushaAPIError(message, response.status_code, err_data)

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
