"""
Test script: Bitnob sandbox connectivity (Milestone 3).
Confirms HMAC-SHA256 auth works and identifies supported stablecoin chains.

Usage:
  source venv/bin/activate && python test_bitnob.py
"""
import asyncio
from app.services.bitnob_client import BitnobClient
from app.core.exceptions import BitnobAPIError


async def main():
    client = BitnobClient()

    print("=== 1. Verify credentials (/api/whoami) ===")
    try:
        res = await client.whoami()
        print("✅ Auth OK:", res)
    except BitnobAPIError as e:
        print("❌ Auth failed:", e)
        await client.close()
        return

    print("\n=== 2. Get wallet balances (/api/balances) ===")
    try:
        balances = await client.get_balances()
        print("✅ Balances:", balances)
    except BitnobAPIError as e:
        print("❌ Balances failed:", e)

    print("\n=== 3. BTC/USD exchange rate ===")
    try:
        rate = await client.get_exchange_rate("USD", "BTC")
        print("✅ Rate:", rate)
    except BitnobAPIError as e:
        print("❌ Rate failed:", e)

    print("\n=== 4. Supported stablecoin chains ===")
    try:
        chains = await client.get_stablecoin_chains()
        print("✅ Chains:", chains)
    except BitnobAPIError as e:
        print("❌ Chains failed:", e)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
