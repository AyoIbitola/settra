import httpx
import time
import subprocess
import uuid

print("Starting Uvicorn...")
proc = subprocess.Popen(["venv/bin/uvicorn", "app.main:app", "--port", "8000"])
time.sleep(5)  # wait for it to start

try:
    test_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    with httpx.Client(base_url="http://localhost:8000", timeout=30.0) as client:
        # Register to get JWT
        res1 = client.post("/auth/register", json={
            "email": test_email,
            "password": "securepass123",
            "business_name": "Test Org"
        })
        token = res1.json().get("access_token", "invalid")
        headers = {"Authorization": f"Bearer {token}"}

        print("--- 1. Create Draft Invoice ---")
        invoice_req = {
            "client_name": "Test Client",
            "client_email": "client@example.com",
            "description": "Consulting services",
            "amount_usd": 1500.00
        }
        res2 = client.post("/invoices", json=invoice_req, headers=headers)
        print(res2.status_code)
        invoice_data = res2.json()
        print(invoice_data)
        
        # Verify schema
        assert invoice_data["status"] == "draft"
        assert "busha_reference" in invoice_data
        assert "bitnob_reference" not in invoice_data
        
        invoice_id = invoice_data["id"]

        print("--- 2. List Invoices ---")
        res3 = client.get("/invoices", headers=headers)
        print(res3.status_code)
        list_data = res3.json()
        print(f"Total invoices: {list_data['total']}")
        assert len(list_data["items"]) >= 1

        print("--- 3. Get Single Invoice ---")
        res4 = client.get(f"/invoices/{invoice_id}", headers=headers)
        print(res4.status_code)
        single_data = res4.json()
        assert single_data["id"] == invoice_id
        assert single_data["busha_reference"] == invoice_data["busha_reference"]
        
        print("ALL TESTS PASSED!")

finally:
    proc.terminate()
    proc.wait()
    print("Done")
