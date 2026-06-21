import httpx
from typing import Any

from app.config import settings

class BushaAPIError(Exception):
    def __init__(self, message: str, status_code: int, response_data: dict):
        super().__init__(f"Busha API error {status_code}: {message}")
        self.status_code = status_code
        self.response_data = response_data
        self.message = message


class BushaClient:
    """Wrapper for the Busha Business API."""

    def __init__(self):
        self.base_url = settings.BUSHA_BASE_URL.rstrip('/')
        self.secret_key = settings.BUSHA_SECRET_KEY
        
        # Remove any surrounding quotes that might have been copied from .env
        self.secret_key = self.secret_key.strip('"').strip("'")
        
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
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

    async def create_one_time_payment_link(
        self,
        name: str,
        title: str,
        description: str,
        quote_amount: str,
        quote_currency: str,
        target_currency: str,
        customer_email: str,
    ) -> dict[str, Any]:
        """Create a new one-time payment link per PRD 5.2."""
        payload = {
            "fixed": True,
            "one_time": True,
            "name": name,
            "title": title,
            "description": description or "",
            "quote_amount": quote_amount,
            "quote_currency": quote_currency,
            "target_currency": target_currency,
            "require_extra_info": [
                {"field_name": "email", "required": True}
            ],
        }
        response = await self.client.post("/v1/payments/links", json=payload)
        await self._handle_response(response)
        return response.json()

    async def create_payment_request_for_link(
        self,
        link_id: str,
        customer_email: str,
        source_currency: str,
        network: str,
    ) -> dict[str, Any]:
        """Create a payment request against an existing link per PRD 5.2."""
        payload = {
            "source_currency": source_currency,
            "network": network,
            "type": "crypto",
            "payment_method": "crypto",
            "requested_info": {
                "email": customer_email
            }
        }
        response = await self.client.post(f"/v1/payments/links/{link_id}/requests", json=payload)
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
