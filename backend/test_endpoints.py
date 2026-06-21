import httpx
import time
import subprocess
import os

print("Starting Uvicorn...")
proc = subprocess.Popen(["venv/bin/uvicorn", "app.main:app", "--port", "8000"])
time.sleep(5)  # wait for it to start

try:
    import uuid
    test_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    with httpx.Client(base_url="http://localhost:8000", timeout=30.0) as client:
        print("--- 1. Register a user ---")
        res1 = client.post("/auth/register", json={
            "email": test_email,
            "password": "securepass123",
            "business_name": "Acme Inc"
        })
        print(res1.status_code, res1.text)
        token = res1.json().get("access_token", "invalid")

        print("--- 2. Reject duplicate registration ---")
        res2 = client.post("/auth/register", json={
            "email": test_email,
            "password": "securepass123",
            "business_name": "Acme Inc"
        })
        print(res2.status_code, res2.text)

        print("--- 3. Login ---")
        res3 = client.post("/auth/login", json={
            "email": test_email,
            "password": "securepass123"
        })
        print(res3.status_code, res3.text)

        print("--- 4. Login with wrong password ---")
        res4 = client.post("/auth/login", json={
            "email": test_email,
            "password": "wrongpass"
        })
        print(res4.status_code, res4.text)

        print("--- 5. Get current user ---")
        res5 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        print(res5.status_code, res5.text)

        print("--- 6. Access /auth/me without token ---")
        res6 = client.get("/auth/me")
        print(res6.status_code, res6.text)

finally:
    proc.terminate()
    proc.wait()
    print("Done")
