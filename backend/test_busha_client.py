import asyncio
import json
from app.services.busha_client import BushaClient, BushaAPIError

async def test_links():
    print("Testing Busha Payment Links...")
    try:
        import uuid
        import json
        test_email = f"customer_{uuid.uuid4().hex[:8]}@gmail.com"
        async with BushaClient() as client:
            print("0. Get Currencies")
            curr_data = await client.get_currencies()
            print(json.dumps(curr_data, indent=2))
            
            print(f"\n1. Creating Payment Link for $150.00 (Target USDC) with email {test_email}...")
            link_data = await client.create_one_time_payment_link(
                name="Test Invoice INV_123",
                title="Invoice INV_123",
                description="Testing link creation",
                quote_amount="150.00",
                quote_currency="USD",
                target_currency="USDT",
                customer_email=test_email
            )
            print(f"Link Created! Status: 200 OK")
            print(json.dumps(link_data, indent=2))
            
            link_id = link_data.get("data", {}).get("id")
            if not link_id:
                print("No link ID returned!")
                return
                
            print(f"\n2. Creating Payment Request against Link {link_id}...")
            req_data = await client.create_payment_request_for_link(
                link_id=link_id,
                customer_email=test_email,
                source_currency="USDC",
                network="base"
            )
            print("Request Created! Status: 200 OK")
            print(json.dumps(req_data, indent=2))
            
    except BushaAPIError as e:
        print(f"\nFAILED! {e}")
        print(f"Response Data: {json.dumps(e.response_data, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_links())
