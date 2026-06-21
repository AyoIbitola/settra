# Bitcoin & Stablecoin Invoicing Platform — Backend

A FastAPI backend that lets freelancers send USD-denominated invoices paid via Bitcoin (on-chain), Lightning, USDC, or USDT — routed through the [Busha API](https://developers.busha.co/).

---

## Tech Stack

- **FastAPI** — async Python web framework
- **PostgreSQL** — primary database (via asyncpg + SQLAlchemy 2.0)
- **Redis** — Celery broker + result backend + rate-limit store
- **Celery** — async task queue (webhook processing, receipt generation, email)
- **Celery Beat** — periodic job scheduler (reconciliation sweep + target expiry)
- **Busha** — Bitcoin / Lightning / Stablecoin payment rails
- **WeasyPrint** — PDF receipt generation

---

## Project Structure

```
backend/
├── app/
│   ├── config.py               # Pydantic Settings — all env vars
│   ├── db.py                   # Async SQLAlchemy engine + session factory
│   ├── main.py                 # FastAPI app factory + rate limiting
│   ├── models/                 # SQLAlchemy ORM models
│   ├── routers/                # FastAPI route handlers
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic (InvoiceService, BitnobClient, etc.)
│   ├── workers/                # Celery app + tasks
│   └── templates/              # Jinja2 HTML templates (PDF receipts)
├── alembic/                    # Database migrations
├── tests/                      # Pytest test suite
├── .env.example                # Template — copy to .env and fill in values
└── pyproject.toml
```

---

## Local Development Setup

### 1. Prerequisites

- Python 3.11+
- PostgreSQL running locally
- Redis running locally
- `ngrok` (required for webhook testing — see step 6)

### 2. Clone and install

```bash
git clone <repo-url>
cd invoice-platform/backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your real values
```

Key values to fill in:
| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Your local Postgres connection string |
| `REDIS_URL` | Your local Redis URL |
| `BUSHA_SECRET_KEY` | Busha Business dashboard → Developer Tools |
| `BUSHA_WEBHOOK_SECRET` | Busha Business dashboard → Webhooks |
| `JWT_SECRET` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the four processes

Open four terminal tabs:

```bash
# Tab 1 — FastAPI server
uvicorn app.main:app --reload

# Tab 2 — Celery worker (processes webhooks, receipts, emails)
celery -A app.workers.celery_app worker --loglevel=info

# Tab 3 — Celery Beat (expiry + reconciliation sweep scheduler)
celery -A app.workers.celery_app beat --loglevel=info

# Tab 4 — ngrok (required for Bitnob to reach your local webhook)
ngrok http 8000
```

### 6. Configure webhooks (required)

Busha requires a **publicly reachable** URL to deliver webhook events. Without this, the reconciliation flow cannot function locally.

1. Run `ngrok http 8000` — you'll get a URL like `https://abc123.ngrok.io`
2. Go to your Busha Business dashboard → **Webhooks**
3. Set the webhook URL to: `https://abc123.ngrok.io/webhooks/busha`
4. Copy the webhook secret and set `BUSHA_WEBHOOK_SECRET` in your `.env`

> ⚠️ The ngrok URL changes every time you restart it. Update the Busha dashboard each time.

---

## API Reference

Once running, interactive docs are at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Authenticated Endpoints (require `Authorization: Bearer <JWT>`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create freelancer account |
| `POST` | `/auth/login` | Get JWT token |
| `GET` | `/auth/me` | Current user profile |
| `POST` | `/invoices` | Create invoice (draft) |
| `GET` | `/invoices` | List invoices (supports `?status=` filter) |
| `GET` | `/invoices/{id}` | Invoice detail |
| `POST` | `/invoices/{id}/cancel` | Cancel draft/pending invoice |
| `POST` | `/invoices/{id}/resend` | Re-send payment link to client |
| `GET` | `/invoices/{id}/receipt` | Download PDF receipt |
| `GET` | `/overpayment-credits` | List overpayment credits |
| `POST` | `/overpayment-credits/{id}/resolve` | Resolve a credit |

### Public Endpoints (no auth, rate-limited per IP)

| Method | Path | Rate Limit | Description |
|---|---|---|---|
| `GET` | `/public/invoices/{id}` | 60/min | Invoice display info |
| `GET` | `/public/invoices/{id}/payment-methods` | 30/min | Supported payment methods |
| `POST` | `/public/invoices/{id}/checkout-link?method=` | 10/min | Generate Busha checkout URL |
| `GET` | `/public/invoices/{id}/status` | 120/min | Payment status (polling) |
| `GET` | `/public/invoices/{id}/receipt` | 20/min | Download receipt |

### Webhook

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhooks/busha` | Busha event receiver (HMAC-SHA256 verified) |

---

## Running Tests

```bash
pytest
# or with coverage
pytest --cov=app tests/
```

---

## Production Deployment

Quick summary — Railway/Render/Fly.io:

| Service | Start Command |
|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Worker | `celery -A app.workers.celery_app worker --loglevel=info` |
| Beat | `celery -A app.workers.celery_app beat --loglevel=info` |

> ⚠️ Run **exactly one** Beat process — scaling it to 2+ replicas causes duplicate task firing.

### Sandbox → Production cutover

Change the following environment variables:
```
BUSHA_BASE_URL=https://api.busha.co
BUSHA_SECRET_KEY=<your-live-secret>
```

No code changes required.

---

## Health Check

`GET /health` returns DB and Redis connectivity status:

```json
{ "status": "ok", "db": "ok", "redis": "ok" }
```
