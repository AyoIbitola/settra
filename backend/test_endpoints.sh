#!/bin/bash
source venv/bin/activate
uvicorn app.main:app &
UVICORN_PID=$!
sleep 3

echo "--- 1. Register a user ---"
RES=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"securepass123","business_name":"Acme Inc"}')
echo $RES
TOKEN=$(echo $RES | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

echo "--- 2. Reject duplicate registration ---"
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"securepass123","business_name":"Acme Inc"}'
echo ""

echo "--- 3. Login ---"
LOGIN_RES=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"securepass123"}')
echo $LOGIN_RES
TOKEN=$(echo $LOGIN_RES | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

echo "--- 4. Login with wrong password ---"
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test1@example.com","password":"wrongpass"}'
echo ""

echo "--- 5. Get current user ---"
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
echo ""

echo "--- 6. Access /auth/me without token ---"
curl -s http://localhost:8000/auth/me
echo ""

kill $UVICORN_PID
