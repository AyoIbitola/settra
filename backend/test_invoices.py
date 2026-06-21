import httpx
import time
import subprocess
import uuid

print("Starting Uvicorn...")
proc = subprocess.Popen(["venv/bin/uvicorn", "app.main:app", "--port", "8000"])
time.sleep(5)  # wait for it to start

try:
    test_email = f"invoice_tester_{uuid.uuid4().hex[:6]}@example.com"
    with httpx.Client(base_url="http://localhost:8000", timeout=30.0) as client:
        # 1. Register logic
        print("--- Registering ---")
        res1 = client.post("/auth/register", json={
            "email": test_email,
            "password": "securepass123",
            "business_name": "Acme Inc"
        })
        token = res1.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Invoice
        print("--- Create Invoice ---")
        res2 = client.post("/invoices", headers=headers, json={
            "client_name": "John Doe",
            "client_email": "john.doe@example.com",
            "description": "Consulting work for June",
            "amount_usd": 1500.50
        })
        print(res2.status_code, res2.text)
        created_invoice = res2.json()
        invoice_id = created_invoice.get("id")

        # 3. List Invoices
        print("--- List Invoices ---")
        res3 = client.get("/invoices", headers=headers)
        print(res3.status_code, res3.text)

        # 4. Get specific invoice
        print(f"--- Get specific invoice {invoice_id} ---")
        res4 = client.get(f"/invoices/{invoice_id}", headers=headers)
        print(res4.status_code, res4.text)

        # 5. Get missing invoice
        random_uuid = str(uuid.uuid4())
        print(f"--- Get missing invoice {random_uuid} ---")
        res5 = client.get(f"/invoices/{random_uuid}", headers=headers)
        print(res5.status_code, res5.text)

finally:
    proc.terminate()
    proc.wait()
    print("Done")
