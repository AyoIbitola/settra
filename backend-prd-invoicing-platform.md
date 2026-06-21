# Backend PRD — Bitcoin & Stablecoin Invoicing Platform

**Version:** 1.0
**Owner:** [Your name]
**Backend stack:** Python, FastAPI, PostgreSQL, Redis, Celery
**Payment rail:** Bitnob API (sandbox → production)
**Audience:** Engineering agent building this end-to-end from scratch

---

## How to use this document

This PRD is written to be handed directly to a coding agent (e.g. an Antigravity agent) as a build spec. It is organized so that each section is buildable in order, with explicit acceptance criteria. Do not skip ahead to a later phase before the acceptance criteria of the current phase are met — later phases assume earlier ones are working and tested.

Where a decision has been made (e.g. "use Postgres," "use HMAC-SHA512"), build to that decision. Where a placeholder is marked `[CONFIRM]`, the agent must verify the actual value against Bitnob's live sandbox docs/response before hardcoding it, since some exact field names were inferred from partial documentation and need confirmation against a real sandbox call before being trusted in code.

---

## Table of Contents

1. Product Summary & Scope
2. System Architecture Overview
3. Tech Stack & Project Structure
4. Data Model (full schema)
5. Bitnob API Integration Layer
6. Core Business Logic — Invoice Lifecycle & Reconciliation
7. API Endpoints (full spec)
8. Webhook Receiver — Detailed Spec
9. Background Jobs (Celery)
10. Authentication & Security
11. PDF Receipt Generation
12. Environment Configuration
13. Testing Strategy
14. Deployment
15. Build Order / Milestones (do this in order)
16. Open Questions / Things to Confirm Against Live Sandbox

---

## 1. Product Summary & Scope

### 1.1 What this system does

Freelancers create USD-denominated invoices. Clients pay those invoices using Bitcoin (on-chain), Lightning, or a stablecoin (USDC/USDT), routed through the Bitnob API. The backend:

- Locks a USD-to-crypto exchange rate at the moment a client opens a payment page
- Generates a payment target (BTC address, Lightning invoice, or stablecoin deposit address) via Bitnob
- Listens for Bitnob webhooks confirming receipt of funds
- Reconciles received amounts against expected amounts (handling underpayment, overpayment, and exact payment)
- Generates a PDF receipt with on-chain proof (tx hash) once an invoice reaches a paid state
- Exposes a freelancer-facing dashboard API and a public client-facing payment-status API

### 1.2 What this system explicitly does NOT do (out of scope for v1)

- No custody of funds at any point — Bitnob holds funds; this backend only orchestrates and records state.
- No automatic refunds (see Section 6.4 — overpayment is handled via manual freelancer-initiated refund only).
- No payouts to freelancer bank accounts — this is a receiving-only system in v1. Bitnob's Payouts/Beneficiaries endpoints are not integrated in this phase.
- No multi-currency invoices beyond USD as the denominating currency.
- No support for more than one stablecoin network per invoice at a time.

### 1.3 Core principle the entire backend is built around

**Never treat "paid" as a boolean.** Every invoice tracks `amount_expected_usd` vs `amount_received_usd_equivalent` as decimal ledger values, with a state machine derived from comparing the two (within a tolerance). This is non-negotiable and described fully in Section 6.

---

## 2. System Architecture Overview

### 2.1 Component diagram

```
                         ┌──────────────────────────┐
                         │   Frontend (separate       │
                         │   repo, not covered here)  │
                         └─────────────┬──────────────┘
                                       │ REST (JSON)
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Application                         │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐ │
│  │ auth router │  │ invoices    │  │ webhooks    │  │ public pay   │ │
│  │             │  │ router      │  │ router      │  │ status router│ │
│  └────────────┘  └─────┬──────┘  └─────┬──────┘  └─────────────┘ │
│                         │                 │                          │
│                         ▼                 ▼                          │
│              ┌─────────────────────────────────────┐                │
│              │   Service layer (business logic)      │                │
│              │  - InvoiceService                      │                │
│              │  - ReconciliationService               │                │
│              │  - BitnobClient (signed HTTP client)   │                │
│              │  - ReceiptService                       │                │
│              └─────────────┬───────────────────────┘                │
└────────────────────────────┼──────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌──────────────┐ ┌────────────┐ ┌──────────────┐
      │  PostgreSQL   │ │   Redis     │ │  Bitnob API   │
      │  (system of   │ │  (Celery    │ │  (sandbox /    │
      │   record)     │ │   broker +  │ │   prod)        │
      │               │ │   cache)    │ │                │
      └──────────────┘ └─────┬──────┘ └──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Celery Workers    │
                    │  - process_webhook  │
                    │    _event (async)   │
                    │  - generate_receipt │
                    │  - send_email       │
                    │  - reconciliation_  │
                    │    sweep (beat job) │
                    └──────────────────┘
```

### 2.2 Request flow — happy path (Lightning payment, fully worked example)

1. Freelancer calls `POST /invoices` → invoice row created with `status=draft`, no payment target yet.
2. Freelancer shares `https://yourapp.com/pay/{invoice_id}` with client.
3. Client's browser calls `GET /public/invoices/{id}/payment-target?method=lightning`.
4. Backend checks: does this invoice already have a non-expired Lightning payment target? If not:
   a. Call Bitnob exchange rate endpoint → lock `rate_usd_to_btc` on the invoice.
   b. Compute `expected_btc_sats = amount_usd / rate_usd_to_btc` (converted to sats).
   c. Call Bitnob "Create Invoice" (Lightning) with `reference=invoice.bitnob_reference`, amount in sats.
   d. Store the returned BOLT11 `payment_request` and `expires_at` on a `payment_target` row linked to the invoice.
5. Backend returns the BOLT11 string + QR-renderable data + countdown expiry to the frontend.
6. Client pays via their Lightning wallet.
7. Bitnob fires a webhook (`POST /webhooks/bitnob`) with the payment event.
8. Webhook receiver verifies HMAC signature, deduplicates by `event_id`, persists the raw event, enqueues `process_webhook_event` as a Celery task, returns `200` immediately.
9. Celery worker resolves `reference` to `invoice_id`, creates a `Payment` row, runs `ReconciliationService.reconcile(invoice_id)` inside a DB transaction with row-level locking.
10. Reconciliation updates `invoice.status` per the state machine (Section 6).
11. If the new status is `paid` or `overpaid`, enqueue `generate_receipt`, which renders a PDF and enqueues `send_email` (to freelancer and client).
12. Client's frontend, which has been polling `GET /public/invoices/{id}/status` every 5s, sees `status=paid` and shows the confirmation screen.

### 2.3 Why Celery, not just FastAPI BackgroundTasks, for webhook processing

`BackgroundTasks` runs in-process and is lost if the process restarts mid-task, which is unacceptable for anything touching money. Celery plus Redis gives durable, retryable task execution, which matters specifically for: receipt generation (must not silently fail), email sending (must retry on transient failure), and the reconciliation sweep (must run on a reliable schedule independent of request traffic). Use `BackgroundTasks` nowhere in this system except possibly for non-critical logging.

---


## 3. Tech Stack & Project Structure

### 3.1 Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Web framework | FastAPI | async throughout |
| ORM | SQLAlchemy 2.0 (async) | use `asyncpg` driver |
| Migrations | Alembic | every schema change goes through a migration, never hand-edited prod DB |
| DB | PostgreSQL 15+ | |
| Cache / broker | Redis 7+ | used by Celery and for short-lived rate-lock caching |
| Background jobs | Celery | worker + beat (scheduler) as separate processes |
| HTTP client (outbound to Bitnob) | `httpx` (async) | |
| Validation | Pydantic v2 | request/response schemas, and Bitnob payload schemas |
| Auth | `python-jose` (JWT) + `passlib[bcrypt]` | freelancer auth only; public endpoints have no auth |
| PDF generation | `weasyprint` | renders HTML/CSS to PDF without a headless browser dependency |
| Email | `httpx` call to Resend API (or equivalent) | keep this behind an `EmailService` interface so the provider can be swapped |
| Testing | `pytest` + `pytest-asyncio` + `httpx` test client | |
| Linting/formatting | `ruff` | |

### 3.2 Project structure

Build exactly this structure. Do not flatten it or merge modules — the separation matters for testability, especially isolating the Bitnob client behind an interface so it can be mocked in tests.

```
backend/
├── alembic/
│   ├── versions/
│   └── env.py
├── app/
│   ├── main.py                      # FastAPI app instantiation, router includes
│   ├── config.py                    # Pydantic Settings, reads from env
│   ├── db.py                        # async engine, session factory
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── invoice.py
│   │   ├── payment.py
│   │   ├── payment_target.py
│   │   ├── webhook_event.py
│   │   └── overpayment_credit.py
│   ├── schemas/                     # Pydantic request/response models
│   │   ├── invoice.py
│   │   ├── payment.py
│   │   ├── auth.py
│   │   └── bitnob.py                # schemas for Bitnob's request/response shapes
│   ├── routers/
│   │   ├── auth.py
│   │   ├── invoices.py              # authenticated freelancer endpoints
│   │   ├── public.py                # unauthenticated client-facing endpoints
│   │   └── webhooks.py
│   ├── services/
│   │   ├── invoice_service.py
│   │   ├── reconciliation_service.py
│   │   ├── receipt_service.py
│   │   ├── bitnob_client.py         # signed HTTP client wrapping all Bitnob calls
│   │   └── email_service.py
│   ├── core/
│   │   ├── security.py              # JWT creation/verification, password hashing
│   │   └── exceptions.py            # custom exception classes
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks.py                 # all Celery task definitions
│   └── templates/
│       └── receipt.html             # Jinja2 template for the PDF receipt
├── tests/
│   ├── conftest.py
│   ├── test_reconciliation.py
│   ├── test_webhook_receiver.py
│   ├── test_bitnob_client.py
│   └── test_invoice_lifecycle.py
├── .env.example
├── pyproject.toml
├── alembic.ini
└── README.md
```

### 3.3 Why the service layer is separate from routers

Routers should be thin: parse request, call a service method, return response. All business logic (rate locking, reconciliation, state transitions) lives in `services/`. This is what makes the reconciliation logic testable without spinning up the whole HTTP stack, and it's what prevents the webhook handler and the REST API from drifting into two different implementations of the same logic — both call into `ReconciliationService`, there is exactly one reconciliation code path.

---

## 4. Data Model (full schema)

Use SQLAlchemy 2.0 declarative models. All monetary and crypto-amount fields use `Numeric`/`Decimal`, never `Float`. Floats introduce rounding errors that are unacceptable for ledger data — this is not a style preference, it is a correctness requirement.

### 4.1 `users` (freelancers)

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| email | String, unique, not null | |
| password_hash | String, not null | bcrypt via passlib |
| business_name | String, nullable | shown on invoices/receipts |
| created_at | TIMESTAMPTZ, not null, default now() | |
| updated_at | TIMESTAMPTZ, not null, default now(), onupdate now() | |

### 4.2 `invoices`

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| user_id | UUID, FK → users.id, not null | the freelancer |
| client_name | String, not null | |
| client_email | String, not null | |
| description | Text, nullable | |
| amount_usd | Numeric(12,2), not null | the headline invoice amount, always USD |
| status | Enum (see 4.2.1), not null, default `draft` | |
| bitnob_reference | String, unique, not null | generated at creation, e.g. `INV_{uuid4 short}` — this is the correlation key for every Bitnob call related to this invoice |
| amount_received_usd_equiv | Numeric(12,2), not null, default 0 | running total, in USD-equivalent at time of each payment's locked rate — see Section 6 for how this is computed |
| overpaid_amount_usd | Numeric(12,2), not null, default 0 | only non-zero when status = `overpaid` |
| due_date | Date, nullable | cosmetic only in v1 |
| created_at | TIMESTAMPTZ, not null, default now() | |
| updated_at | TIMESTAMPTZ, not null, default now(), onupdate now() | |

**Indexes:** `idx_invoices_user_id`, unique index on `bitnob_reference`, index on `status` (used heavily by the reconciliation sweep job).

#### 4.2.1 Invoice status enum — the full state machine

```python
class InvoiceStatus(str, Enum):
    DRAFT = "draft"                  # created, no payment target generated yet
    PENDING = "pending"               # payment target generated, awaiting payment
    PARTIALLY_PAID = "partially_paid" # some funds received, less than expected
    PAID = "paid"                     # funds received within tolerance of expected
    OVERPAID = "overpaid"             # funds received exceed expected beyond tolerance
    EXPIRED = "expired"               # payment target/rate lock expired with zero payment
    CANCELLED = "cancelled"           # freelancer manually cancelled
    REFUNDED = "refunded"             # manual refund recorded (v1: record-keeping only, no automated refund execution)
```

**Allowed transitions (enforce this explicitly in code — reject any transition not in this table):**

| From | To | Trigger |
|---|---|---|
| `draft` | `pending` | payment target successfully generated |
| `pending` | `partially_paid` | payment received, total < expected - tolerance |
| `pending` | `paid` | payment received, total within tolerance of expected |
| `pending` | `overpaid` | payment received, total > expected + tolerance |
| `pending` | `expired` | rate lock / payment target TTL elapsed, zero payments received |
| `pending` | `cancelled` | freelancer action |
| `partially_paid` | `partially_paid` | additional payment received, still short |
| `partially_paid` | `paid` | additional payment received, now within tolerance |
| `partially_paid` | `overpaid` | additional payment received, now exceeds tolerance |
| `expired` | `paid` / `partially_paid` / `overpaid` | late payment arrives — honor the original locked rate (see Section 6.5) |
| `paid` | `overpaid` | an additional, unexpected payment arrives after already-paid |
| `overpaid` | `refunded` | freelancer manually records a refund |
| any | `cancelled` | freelancer action, only permitted from `draft` or `pending` — never cancel an invoice with any received funds |

**Explicitly forbidden transitions** (write a unit test asserting these raise an `InvalidStateTransitionError`):
- `paid` → `pending` or `draft` (never un-pay an invoice)
- `overpaid` → `partially_paid` (money already exceeds expectation; cannot become "less paid")
- `refunded` → anything (terminal state)
- `cancelled` → anything (terminal state)

### 4.3 `payment_targets`

One invoice can have multiple payment targets over its lifetime (e.g., a fresh Lightning invoice generated after the first one expired, or three separate targets if the freelancer enabled BTC + Lightning + USDC and the client's frontend requested all three).

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| invoice_id | UUID, FK → invoices.id, not null | |
| method | Enum: `btc_onchain`, `lightning`, `usdc`, `usdt` | |
| network | String, nullable | e.g. chain name for stablecoins — populate from `[CONFIRM]` Stablecoin Networks response, do not hardcode |
| target_value | String, not null | the BTC address, BOLT11 string, or stablecoin deposit address |
| rate_locked_usd_to_crypto | Numeric(20,8), not null | the locked exchange rate at generation time |
| amount_expected_crypto | Numeric(20,8), not null | computed from `invoice.amount_usd` / `rate_locked_usd_to_crypto` (or the remaining balance if this is a top-up target — see 4.3.1) |
| bitnob_response_raw | JSONB, nullable | store the full raw Bitnob response for debugging/audit |
| expires_at | TIMESTAMPTZ, not null | |
| is_active | Boolean, not null, default true | set false once expired or superseded by a new target |
| created_at | TIMESTAMPTZ, not null, default now() | |

**Indexes:** `idx_payment_targets_invoice_id`, index on `(invoice_id, is_active)`.

#### 4.3.1 Top-up targets for partial payments

When an invoice is `partially_paid`, do not generate a whole new invoice. Generate a new `payment_target` row scoped to the **remaining balance only** (`invoice.amount_usd - invoice.amount_received_usd_equiv`), linked to the same `invoice_id`. This is what lets the client "pay the remaining balance" without restarting the whole flow, per the recommended UX pattern from Section 6.

### 4.4 `payments`

Append-only ledger of every confirmed receipt of funds against an invoice. Never update or delete rows here except to add `confirmations` as they increase for an already-recorded BTC payment (see note below).

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| invoice_id | UUID, FK → invoices.id, not null | |
| payment_target_id | UUID, FK → payment_targets.id, not null | which specific target this payment was received against |
| tx_hash | String, not null | the on-chain hash, or BOLT11 payment hash for Lightning |
| amount_received_crypto | Numeric(20,8), not null | exact amount as reported by Bitnob |
| amount_received_usd_equiv | Numeric(12,2), not null | computed using the *target's locked rate*, not a live rate, per Section 6.5 |
| method | Enum: `btc_onchain`, `lightning`, `usdc`, `usdt` | |
| network | String, nullable | |
| confirmations | Integer, not null, default 0 | |
| bitnob_event_id | String, FK → webhook_events.event_id, not null | traceability back to the exact webhook that produced this row |
| received_at | TIMESTAMPTZ, not null | |
| created_at | TIMESTAMPTZ, not null, default now() | |

**Unique constraint:** `(tx_hash, invoice_id)` — prevents the same on-chain transaction from ever being recorded twice against the same invoice, which is a second layer of defense beyond webhook event deduplication.

**Note on confirmations:** for BTC on-chain payments, Bitnob will likely send multiple webhook events for the same `tx_hash` as confirmation count increases. Do not insert a new `payments` row for each — instead, update the existing row's `confirmations` field, keyed by `tx_hash`. Only the *first* sighting of a given `tx_hash` should trigger reconciliation logic for the underpaid/overpaid calculation; subsequent confirmation-count updates should not re-run the full reconciliation state machine, only update the confirmation count and, if you choose to gate "paid" status on a minimum confirmation count (see open question in Section 16), potentially trigger the final state transition once the threshold is met.

### 4.5 `webhook_events`

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| event_id | String, unique, not null | Bitnob's top-level `event_id` — the deduplication key |
| event_type | String, not null | e.g. `stablecoin.usdc.received.success` |
| raw_payload | JSONB, not null | full original payload, for audit/replay |
| signature_valid | Boolean, not null | record this even though invalid-signature events should be rejected before reaching this table in the happy path — useful for security audit logs if you choose to log-and-reject rather than just reject |
| processed_at | TIMESTAMPTZ, nullable | null until the Celery task finishes processing |
| processing_error | Text, nullable | populated if `process_webhook_event` raised |
| created_at | TIMESTAMPTZ, not null, default now() | |

**Unique constraint on `event_id` is the core deduplication mechanism** — the webhook receiver should attempt to insert this row inside a transaction and treat a unique-constraint violation as "already processed, ack and skip," not as an error to surface to Bitnob (still return 200).

### 4.6 `overpayment_credits`

Implements Option A from the reconciliation design (accept + notify) plus a lightweight aging queue so overpayments don't become invisible.

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| user_id | UUID, FK → users.id, not null | the freelancer who received the overpayment |
| source_invoice_id | UUID, FK → invoices.id, not null | |
| amount_usd | Numeric(12,2), not null | |
| status | Enum: `unresolved`, `refunded`, `acknowledged_keep` | freelancer must explicitly resolve — see 4.6.1 |
| created_at | TIMESTAMPTZ, not null, default now() | used to compute "age" for the dashboard warning |
| resolved_at | TIMESTAMPTZ, nullable | |

#### 4.6.1 Resolution actions (freelancer-facing, v1 scope)

- **`acknowledged_keep`** — freelancer confirms they are keeping the overpayment as a tip/buffer. No money moves. Just closes the record.
- **`refunded`** — freelancer confirms they manually refunded the client out-of-band (e.g., sent it back via their own wallet outside this system). This is a record-keeping action only in v1 — the backend does not execute the refund itself, per the decision in Section 6.4 to avoid automated refunds.

Dashboard must surface any `overpayment_credits` row with `status=unresolved` and `created_at` older than 7 days as a flagged item — do not let these silently age forever unseen.

---

## 5. Bitnob API Integration Layer

### 5.1 Authentication scheme

Bitnob's sandbox docs show two different auth patterns depending on context — confirm which applies to the specific endpoints you're calling before writing the client:

- Some endpoint examples use a simple `Authorization: Bearer API-KEY` header.
- The account-setup / HMAC pattern described in earlier discovery references `CLIENT_ID` + `CLIENT_SECRET` with HMAC-SHA256 request signing using `X-Auth-Client`, `X-Auth-Signature`, `X-Auth-Timestamp`, `X-Auth-Nonce` headers.

**[CONFIRM]** Before writing `bitnob_client.py`, make one real authenticated sandbox call to `GET /api/v1/wallets` using whichever scheme the current Bitnob developer dashboard issues credentials for, and confirm which header set is actually required. Build `BitnobClient` around whichever is confirmed — do not implement both speculatively.

### 5.2 `BitnobClient` design

Build this as a single class wrapping all outbound Bitnob calls. No other part of the codebase should construct an HTTP request to Bitnob directly — this is the only place that knows about signing, base URLs, and retry behavior.

```python
# app/services/bitnob_client.py

import hashlib
import hmac
import time
import uuid
import httpx
from app.config import settings

class BitnobClient:
    def __init__(self):
        self.base_url = settings.BITNOB_BASE_URL  # sandboxapi.bitnob.co or api.bitnob.com
        self.client_id = settings.BITNOB_CLIENT_ID
        self.client_secret = settings.BITNOB_CLIENT_SECRET
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=15.0)

    def _sign(self, timestamp: str, nonce: str, payload: str) -> str:
        message = f"{self.client_id}:{timestamp}:{nonce}:{payload}"
        return hmac.new(
            self.client_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def _headers(self, payload: str) -> dict:
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        signature = self._sign(timestamp, nonce, payload)
        return {
            "X-Auth-Client": self.client_id,
            "X-Auth-Timestamp": timestamp,
            "X-Auth-Nonce": nonce,
            "X-Auth-Signature": signature,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        import json as json_lib
        payload = json_lib.dumps(json_body) if json_body else ""
        headers = self._headers(payload)
        response = await self._http.request(method, path, headers=headers, json=json_body)
        response.raise_for_status()
        return response.json()

    # --- Public methods, one per Bitnob capability used by this app ---

    async def get_exchange_rate(self, pair: str = "btcusd") -> dict:
        return await self._request("GET", "/api/v1/wallets/exchange-rates")  # [CONFIRM] exact path/params

    async def get_stablecoin_networks(self) -> dict:
        return await self._request("GET", "/api/v1/wallets/stable-coins-networks")

    async def generate_btc_address(self, reference: str, customer_email: str) -> dict:
        return await self._request("POST", "/api/v1/wallets/address", {
            "reference": reference,
            "customerEmail": customer_email,
        })  # [CONFIRM] exact field names against live docs

    async def create_lightning_invoice(self, sats: int, reference: str, customer_email: str, description: str = "") -> dict:
        return await self._request("POST", "/api/v1/wallets/ln/createinvoice", {
            "satoshis": sats,
            "reference": reference,
            "customerEmail": customer_email,
            "description": description,
        })

    async def get_lightning_invoice(self, invoice_id: str) -> dict:
        return await self._request("GET", f"/api/v1/wallets/ln/invoice/{invoice_id}")

    async def decode_payment_request(self, request: str) -> dict:
        return await self._request("GET", "/api/v1/wallets/ln/decodepaymentrequest", {"request": request})

    async def get_stablecoin_deposit_address(self, network: str, reference: str, customer_email: str) -> dict:
        return await self._request("POST", "/api/v1/wallets/stablecoin/address", {
            "network": network,
            "reference": reference,
            "customerEmail": customer_email,
        })  # [CONFIRM] exact path and field names — not directly observed in discovery

    async def list_transactions(self, reference: str | None = None) -> dict:
        params = {"reference": reference} if reference else {}
        return await self._request("GET", "/api/v1/transactions", params)
```

### 5.3 Error handling contract

Every method on `BitnobClient` can raise:
- `httpx.HTTPStatusError` on non-2xx — catch this at the service layer (`InvoiceService`, never in routers) and translate into a domain-specific exception (e.g. `PaymentTargetGenerationError`) that the router layer turns into a clean 502/503 response to the frontend. Never let a raw `httpx` exception or Bitnob's raw error JSON leak into an API response.
- `httpx.TimeoutException` — wrap all Bitnob calls with a retry policy: 2 retries, exponential backoff starting at 1s, only for idempotent GET requests (exchange rate, list transactions, get invoice status). **Never automatically retry a POST that creates a payment target or sends funds** — a retried "generate address" call should be safe (idempotent on Bitnob's side, scoped by reference) but retrying anything that could double-trigger an outbound send must not be done blindly. Treat any POST failure as a failure surfaced to the caller, not silently retried.

### 5.4 Caching the exchange rate lookup

Exchange rates should be cached in Redis for a short TTL (e.g. 30 seconds) to avoid hammering Bitnob's rate endpoint if multiple clients open payment pages in quick succession. This is a read-through cache: check Redis first, call Bitnob on miss, write through with the TTL. This caching only applies to *looking up* the current rate for display/quoting purposes — once a rate is locked onto a specific `payment_target` row, it is never re-fetched or refreshed for that target.

---

## 6. Core Business Logic — Invoice Lifecycle & Reconciliation

This is the most important section of this document. Read it fully before writing any reconciliation code.

### 6.1 Ledger-first principle (restated precisely)

Every invoice tracks two running numbers:
- `amount_usd` — fixed at creation, the invoice total.
- `amount_received_usd_equiv` — a running sum, updated only by `ReconciliationService`, computed by summing `payments.amount_received_usd_equiv` for all payments on that invoice.

Status is **always derived** from comparing these two numbers (plus tolerance). Status is never set directly by any code path other than `ReconciliationService.reconcile()`. If you find yourself writing `invoice.status = InvoiceStatus.PAID` anywhere outside that one method, that is a bug.

### 6.2 Tolerance — defined in USD, not in crypto units

Do not hardcode a fixed satoshi or token-unit tolerance. Define tolerance as a small USD-equivalent band, computed against the invoice amount:

```python
# app/services/reconciliation_service.py

from decimal import Decimal

# Absolute floor: covers genuine rounding/dust regardless of invoice size.
MIN_TOLERANCE_USD = Decimal("0.05")

# Relative ceiling: scales with invoice size so large invoices aren't
# falsely flagged paid/overpaid from proportionally larger crypto rounding.
TOLERANCE_BPS = Decimal("10")  # 0.10%

def compute_tolerance_usd(amount_usd: Decimal) -> Decimal:
    relative = amount_usd * TOLERANCE_BPS / Decimal("10000")
    return max(MIN_TOLERANCE_USD, relative)
```

This replaces a hardcoded crypto-denominated constant. It is currency-agnostic — the same function applies whether the payment came in as BTC, Lightning, or a stablecoin — because the comparison always happens in USD-equivalent space, never in raw crypto units.

### 6.3 Computing `amount_received_usd_equiv` for a single payment

When a payment arrives, convert its crypto amount to USD using **the rate locked on the `payment_target` it was paid against**, never a freshly-fetched live rate:

```python
payment.amount_received_usd_equiv = (
    payment.amount_received_crypto * payment_target.rate_locked_usd_to_crypto
)
```

This is what makes "honor the original quote" (Section 6.5) actually work — the USD value of a late payment is computed using the rate that was true when the quote was issued, not the rate at the moment the webhook fires.

### 6.4 The reconciliation algorithm (full implementation)

```python
# app/services/reconciliation_service.py

from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.overpayment_credit import OverpaymentCredit
from app.core.exceptions import InvalidStateTransitionError

ALLOWED_TRANSITIONS = {
    InvoiceStatus.DRAFT: {InvoiceStatus.PENDING, InvoiceStatus.CANCELLED},
    InvoiceStatus.PENDING: {
        InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID,
        InvoiceStatus.OVERPAID, InvoiceStatus.EXPIRED, InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.PARTIALLY_PAID: {
        InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID, InvoiceStatus.OVERPAID,
    },
    InvoiceStatus.EXPIRED: {
        InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERPAID,
    },
    InvoiceStatus.PAID: {InvoiceStatus.OVERPAID},
    InvoiceStatus.OVERPAID: {InvoiceStatus.REFUNDED},
    InvoiceStatus.CANCELLED: set(),
    InvoiceStatus.REFUNDED: set(),
}

class ReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile(self, invoice_id: str) -> Invoice:
        """
        Must be called with the invoice row locked (SELECT ... FOR UPDATE)
        to prevent concurrent webhook events from racing on the same invoice.
        This is the ONLY method permitted to change invoice.status.
        """
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id).with_for_update()
        )
        invoice = result.scalar_one()

        # Recompute the running total from the payments ledger — never trust
        # an incrementally-updated counter, always re-sum from source rows.
        payments_result = await self.db.execute(
            select(Payment).where(Payment.invoice_id == invoice_id)
        )
        payments = payments_result.scalars().all()
        total_received = sum((p.amount_received_usd_equiv for p in payments), Decimal("0"))

        tolerance = compute_tolerance_usd(invoice.amount_usd)
        delta = invoice.amount_usd - total_received  # positive = still short

        if total_received <= Decimal("0"):
            new_status = invoice.status  # no payment yet, no transition triggered here
        elif delta > tolerance:
            new_status = InvoiceStatus.PARTIALLY_PAID
        elif delta >= -tolerance:
            new_status = InvoiceStatus.PAID
        else:
            new_status = InvoiceStatus.OVERPAID

        if new_status != invoice.status:
            self._assert_valid_transition(invoice.status, new_status)
            invoice.status = new_status

        invoice.amount_received_usd_equiv = total_received

        if new_status == InvoiceStatus.OVERPAID:
            overpaid_amount = total_received - invoice.amount_usd
            invoice.overpaid_amount_usd = overpaid_amount
            await self._ensure_overpayment_credit_recorded(invoice, overpaid_amount)

        await self.db.commit()
        return invoice

    def _assert_valid_transition(self, current: InvoiceStatus, target: InvoiceStatus) -> None:
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition invoice from {current} to {target}"
            )

    async def _ensure_overpayment_credit_recorded(self, invoice: Invoice, amount: Decimal) -> None:
        existing = await self.db.execute(
            select(OverpaymentCredit).where(
                OverpaymentCredit.source_invoice_id == invoice.id,
                OverpaymentCredit.status == "unresolved",
            )
        )
        if existing.scalar_one_or_none() is None:
            self.db.add(OverpaymentCredit(
                user_id=invoice.user_id,
                source_invoice_id=invoice.id,
                amount_usd=amount,
                status="unresolved",
            ))
```

**Critical implementation requirement: the `SELECT ... FOR UPDATE` row lock.** This is what prevents the race condition where two webhook events for the same invoice (e.g. two partial payments arriving seconds apart) both read the pre-update total and both write an incorrect result. Every call into `reconcile()` must happen inside a transaction that locks the invoice row first. Do not optimize this away — it is the single most important correctness guarantee in this codebase.

### 6.5 Honoring the original quote on late/expired payments

When a payment arrives for an invoice whose associated `payment_target` has `expires_at` in the past:
- **Do not** re-fetch a current exchange rate.
- **Do** still compute `amount_received_usd_equiv` using the *original* `rate_locked_usd_to_crypto` stored on that `payment_target` row.
- Proceed through the normal reconciliation algorithm above using that value.

This is why `rate_locked_usd_to_crypto` lives on `payment_targets`, immutable once written, never updated after creation.

**Known limitation, acceptable for v1, must be documented in code comments where this logic lives:** honoring an expired quote indefinitely creates an open-ended optionality risk if BTC price moves significantly between quote and late payment. V1 accepts this risk. A future version should cap how late "late" is allowed to be (e.g., honor up to 24 hours past expiry, require a fresh quote after that) — do not build this cap now, but leave a `# TODO: cap late-payment honor window, see PRD section 6.5` comment so it's a deliberate, visible decision, not a forgotten one.

### 6.6 Overpayment handling (Option A — accept and flag, no automated refunds)

As implemented in `_ensure_overpayment_credit_recorded` above: when an invoice becomes `overpaid`, write a row to `overpayment_credits` with `status=unresolved`. This is the entire v1 overpayment handling mechanism. Do not build any automatic refund execution — this was a deliberate scope decision (see Section 1.2 and the earlier design discussion on why automated refunds are dangerous: sender addresses are frequently unrecoverable for Lightning payments and exchange-sourced transfers).

The freelancer-facing dashboard must surface unresolved `overpayment_credits` prominently, and flag any older than 7 days distinctly (see Section 4.6.1).

### 6.7 Underpayment / top-up flow

When `reconcile()` produces `PARTIALLY_PAID`:
1. The public payment-status endpoint (Section 7.3) returns the remaining balance (`invoice.amount_usd - invoice.amount_received_usd_equiv`) to the frontend.
2. If the client wants to pay the remainder, the frontend calls the payment-target endpoint again; `InvoiceService` must detect the invoice is `partially_paid` and generate a **new payment target scoped to the remaining balance only** (per Section 4.3.1), not a target for the full original amount.
3. This new target gets its own fresh rate lock — the remaining balance is re-quoted at current rates, since the original quote was for the original (now partially fulfilled) amount, not a fixed crypto amount that should be re-honored. (This is different from 6.5 — 6.5 is about honoring a quote for a payment already in flight against an existing target; this is about quoting a new target for a remaining balance, which is a new pricing event.)

---

## 7. API Endpoints (full spec)

All authenticated endpoints require `Authorization: Bearer <JWT>`. Public endpoints require no auth and must never expose any other freelancer's data — every public endpoint is scoped strictly by `invoice_id` (a UUID, not guessable), and returns only the fields a client needs to pay and confirm, never internal fields like `user_id` or full payment history of other invoices.

### 7.1 Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | none | body: `email`, `password`, `business_name`. Returns JWT. |
| POST | `/auth/login` | none | body: `email`, `password`. Returns JWT. |
| GET | `/auth/me` | required | returns current user profile. |

### 7.2 Freelancer invoice management (authenticated)

| Method | Path | Description |
|---|---|---|
| POST | `/invoices` | Create invoice. Body: `client_name`, `client_email`, `description`, `amount_usd`, `due_date` (optional). Creates row with `status=draft`. Does NOT call Bitnob — payment targets are generated lazily (see 2.2). |
| GET | `/invoices` | List invoices for the authenticated user. Supports `?status=` filter and pagination (`?page=`, `?page_size=`). |
| GET | `/invoices/{id}` | Full detail of a single invoice, including all `payment_targets` and `payments`. Must verify `invoice.user_id == current_user.id` or return 404 (not 403 — don't leak existence of other users' invoices). |
| POST | `/invoices/{id}/cancel` | Transitions `draft` or `pending` → `cancelled`. Reject (409) if invoice has any received payments. |
| POST | `/invoices/{id}/resend` | Re-sends the payment link email to the client. Rate-limit this (e.g. max 1 per 5 minutes per invoice) to prevent abuse. |
| GET | `/invoices/{id}/receipt` | Returns the receipt PDF (or a signed URL to it), only once status is `paid`/`partially_paid`/`overpaid`. 404 if not yet generated. |
| GET | `/overpayment-credits` | List unresolved/resolved overpayment credits for the freelancer's invoices. |
| POST | `/overpayment-credits/{id}/resolve` | Body: `action` (`acknowledged_keep` or `refunded`). Updates status, sets `resolved_at`. |

### 7.3 Public client-facing endpoints (no auth)

| Method | Path | Description |
|---|---|---|
| GET | `/public/invoices/{id}` | Returns minimal invoice display data: `client_name`, `business_name` (of freelancer), `description`, `amount_usd`, `status`, `due_date`. No internal IDs beyond what's needed. |
| GET | `/public/invoices/{id}/payment-methods` | Returns which methods the freelancer enabled (`btc_onchain`, `lightning`, `usdc`, `usdt`) so the frontend can render method-selection cards. |
| POST | `/public/invoices/{id}/payment-target?method={method}` | The core "give me something to pay" endpoint. See 7.3.1 below for full logic. |
| GET | `/public/invoices/{id}/status` | Lightweight polling endpoint. Returns `status`, `amount_received_usd_equiv`, `remaining_usd` (if partially paid), `overpaid_amount_usd` (if overpaid), and the active payment target's `expires_at` if still pending. This is what the frontend polls every ~5 seconds. |
| GET | `/public/invoices/{id}/receipt` | Returns the receipt PDF once available. Same access pattern as the authenticated version, just without auth (still scoped by the unguessable invoice UUID). |

#### 7.3.1 `POST /public/invoices/{id}/payment-target` — detailed logic

This endpoint must be idempotent and safe to call repeatedly (the frontend may call it on page load, and again if the user switches payment method tabs).

```
1. Load invoice. If status not in {draft, pending, partially_paid, expired}, return 409
   (e.g. invoice is already fully paid or cancelled — nothing to generate).
2. Check for an existing payment_target for this invoice + method where is_active=true
   and expires_at > now().
   - If found: return it directly (no new Bitnob call).
3. If not found (none exists, or existing one expired):
   a. If invoice.status == draft: transition to pending (first target ever generated).
   b. Determine the amount to quote:
      - If invoice.status in {pending, draft, expired} with zero payments received:
        quote the full invoice.amount_usd.
      - If invoice.status == partially_paid: quote only the remaining balance
        (invoice.amount_usd - invoice.amount_received_usd_equiv), per Section 6.7.
   c. Call BitnobClient to fetch current rate, lock it on the new payment_target row.
   d. Call the appropriate BitnobClient method for the requested method
      (generate_btc_address / create_lightning_invoice / get_stablecoin_deposit_address).
   e. Mark any prior payment_target for this invoice+method as is_active=false.
   f. Persist new payment_target, commit.
4. Return payment_target details: target_value (address/BOLT11/etc.), amount_expected_crypto,
   rate_locked_usd_to_crypto, expires_at.
```

### 7.4 Webhooks

| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/bitnob` | Receives all Bitnob webhook events. See Section 8 for full spec. |

---

## 8. Webhook Receiver — Detailed Spec

### 8.1 Endpoint implementation

```python
# app/routers/webhooks.py

import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from app.db import get_session
from app.models.webhook_event import WebhookEvent
from app.workers.tasks import process_webhook_event
from app.config import settings

router = APIRouter()

@router.post("/webhooks/bitnob")
async def bitnob_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-bitnob-signature", "")

    expected = hmac.new(
        settings.BITNOB_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    # Constant-time comparison — never use `==` for signature checks.
    if not hmac.compare_digest(expected, signature):
        # Return 401, but DO NOT include any detail about what was expected.
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event")
    data = payload.get("data", {})
    event_id = data.get("event_id") or data.get("id")  # [CONFIRM] field name consistency
                                                          # across event types — some examples
                                                          # show "id", newer ones show "event_id"

    if not event_id:
        # Cannot dedupe without an identifier — log loudly, still ack 200
        # so Bitnob doesn't retry indefinitely, but flag for manual review.
        await log_malformed_webhook(payload)
        return {"status": "ok"}

    async with get_session() as db:
        existing = await db.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        )
        if existing.scalar_one_or_none() is not None:
            return {"status": "ok"}  # already processed, ack without reprocessing

        webhook_row = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            raw_payload=payload,
            signature_valid=True,
        )
        db.add(webhook_row)
        await db.commit()

    # Hand off to Celery — do not process synchronously in the request handler.
    process_webhook_event.delay(str(webhook_row.id))

    return {"status": "ok"}
```

### 8.2 Why signature verification happens before JSON parsing of anything meaningful

Read `raw_body` as bytes and compute the HMAC over the **exact raw bytes received**, not over a re-serialized JSON object. If you parse JSON first and re-`json.dumps()` it to compute the signature, differences in key ordering or whitespace will produce a different signature than what Bitnob actually signed, causing valid webhooks to be rejected. Always verify against the raw request body bytes.

### 8.3 Always return 200 quickly

Per Bitnob's documented retry behavior (3 retries on non-200), the handler above does the minimum synchronous work (verify signature, dedupe-check, persist raw event) and delegates everything else — resolving the invoice, updating the ledger, generating receipts — to a Celery task. A slow handler risks Bitnob's request timing out and triggering a retry storm even though the event already succeeded on your end.

### 8.4 Event routing inside the Celery task

```python
# app/workers/tasks.py

EVENT_HANDLERS = {
    "stablecoin.usdc.received.success": handle_stablecoin_received,
    "stablecoin.usdt.received.success": handle_stablecoin_received,
    "btc.received.success": handle_btc_received,          # [CONFIRM] exact event name
    "ln.invoice.paid": handle_lightning_paid,               # [CONFIRM] exact event name
}

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_webhook_event(self, webhook_event_id: str):
    try:
        # load webhook_event row, dispatch to EVENT_HANDLERS[event_type],
        # each handler is responsible for:
        #   1. resolving `reference` from the payload -> invoice_id
        #   2. upserting a Payment row (insert if new tx_hash, update confirmations if seen)
        #   3. calling ReconciliationService.reconcile(invoice_id) inside a locked transaction
        #   4. if new status in {paid, partially_paid, overpaid}, enqueue generate_receipt.delay(invoice_id)
        ...
    except Exception as exc:
        # mark webhook_event.processing_error, let Celery retry per the decorator config
        raise self.retry(exc=exc)
```

Each handler must be written defensively: if `reference` doesn't resolve to any known invoice (e.g. a test event, or a reference format mismatch), log it clearly and return without raising — this is a data inconsistency to investigate, not a transient failure to retry indefinitely.

---

## 9. Background Jobs (Celery)

### 9.1 Task list

| Task | Trigger | Purpose |
|---|---|---|
| `process_webhook_event` | enqueued by webhook receiver | full event processing, as in 8.4 |
| `generate_receipt` | enqueued after reconciliation produces paid/partially_paid/overpaid | renders PDF, stores it, enqueues `send_email` |
| `send_email` | enqueued by `generate_receipt`, also by invoice creation (send initial payment link) and `/invoices/{id}/resend` | all outbound email goes through this one task |
| `reconciliation_sweep` | Celery beat, every 5 minutes | safety net described in 9.2 |
| `expire_stale_payment_targets` | Celery beat, every 1 minute | marks `payment_targets` with `expires_at < now()` and `is_active=true` as `is_active=false`; if an invoice has zero payments and its only targets are now all inactive, transition it to `expired` via `ReconciliationService` |

### 9.2 `reconciliation_sweep` — the fallback Bitnob explicitly recommends

Bitnob's own webhook documentation recommends maintaining a polling fallback in case webhook delivery fails. Implement this as:

```python
@celery_app.task
def reconciliation_sweep():
    """
    Runs every 5 minutes. For every invoice in {pending, partially_paid}
    that has at least one active, non-expired payment_target, call
    BitnobClient.list_transactions(reference=invoice.bitnob_reference)
    and compare against what's already recorded in `payments`.
    If Bitnob shows a transaction not present locally (e.g. webhook was
    lost), insert it and run reconciliation — using the exact same
    ReconciliationService code path the webhook handler uses.
    """
```

This task must call into the same `ReconciliationService.reconcile()` method as the webhook path — never duplicate the reconciliation logic here. The only difference between this and the webhook path is *how* a new payment is discovered (polling vs. push); once discovered, the downstream logic is identical.

### 9.3 Celery configuration notes

- Run `celery worker` and `celery beat` as separate, independently deployed processes — not in the same process as the FastAPI app.
- Use Redis as both broker and result backend for simplicity in v1.
- Set `task_acks_late = True` and a reasonable `task_time_limit` so a crashed worker doesn't silently lose an in-flight webhook-processing task.

---

## 10. Authentication & Security

### 10.1 Freelancer auth (JWT)

- Passwords hashed with bcrypt via `passlib`.
- JWT signed with a server-side secret (`JWT_SECRET` env var), short-lived access token (e.g. 1 hour) — refresh-token flow is acceptable to skip for v1 given the low-stakes nature of a re-login, but document this as a deliberate v1 simplification.
- All `/invoices/*` routes (non-public) depend on a `get_current_user` dependency that decodes and validates the JWT, 401s on failure.

### 10.2 Public endpoint security model

Public endpoints are secured by **unguessability of the invoice UUID**, not by auth. This is an acceptable and common pattern (Stripe Checkout links work the same way), but it means:
- Invoice IDs must be UUIDv4 (already true per the schema), never sequential integers.
- Public endpoints must never return any field that could let someone enumerate or infer other invoices (e.g., never return `user_id`, never return a list of "other invoices from this freelancer").
- Rate-limit public endpoints per-IP (e.g. via `slowapi` or a Redis-backed limiter) to prevent brute-force UUID guessing, even though guessing a UUIDv4 is computationally infeasible — defense in depth.

### 10.3 Webhook security

- HMAC-SHA512 signature verification on every incoming webhook, as specified in Section 8 — non-negotiable, this is the only thing standing between your invoice ledger and anyone who finds your webhook URL.
- Store `BITNOB_WEBHOOK_SECRET` and `BITNOB_CLIENT_SECRET` only in environment variables / a secrets manager, never in source control. Add both to `.gitignore`'d `.env`, document required vars in `.env.example` with placeholder values only.
- Webhook endpoint should not be discoverable/guessable beyond its fixed path — Bitnob will need the exact URL configured in their dashboard, so this is inherently a fixed, known endpoint; security here rests entirely on signature verification, not obscurity.

### 10.4 Secrets and key rotation

Follow Bitnob's own documented guidance: name keys recognizably (`dev-sandbox-key`, `prod-main-key`), copy the secret at creation time since it won't be shown again, and rotate periodically. Document the rotation procedure in the README even if not automated in v1.

---

## 11. PDF Receipt Generation

### 11.1 Trigger

`generate_receipt` Celery task, enqueued whenever `ReconciliationService.reconcile()` produces a status of `paid`, `partially_paid` (yes — generate an interim receipt showing partial payment, since the client may want proof of what they've paid so far), or `overpaid`.

### 11.2 Implementation

- Use `weasyprint` to render `app/templates/receipt.html` (a Jinja2 template) to PDF. This avoids a headless-browser dependency (no Puppeteer/Playwright needed in the Python stack).
- Template must include: freelancer business name, client name, invoice description, amount paid (crypto amount and USD-equivalent), payment method, tx hash, a block-explorer link (construct this based on `method`/`network` — e.g. mempool.space for BTC, the relevant chain explorer for stablecoins), timestamp, and invoice reference number.
- Store the rendered PDF in object storage (S3-compatible — use whatever the deployment target provides; for local/dev, local filesystem under a `receipts/` directory is acceptable) and save the URL/path on a `receipts` table (add this table if not already present — track `invoice_id`, `payment_id` it corresponds to, `pdf_path`, `generated_at`).
- After storing, enqueue `send_email` with the receipt attached/linked, to both `invoice.client_email` and the freelancer's `user.email`.

### 11.3 Regenerating receipts

If additional payments arrive after a receipt was already generated (e.g. a partial-payment receipt exists, then the balance is paid off), generate a **new** receipt reflecting the updated total rather than mutating the old one. Keep both records — this preserves an honest audit trail of what was known at each point in time.

---

## 12. Environment Configuration

### 12.1 Required environment variables (`.env.example`)

```
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/invoicing

# Redis
REDIS_URL=redis://localhost:6379/0

# Bitnob
BITNOB_BASE_URL=https://sandboxapi.bitnob.co
BITNOB_CLIENT_ID=
BITNOB_CLIENT_SECRET=
BITNOB_WEBHOOK_SECRET=

# Auth
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60

# Email
EMAIL_PROVIDER_API_KEY=
EMAIL_FROM_ADDRESS=receipts@yourapp.com

# App
APP_BASE_URL=http://localhost:8000
FRONTEND_BASE_URL=http://localhost:3000
ENVIRONMENT=development   # development | staging | production
```

### 12.2 Sandbox-to-production cutover

Per Bitnob's documented pattern, the same `BITNOB_CLIENT_ID` carries across environments — only `BITNOB_CLIENT_SECRET` and `BITNOB_BASE_URL` change between sandbox and production. Build `config.py` so switching `ENVIRONMENT` and these two values is the *entire* cutover procedure — no code branches on environment beyond config loading.

### 12.3 Local webhook testing

Bitnob requires a publicly reachable webhook URL. For local development, use `ngrok http 8000` (or Cloudflare Tunnel) and register the resulting URL in the Bitnob sandbox dashboard. Document this exact step in the README's "Local Development" section — this is not optional tooling, it is required to test the most important code path in the system.

---

## 13. Testing Strategy

### 13.1 What must have automated tests before this is considered "done"

| Area | Test type | Specifics |
|---|---|---|
| Reconciliation state machine | Unit tests | Every row in the allowed-transitions table (Section 4.2.1) needs a passing test; every forbidden transition needs a test asserting `InvalidStateTransitionError` is raised. |
| Tolerance calculation | Unit tests | Test `compute_tolerance_usd` at small invoice amounts (tolerance floor applies), large amounts (bps applies), and the boundary between them. |
| Underpayment flow | Integration test | Simulate a payment arriving short of expected, assert status becomes `partially_paid`, assert a top-up target quotes only the remaining balance. |
| Overpayment flow | Integration test | Simulate an overpayment, assert `overpayment_credits` row is created exactly once (not duplicated on a second reconcile() call). |
| Concurrent payment race | Integration test | Fire two simulated webhook events for the same invoice concurrently (use `asyncio.gather` against two calls into the reconciliation path), assert the final `amount_received_usd_equiv` correctly reflects both, not just one (this is the test that catches a missing row lock). |
| Webhook signature verification | Unit test | Valid signature passes; tampered body or wrong signature returns 401; missing signature header returns 401. |
| Webhook deduplication | Integration test | Same `event_id` delivered twice results in exactly one `Payment` row and one reconciliation run. |
| Late/expired payment honoring original quote | Integration test | Payment arrives after `payment_target.expires_at`; assert the USD-equivalent is computed from the original locked rate, not a freshly fetched one. |
| Bitnob client signing | Unit test | Verify the HMAC signature construction matches a known test vector once confirmed against real sandbox behavior (see Section 16). |

### 13.2 Mocking Bitnob in tests

`BitnobClient` must be injectable/mockable (constructor injection or a FastAPI dependency override) so that all tests above run without making real network calls. Build a `FakeBitnobClient` test double implementing the same interface, returning canned responses, for use throughout the test suite. Real sandbox calls are for manual/exploratory verification only, never part of the automated test suite.

---

## 14. Deployment

### 14.1 Processes to run

This system requires **four** independently running processes in production, not one:

1. FastAPI app (e.g. via `uvicorn`/`gunicorn` with uvicorn workers)
2. Celery worker
3. Celery beat (scheduler)
4. PostgreSQL + Redis (managed services recommended over self-hosting for a v1)

### 14.2 Suggested hosting

- App + Celery worker + Celery beat: any platform supporting long-running processes (Railway, Render, Fly.io) — avoid pure serverless (e.g. raw AWS Lambda) for the Celery worker/beat, since they need to run continuously, not on-demand.
- Postgres + Redis: managed instances from the same platform, or a dedicated provider (Neon/Supabase for Postgres, Upstash for Redis) if preferred.

### 14.3 Health checks

Expose `GET /health` returning DB connectivity and Redis connectivity status — required by most hosting platforms for process supervision, and useful for verifying the Celery broker connection is alive.

---

## 15. Build Order / Milestones (do this in order)

Each milestone should be working and manually verifiable before moving to the next. Do not parallelize across milestones — later ones depend on earlier ones being correct.

**Milestone 1 — Foundations**
Project scaffold per Section 3.2, Postgres + Alembic set up, `users` and `invoices` tables migrated, basic JWT auth (`/auth/register`, `/auth/login`, `/auth/me`) working end to end.

**Milestone 2 — Invoice CRUD, no payments yet**
`POST /invoices`, `GET /invoices`, `GET /invoices/{id}` working against the `draft` status only. No Bitnob integration yet. Verify with manual API calls (curl/Postman) or automated tests.

**Milestone 3 — Bitnob client + sandbox connectivity**
Build `BitnobClient`, confirm the `[CONFIRM]` items in Section 16 against a real sandbox account, get `GET /api/v1/wallets` returning 200. This milestone is "done" when you can make one successful authenticated call to Bitnob's sandbox from your codebase.

**Milestone 4 — Stablecoin payment target generation (start here, not BTC/Lightning)**
Implement `POST /public/invoices/{id}/payment-target?method=usdc` end to end: rate lock, Bitnob call, `payment_targets` row created, returned to caller. Stablecoins are the simplest rail to integrate first since there's no Lightning-node-specific quirks and no BTC confirmation-depth question yet.

**Milestone 5 — Webhook receiver + reconciliation (the core of the system)**
Build the full webhook receiver (Section 8), `ReconciliationService` (Section 6) with all unit tests from Section 13.1 passing, Celery worker wired up. Test end to end against the sandbox: generate a USDC payment target, send a real sandbox test payment (Bitnob sandbox should support simulated deposits — confirm this), watch the webhook arrive, watch the invoice transition to `paid`.

**Milestone 6 — Lightning and BTC on-chain**
Add the remaining two payment methods. By this point the reconciliation/webhook plumbing is proven, so this is mostly additional `BitnobClient` methods plus method-specific fields on `payment_targets`.

**Milestone 7 — PDF receipts + email**
Build the receipt template, `weasyprint` rendering, storage, and the `send_email` task. Verify a receipt is generated and emailed automatically after Milestone 5/6's flows reach `paid`.

**Milestone 8 — Reconciliation sweep + expiry job**
Add the two Celery beat jobs from Section 9.1/9.2. Verify the sweep job actually catches a payment when you deliberately disable the webhook (simulate a missed webhook) and confirm it self-heals within one sweep interval.

**Milestone 9 — Overpayment/underpayment UX support + dashboard endpoints**
`overpayment_credits` endpoints, top-up payment target logic (Section 6.7), `/invoices/{id}/resend`, `/invoices/{id}/cancel`.

**Milestone 10 — Hardening**
Rate limiting on public endpoints, full test suite from Section 13 passing, health check endpoint, `.env.example` finalized, README written covering local setup including the ngrok webhook step.

---

## 16. Open Questions / Things to Confirm Against Live Sandbox

These items were inferred from partial/fragmentary documentation review and must be verified against a real Bitnob sandbox account before being trusted in production code. Do not ship Milestone 3 until these are resolved.

1. **Auth scheme** — confirm whether the current Bitnob developer dashboard issues a simple Bearer API key or a CLIENT_ID/CLIENT_SECRET pair requiring HMAC-SHA256 request signing. The discovery material suggests both patterns appear somewhere in Bitnob's docs/examples; only one is likely current.
2. **Exact endpoint paths and field names** for: exchange rate lookup, stablecoin deposit address generation, and Lightning invoice creation response shape (what exactly comes back — is it `payment_request`, `paymentRequest`, `request`?).
3. **Exact webhook event type strings** for BTC on-chain receipt and Lightning payment confirmation (we have confirmed examples for stablecoin and payout/beneficiary/virtual-card events, but not BTC-onchain-received or lightning-invoice-paid specifically).
4. **Webhook payload field for the dedup key** — confirm whether it's consistently `event_id` across all event types, or whether older event types still only expose `id` (the discovery material shows both forms in different examples).
5. **Confirmation-depth requirements** — does Bitnob's webhook fire only once funds are "confirmed" by their own internal policy, or does it fire on first-seen (0-conf) with subsequent events for confirmation count increases? This determines whether this system needs its own confirmation-depth gating logic or can trust Bitnob's webhook as final.
6. **Sandbox test payment simulation** — confirm how to trigger a simulated incoming payment in the sandbox (the discovery material referenced a "Simulate Address Deposit" endpoint under Offramps — confirm if this or an equivalent exists for inbound stablecoin/BTC/Lightning testing).
7. **Stablecoin network support** — call `GET /api/v1/wallets/stable-coins-networks` early and confirm which networks (e.g. Tron, Base, Polygon) and which tokens (USDC vs USDT) are actually supported before finalizing any frontend copy or `payment_targets.network` enum values.
