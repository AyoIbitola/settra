# Backend PRD — Settra (Bitcoin & Stablecoin Invoicing Platform)

**Product name:** Settra
**Version:** 1.0
**Owner:** [Your name]
**Backend stack:** Python, FastAPI, PostgreSQL, Redis, Celery
**Payment rail:** Busha API (sandbox → production)
**Audience:** Engineering agent building this end-to-end from scratch

---

## How to use this document

This PRD is written to be handed directly to a coding agent (e.g. an Antigravity agent) as a build spec. It is organized so that each section is buildable in order, with explicit acceptance criteria. Do not skip ahead to a later phase before the acceptance criteria of the current phase are met — later phases assume earlier ones are working and tested.

Where a decision has been made (e.g. "use Postgres," "use HMAC-SHA256 + base64 for webhook verification"), build to that decision. Where a placeholder is marked `[CONFIRM]`, the agent must verify the actual value against Busha's live sandbox docs/response before hardcoding it, since some exact field names were inferred from partial documentation and need confirmation against a real sandbox call before being trusted in code.

---

## Table of Contents

1. Product Summary & Scope
2. System Architecture Overview
3. Tech Stack & Project Structure
4. Data Model (full schema)
5. Busha API Integration Layer
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

Freelancers create USD-denominated invoices. Clients pay those invoices using Bitcoin (on-chain) or a stablecoin (USDC/USDT), routed through the Busha API. The backend:

- Creates a Busha one-time, fixed-amount payment link per invoice, which carries a Busha-issued locked exchange rate
- Generates a payment request against that link (BTC address or stablecoin deposit address) at the moment a client opens the payment page
- Listens for Busha webhooks confirming receipt of funds
- Reconciles received amounts against expected amounts (handling underpayment, overpayment, and exact payment)
- Generates a PDF receipt with on-chain proof (tx hash) once an invoice reaches a paid state
- Exposes a freelancer-facing dashboard API and a public client-facing payment-status API

**Branch note:** this PRD was originally written against the Bitnob API. It has been rewritten to target Busha instead — see Section 5 for the integration layer and Section 16 for what's still unconfirmed against a live Busha sandbox. Lightning Network support has been explicitly cut from scope: Busha does not offer a Lightning product, and this is a deliberate decision, not a temporary gap.

### 1.2 What this system explicitly does NOT do (out of scope for v1)

- No custody of funds at any point — Busha holds funds; this backend only orchestrates and records state.
- No automatic refunds (see Section 6.4 — overpayment is handled via manual freelancer-initiated refund only).
- No payouts to freelancer bank accounts — this is a receiving-only system in v1. Busha's payout/transfer endpoints (which do support bank and mobile money payout) are not integrated in this phase.
- No multi-currency invoices beyond USD as the denominating currency (note: Busha itself is multi-fiat — NGN, KES, GHS, USD — but Settra's invoices are always USD-denominated regardless of what Busha supports underneath).
- No support for more than one stablecoin network per invoice at a time.
- **No Lightning Network support.** Settlement methods are limited to BTC on-chain, USDC, and USDT.

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
│              │  - BushaClient (bearer-token HTTP client) │                │
│              │  - ReceiptService                       │                │
│              └─────────────┬───────────────────────┘                │
└────────────────────────────┼──────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌──────────────┐ ┌────────────┐ ┌──────────────┐
      │  PostgreSQL   │ │   Redis     │ │  Busha API    │
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

### 2.2 Request flow — happy path (USDC payment, fully worked example)

1. Freelancer calls `POST /invoices` → invoice row created with `status=draft`, no payment target yet.
2. Freelancer shares `https://yourapp.com/pay/{invoice_id}` with client.
3. As part of invoice creation (or lazily, on first client visit — see Section 7.3.1 for the exact trigger), the backend calls Busha's `create_one_time_payment_link` with `quote_currency="USD"`, `quote_amount=invoice.amount_usd`, `target_currency="USDC"`. Busha returns a `link_id` and the link is stored on the invoice.
4. Client's browser calls `GET /public/invoices/{id}/payment-target?method=usdc`.
5. Backend checks: does this invoice already have a non-expired USDC payment request? If not:
   a. Call Busha `create_payment_request_for_link(link_id, customer_email)`.
   b. Busha's response includes a locked `rate` object (`type: "FIXED"`), a `pay_in` object with the deposit address/network/expiry, and `source_amount`/`target_amount`.
   c. Persist all of this onto a new `payment_target` row: `rate_locked_usd_to_crypto` from the rate object, `target_value` from `pay_in.address`, `network` from `pay_in.network`, `expires_at` from `pay_in.expires_at`.
6. Backend returns the deposit address + QR-renderable data + countdown expiry to the frontend.
7. Client sends USDC to the address via their own wallet/exchange.
8. Busha fires a webhook (`POST /webhooks/busha`) — first `payment_request.pending`, then `payment_request.processing`, then `payment_request.completed` as the payment progresses through Busha's own internal pipeline.
9. Webhook receiver verifies the `x-bu-signature` HMAC-SHA256 (base64-encoded) signature, deduplicates by event identity (see Section 8 for the exact dedup key, since Busha's payloads don't always expose a single canonical `event_id` field the way Section 4.5's schema assumes — confirm against Section 16), persists the raw event, enqueues `process_webhook_event` as a Celery task, returns `200` immediately.
10. Celery worker resolves `reference` (Busha echoes back the payment request's own ID as `reference`) to `invoice_id`, creates or updates a `Payment` row, runs `ReconciliationService.reconcile(invoice_id)` inside a DB transaction with row-level locking. Only the `payment_request.completed` event should drive a reconciliation state change that can move an invoice to `paid`/`partially_paid`/`overpaid` — treat `.pending` and `.processing` as informational/UI-status-only events, not reconciliation triggers (see Section 6 for why funds must actually be confirmed received before the ledger changes).
11. Reconciliation updates `invoice.status` per the state machine (Section 6).
12. If the new status is `paid` or `overpaid`, enqueue `generate_receipt`, which renders a PDF and enqueues `send_email` (to freelancer and client).
13. Client's frontend, which has been polling `GET /public/invoices/{id}/status` every 5s, sees `status=paid` and shows the confirmation screen.

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
| HTTP client (outbound to Busha) | `httpx` (async) | |
| Validation | Pydantic v2 | request/response schemas, and Busha payload schemas |
| Auth | `python-jose` (JWT) + `passlib[bcrypt]` | freelancer auth only; public endpoints have no auth |
| PDF generation | `weasyprint` | renders HTML/CSS to PDF without a headless browser dependency |
| Email | `httpx` call to Resend API (or equivalent) | keep this behind an `EmailService` interface so the provider can be swapped |
| Testing | `pytest` + `pytest-asyncio` + `httpx` test client | |
| Linting/formatting | `ruff` | |

### 3.2 Project structure

Build exactly this structure. Do not flatten it or merge modules — the separation matters for testability, especially isolating the Busha client behind an interface so it can be mocked in tests.

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
│   │   └── busha.py                 # schemas for Busha's request/response shapes
│   ├── routers/
│   │   ├── auth.py
│   │   ├── invoices.py              # authenticated freelancer endpoints
│   │   ├── public.py                # unauthenticated client-facing endpoints
│   │   └── webhooks.py
│   ├── services/
│   │   ├── invoice_service.py
│   │   ├── reconciliation_service.py
│   │   ├── receipt_service.py
│   │   ├── busha_client.py          # bearer-token HTTP client wrapping all Busha calls
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
│   ├── test_busha_client.py
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
| busha_reference | String, unique, not null | generated at creation, e.g. `INV_{uuid4 short}` — passed to Busha wherever a reference field is accepted, and used to correlate incoming webhooks back to this invoice (see Section 8 for the exact correlation mechanism, since Busha's payment-request objects use their own `id`/`reference` fields which echo back what you sent) |
| busha_link_id | String, nullable, unique when set | the Busha one-time payment link `id` created for this invoice (Section 5.2's `create_one_time_payment_link`) — nullable until the link is actually created, which may happen at invoice-creation time or lazily on first client visit depending on Milestone implementation order |
| amount_received_usd_equiv | Numeric(12,2), not null, default 0 | running total, in USD-equivalent at time of each payment's locked rate — see Section 6 for how this is computed |
| overpaid_amount_usd | Numeric(12,2), not null, default 0 | only non-zero when status = `overpaid` |
| due_date | Date, nullable | cosmetic only in v1 |
| created_at | TIMESTAMPTZ, not null, default now() | |
| updated_at | TIMESTAMPTZ, not null, default now(), onupdate now() | |

**Indexes:** `idx_invoices_user_id`, unique index on `busha_reference`, unique index on `busha_link_id` (where not null), index on `status` (used heavily by the reconciliation sweep job).

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

One invoice can have multiple payment targets over its lifetime (e.g., a fresh payment request generated after the first one expired, or two separate targets if the freelancer enabled both BTC and USDC and the client's frontend requested both). Each `payment_target` row corresponds to one Busha **payment request** created against the invoice's underlying payment link (Section 5.2).

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| invoice_id | UUID, FK → invoices.id, not null | |
| method | Enum: `btc_onchain`, `usdc`, `usdt` | no `lightning` value — Busha does not offer Lightning, see Section 1.1 |
| network | String, nullable | e.g. `BASE`, `TRX`, `BTC` — validate against the confirmed table in Section 5.3, do not accept free-text values |
| target_value | String, not null | the BTC/stablecoin deposit address returned in Busha's `pay_in.address` field |
| busha_payment_request_id | String, not null, unique | the Busha payment request `id` (e.g. `PAYR_...`) — this is the value Busha echoes back as `reference` on every webhook event for this specific payment attempt, and is the primary correlation key described in Section 8 |
| rate_locked_usd_to_crypto | Numeric(20,8), not null | extracted from Busha's `rate.rate` field at payment-request creation time — see Section 5.4 |
| amount_expected_crypto | Numeric(20,8), not null | extracted from Busha's `source_amount` field (or computed from `invoice.amount_usd` / `rate_locked_usd_to_crypto` if this is a top-up target — see 4.3.1) |
| busha_response_raw | JSONB, nullable | store the full raw Busha payment-request response for debugging/audit |
| expires_at | TIMESTAMPTZ, not null | extracted from Busha's `pay_in.expires_at` field |
| is_active | Boolean, not null, default true | set false once expired or superseded by a new target |
| created_at | TIMESTAMPTZ, not null, default now() | |

**Indexes:** `idx_payment_targets_invoice_id`, index on `(invoice_id, is_active)`, unique index on `busha_payment_request_id`.

#### 4.3.1 Top-up targets for partial payments

When an invoice is `partially_paid`, do not generate a whole new invoice. Generate a new `payment_target` row scoped to the **remaining balance only** (`invoice.amount_usd - invoice.amount_received_usd_equiv`), linked to the same `invoice_id`. This means creating a new Busha payment request against the *same* underlying `busha_link_id` (Busha's reusable-vs-one-time link distinction matters here — see Section 16 item 2 for what's still unconfirmed about creating a second payment request against an already-one-time link). This is what lets the client "pay the remaining balance" without restarting the whole flow, per the recommended UX pattern from Section 6.

### 4.4 `payments`

Append-only ledger of every confirmed receipt of funds against an invoice. Never update or delete rows here except to add `confirmations` as they increase for an already-recorded BTC payment (see note below).

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| invoice_id | UUID, FK → invoices.id, not null | |
| payment_target_id | UUID, FK → payment_targets.id, not null | which specific target this payment was received against |
| tx_hash | String, not null | the on-chain hash, from Busha's `pay_in.blockchain_hash` field (present once funds are detected — see Section 16 for confirmation that this field is populated at the `processing` stage, not only at `completed`) |
| amount_received_crypto | Numeric(20,8), not null | exact amount as reported by Busha (`source_amount` on the completed payment request) |
| amount_received_usd_equiv | Numeric(12,2), not null | computed using the *target's locked rate*, not a live rate, per Section 6.5 |
| method | Enum: `btc_onchain`, `usdc`, `usdt` | |
| network | String, nullable | |
| confirmations | Integer, not null, default 0 | [CONFIRM] whether Busha's webhook payloads expose a raw confirmation count at all, or whether `processing` → `completed` is the only granularity available — see Section 16. If Busha doesn't expose confirmation counts, this column can be set to 0/1 as a simple "unconfirmed/confirmed" flag rather than a true count, and the gating logic in Section 6 should key off `payment_request.completed` rather than a numeric threshold. |
| busha_payment_request_id | String, FK → payment_targets.busha_payment_request_id, not null | traceability back to the exact payment request that produced this row |
| received_at | TIMESTAMPTZ, not null | |
| created_at | TIMESTAMPTZ, not null, default now() | |

**Unique constraint:** `(tx_hash, invoice_id)` — prevents the same on-chain transaction from ever being recorded twice against the same invoice, which is a second layer of defense beyond webhook event deduplication.

**Note on confirmations:** for BTC on-chain payments, if Busha's webhooks do expose incrementing confirmation counts (confirm this against Section 16), do not insert a new `payments` row for each update — instead, update the existing row's `confirmations` field, keyed by `tx_hash`. Only the *first* sighting of a given `tx_hash` (or the `payment_request.completed` event, whichever model is confirmed correct) should trigger reconciliation logic for the underpaid/overpaid calculation; subsequent confirmation-count updates should not re-run the full reconciliation state machine.

### 4.5 `webhook_events`

| Column | Type | Notes |
|---|---|---|
| id | UUID, PK | |
| event_dedup_key | String, unique, not null | **[CONFIRM]** Busha's webhook payloads (as documented) do not expose a single, consistently-named top-level event identifier the way the original Bitnob-based design assumed. Build this as a composite key instead: `f"{data['id']}:{event_type}:{data.get('updated_at', data.get('created_at'))}"` — i.e., the underlying object's own ID, the event type, and its timestamp, concatenated. This means the same object reaching the same status twice (which shouldn't normally happen) is still deduplicated, while two *different* status transitions for the same object (e.g. `payment_request.pending` then `payment_request.completed`) are correctly treated as two distinct, both-meaningful events rather than colliding as duplicates. Revisit this if Busha's actual sandbox payloads turn out to expose a cleaner dedicated event ID field — confirm before committing to this composite-key approach. |
| event_type | String, not null | e.g. `payment_request.completed`, `transfer.funds_received` |
| raw_payload | JSONB, not null | full original payload, for audit/replay |
| signature_valid | Boolean, not null | record this even though invalid-signature events should be rejected before reaching this table in the happy path — useful for security audit logs if you choose to log-and-reject rather than just reject |
| processed_at | TIMESTAMPTZ, nullable | null until the Celery task finishes processing |
| processing_error | Text, nullable | populated if `process_webhook_event` raised |
| created_at | TIMESTAMPTZ, not null, default now() | |

**Unique constraint on `event_dedup_key` is the core deduplication mechanism** — the webhook receiver should attempt to insert this row inside a transaction and treat a unique-constraint violation as "already processed, ack and skip," not as an error to surface to Busha (still return 200).

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

## 5. Busha API Integration Layer

> **Branch note:** this section replaces the original Bitnob-based integration layer. Settra now uses Busha as its payment rail. Lightning is explicitly out of scope — Busha does not expose a Lightning product, and this is a deliberate scope cut, not a gap to fill later.

### 5.1 Authentication scheme — confirmed, no [CONFIRM] needed here

Busha issues two key types from the dashboard (Settings → Developer Tools → API Tokens):
- **Public key** — safe for frontend/client-side use, can initiate but not modify account state. Not used by this backend directly, but worth knowing about since the frontend PRD may reference it for any client-side Busha widget usage.
- **Secret key** — server-side only, full account access. This is what `BushaClient` uses. Never log it, never commit it, never send it to the frontend.

Auth is a simple bearer token, no request signing required for outbound calls:

```
Authorization: Bearer YOUR_SECRET_KEY
```

This is simpler than the original Bitnob-based design, which assumed HMAC request signing — that signing logic is no longer needed for outbound requests. (Signing still applies to *incoming webhooks* — see Section 8.)

### 5.2 `BushaClient` design

Build this as a single class wrapping all outbound Busha calls, replacing the old `BitnobClient`. No other part of the codebase should construct an HTTP request to Busha directly.

```python
# app/services/busha_client.py

import httpx
from app.config import settings

class BushaClient:
    def __init__(self):
        self.base_url = settings.BUSHA_BASE_URL  # https://api.sandbox.busha.so or production equivalent
        self.secret_key = settings.BUSHA_SECRET_KEY
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15.0,
            headers={
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
            },
        )

    async def _request(self, method: str, path: str, json_body: dict | None = None, params: dict | None = None) -> dict:
        response = await self._http.request(method, path, json=json_body, params=params)
        response.raise_for_status()
        return response.json()

    # --- Payment links (this is Settra's core "generate a payment target" call) ---

    async def create_one_time_payment_link(
        self,
        name: str,
        title: str,
        description: str,
        quote_amount: str,
        quote_currency: str,   # "USD" for Settra invoices
        target_currency: str,  # "BTC" | "USDC" | "USDT"
        customer_email: str,
    ) -> dict:
        return await self._request("POST", "/v1/payments/links", {
            "fixed": True,
            "one_time": True,
            "name": name,
            "title": title,
            "description": description,
            "quote_amount": quote_amount,
            "quote_currency": quote_currency,
            "target_currency": target_currency,
            "require_extra_info": [
                {"field_name": "email", "required": True}
            ],
        })

    async def get_payment_link(self, link_id: str) -> dict:
        return await self._request("GET", f"/v1/payments/links/{link_id}")

    async def create_payment_request_for_link(self, link_id: str, customer_email: str) -> dict:
        # Used when a client opens a payment link and needs an actual pay-in
        # target (address/expiry/rate) generated against it.
        return await self._request("POST", f"/v1/payments/links/{link_id}/requests", {
            "email": customer_email,
        })  # [CONFIRM] exact request body shape against live sandbox — see Section 16

    async def get_payment_request(self, request_id: str) -> dict:
        return await self._request("GET", f"/v1/payment-requests/{request_id}")

    async def list_payment_requests_for_link(self, link_id: str) -> dict:
        return await self._request("GET", f"/v1/payments/links/{link_id}/requests")

    # --- Currencies / supported networks ---

    async def get_supported_currencies(self) -> dict:
        return await self._request("GET", "/v1/currencies")

    async def get_currency_details(self, code: str) -> dict:
        return await self._request("GET", f"/v1/currencies/{code}")

    # --- Transactions (used by the reconciliation sweep, Section 9.2) ---

    async def list_transactions(self, reference: str | None = None) -> dict:
        params = {"reference": reference} if reference else None
        return await self._request("GET", "/v1/transactions", params=params)

    async def get_transaction(self, transaction_id: str) -> dict:
        return await self._request("GET", f"/v1/transactions/{transaction_id}")
```

### 5.3 Supported settlement currencies and networks — confirmed, use exactly these

Do not invent or assume network names beyond this confirmed list (from Busha's own currency reference, checked directly against their docs):

| Crypto currency | Confirmed networks for deposit |
|---|---|
| BTC | BTC (on-chain only) |
| USDC | BASE, ETH (ERC20), TRX (TRC20), XLM, SOL |
| USDT | BSC (BEP20), ETH (ERC20), TRX (TRC20), Plasma (XPL), SOL |

Settra's `PaymentMethod` enum (Section 4.3) should be `btc_onchain`, `usdc`, `usdt` — **no `lightning` value**. Wherever the original PRD or the frontend spec references Lightning, treat it as removed. The `network` field on `payment_targets` should be validated against this table (e.g. reject an attempt to quote USDC on a network not in this list) rather than left as a free-text field with no validation.

**Recommendation for v1: default to a single network per stablecoin to keep the UI simple** — e.g. USDC on BASE, USDT on TRX (Tron) — since Tron has the lowest transaction fees of the supported options, which matters for smaller invoice amounts. Exposing all five networks per stablecoin in the UI is unnecessary complexity for v1; this can be revisited later. Document this choice in `config.py` as a `DEFAULT_NETWORKS` mapping rather than hardcoding it inline anywhere.

### 5.4 Rate locking — Busha does this for you

This is a meaningful simplification from the original Bitnob-based design. Busha's payment link/request objects already return a `rate` object with `type: "FIXED"` at creation time, e.g.:

```json
"rate": {
  "product": "BTCNGN",
  "rate": "136593125.15",
  "side": "sell",
  "type": "FIXED",
  "source_currency": "BTC",
  "target_currency": "NGN"
}
```

Settra still maintains its own `payment_targets.rate_locked_usd_to_crypto` column (Section 4.3) as the source of truth for Settra's own ledger math — **do not rely on re-fetching this from Busha later**, store it locally the moment the payment request is created, exactly as the original design intended. The difference from the Bitnob-based plan is that you no longer need to call a separate exchange-rate endpoint and lock it yourself — extract the locked rate directly from the `create_payment_request_for_link` response and persist it.

### 5.5 Error handling contract

Unchanged in principle from the original design:
- `httpx.HTTPStatusError` on non-2xx — caught at the service layer, never in routers, translated into a domain-specific exception. Busha's error shape is documented and consistent: `{"error": {"name": "...", "message": "..."}}`, optionally with `schema` or `fields` detail — parse this shape specifically when building the translated exception message, rather than just dumping the raw body.
- Retry policy: 2 retries with exponential backoff, only for idempotent GET requests (get payment link, get transaction, list transactions). Never automatically retry `create_one_time_payment_link` or `create_payment_request_for_link` — a duplicate call creates a duplicate, separately-billed payment link/request on Busha's side, which is a real-money mistake, not a safe retry.
- Respect the documented rate limit: Busha returns an `x-rate-limit` header (requests per rolling minute, default 100/min if absent) and a `429` when exceeded. `BushaClient` should catch `429` specifically and raise a distinct `RateLimitedError` so the service layer can decide whether to queue/retry-later rather than treating it like a generic failure.

### 5.6 Caching

Unchanged in principle: short-TTL Redis caching is no longer needed for a separate exchange-rate lookup (Section 5.4 removes that call entirely), but is still useful for caching `get_supported_currencies` results (these change rarely) to avoid refetching the network-support table on every invoice creation.

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
| POST | `/invoices` | Create invoice. Body: `client_name`, `client_email`, `description`, `amount_usd`, `due_date` (optional). Creates row with `status=draft`. Does NOT call Busha — payment targets are generated lazily (see 2.2). |
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
| GET | `/public/invoices/{id}/payment-methods` | Returns which methods the freelancer enabled (`btc_onchain`, `usdc`, `usdt`) so the frontend can render method-selection cards. No `lightning` value — see Section 1.1. |
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
   - If found: return it directly (no new Busha call).
3. If not found (none exists, or existing one expired):
   a. If invoice.status == draft: transition to pending (first target ever generated).
   b. If invoice.busha_link_id is not yet set: call BushaClient.create_one_time_payment_link()
      (Section 5.2) with quote_currency="USD", quote_amount=invoice.amount_usd,
      target_currency mapped from the requested method (BTC/USDC/USDT). Persist the
      returned link id onto invoice.busha_link_id.
   c. Determine the amount to quote:
      - If invoice.status in {pending, draft, expired} with zero payments received:
        quote the full invoice.amount_usd.
      - If invoice.status == partially_paid: quote only the remaining balance
        (invoice.amount_usd - invoice.amount_received_usd_equiv), per Section 6.7.
        [CONFIRM] whether Busha's one-time link type supports a second payment
        request at a different amount than the original — see Section 16 item 2.
        If not supported, a second payment link may need to be created for the
        remaining balance instead of reusing busha_link_id.
   d. Call BushaClient.create_payment_request_for_link(link_id, customer_email).
      Extract rate_locked_usd_to_crypto from the response's rate.rate field,
      target_value from pay_in.address, network from pay_in.network,
      expires_at from pay_in.expires_at, amount_expected_crypto from source_amount.
   e. Mark any prior payment_target for this invoice+method as is_active=false.
   f. Persist new payment_target, commit.
4. Return payment_target details: target_value (address), amount_expected_crypto,
   rate_locked_usd_to_crypto, expires_at.
```

### 7.4 Webhooks

| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/busha` | Receives all Busha webhook events. See Section 8 for full spec. |

---

## 8. Webhook Receiver — Detailed Spec

### 8.1 Endpoint implementation

```python
# app/routers/webhooks.py

import hmac
import hashlib
import base64
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from app.db import get_session
from app.models.webhook_event import WebhookEvent
from app.workers.tasks import process_webhook_event
from app.config import settings

router = APIRouter()

@router.post("/webhooks/busha")
async def busha_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-bu-signature", "")

    # Busha's documented scheme: HMAC-SHA256 of the raw request body,
    # using the webhook secret as the key, base64-encoded (NOT hex).
    mac = hmac.new(
        settings.BUSHA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    )
    expected = base64.b64encode(mac.digest()).decode()

    # Constant-time comparison — never use `==` for signature checks.
    if not hmac.compare_digest(expected, signature):
        # Return 401, but DO NOT include any detail about what was expected.
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = payload.get("event")
    data = payload.get("data", {})

    # Busha's payloads do not expose a single dedicated "event_id" field
    # the way the original Bitnob-based design assumed. Build a composite
    # dedup key from the underlying object's own id, the event type, and
    # its timestamp — see Section 4.5 for the full rationale, and Section 16
    # for what to re-confirm if Busha's actual sandbox payloads differ.
    object_id = data.get("id")
    timestamp = data.get("updated_at") or data.get("created_at")

    if not object_id:
        # Cannot dedupe without an identifier — log loudly, still ack 200
        # so Busha doesn't retry indefinitely, but flag for manual review.
        await log_malformed_webhook(payload)
        return {"status": "ok"}

    dedup_key = f"{object_id}:{event_type}:{timestamp}"

    async with get_session() as db:
        existing = await db.execute(
            select(WebhookEvent).where(WebhookEvent.event_dedup_key == dedup_key)
        )
        if existing.scalar_one_or_none() is not None:
            return {"status": "ok"}  # already processed, ack without reprocessing

        webhook_row = WebhookEvent(
            event_dedup_key=dedup_key,
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

Read `raw_body` as bytes and compute the HMAC over the **exact raw bytes received**, not over a re-serialized JSON object. If you parse JSON first and re-`json.dumps()` it to compute the signature, differences in key ordering or whitespace will produce a different signature than what Busha actually signed, causing valid webhooks to be rejected. Always verify against the raw request body bytes. Note the encoding specifically: Busha's documented Go example base64-encodes the HMAC digest, not hex — get this wrong and every signature check fails silently against otherwise-valid webhooks.

### 8.3 Always return 200 quickly

The handler above does the minimum synchronous work (verify signature, dedupe-check, persist raw event) and delegates everything else — resolving the invoice, updating the ledger, generating receipts — to a Celery task. A slow handler risks Busha's request timing out and triggering unnecessary retries even though the event already succeeded on your end. **[CONFIRM]** Busha's documentation (unlike Bitnob's, which explicitly stated a 3-retry policy) does not specify an exact retry count for non-200 responses in what's been reviewed so far — confirm this against the live dashboard/docs before relying on any specific retry-count assumption, but the principle of returning 200 fast holds regardless.

### 8.4 Event routing inside the Celery task

Route on the **payment request** lifecycle events primarily, since that's what corresponds to a client paying a Settra invoice (see Section 2.2's worked example). Busha's broader `transfer.*` events matter mostly for the reconciliation sweep (Section 9.2) and for any future payout features, not for the core invoice-payment flow.

```python
# app/workers/tasks.py

EVENT_HANDLERS = {
    "payment_request.pending": handle_payment_request_pending,        # informational only, no reconciliation
    "payment_request.processing": handle_payment_request_processing,  # informational only, no reconciliation
    "payment_request.completed": handle_payment_request_completed,    # triggers reconciliation
    "payment_request.expired": handle_payment_request_expired,
    "payment_request.failed": handle_payment_request_failed,
    "payment_request.cancelled": handle_payment_request_cancelled,
}

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_webhook_event(self, webhook_event_id: str):
    try:
        # load webhook_event row, dispatch to EVENT_HANDLERS[event_type],
        # unrecognized event types (e.g. transfer.* or customer.* events not
        # relevant to invoice payment) should be acknowledged and ignored,
        # not treated as errors.
        #
        # handle_payment_request_completed is responsible for:
        #   1. resolving `reference` from the payload's data.reference field
        #      to invoice_id, via payment_targets.busha_payment_request_id
        #   2. upserting a Payment row (insert if new tx_hash from
        #      data.pay_in.blockchain_hash; update confirmations if already seen
        #      and Busha exposes a confirmation count — see Section 16)
        #   3. calling ReconciliationService.reconcile(invoice_id) inside a
        #      locked transaction
        #   4. if new status in {paid, partially_paid, overpaid}, enqueue
        #      generate_receipt.delay(invoice_id)
        #
        # handle_payment_request_pending / _processing should update the
        # payment_target's cached status for display purposes only — they
        # must NOT call ReconciliationService, since funds have not yet
        # been confirmed received (see Section 6 for why this distinction
        # matters: reconciliation changes the ledger, and the ledger should
        # only change once Busha confirms completion).
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

### 9.2 `reconciliation_sweep` — the fallback Busha explicitly recommends

Busha's own webhook documentation explicitly states that webhooks are the recommended approach over polling, but also exposes a `GET /v1/transactions` (and `GET /v1/payments/links/{id}/requests`) endpoint specifically so a polling fallback is possible if webhook delivery fails. Implement this as:

```python
@celery_app.task
def reconciliation_sweep():
    """
    Runs every 5 minutes. For every invoice in {pending, partially_paid}
    that has at least one active, non-expired payment_target, call
    BushaClient.list_payment_requests_for_link(invoice.busha_link_id)
    and compare against what's already recorded in `payments`.
    If Busha shows a payment request with status "completed" that isn't
    present locally (e.g. webhook was lost), insert the payment and run
    reconciliation — using the exact same ReconciliationService code path
    the webhook handler uses.
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

- HMAC-SHA256 (base64-encoded) signature verification on every incoming webhook, as specified in Section 8 — non-negotiable, this is the only thing standing between your invoice ledger and anyone who finds your webhook URL.
- Store `BUSHA_WEBHOOK_SECRET` and `BUSHA_SECRET_KEY` only in environment variables / a secrets manager, never in source control. Add both to `.gitignore`'d `.env`, document required vars in `.env.example` with placeholder values only.
- Webhook endpoint should not be discoverable/guessable beyond its fixed path — Busha will need the exact URL registered in their dashboard (Settings → Developer Tools → Webhooks), so this is inherently a fixed, known endpoint; security here rests entirely on signature verification, not obscurity.

### 10.4 Secrets and key rotation

Per Busha's own documented guidance: the secret key is shown only once at creation time in the dashboard and must be copied immediately; it can be reset/regenerated from the dashboard if ever suspected compromised. The public key (safe for any client-side use) and secret key (server-side only, full account access) are distinct — never use the secret key anywhere the frontend can see it, and never use the public key for this backend's server-to-server calls since it cannot perform the mutating operations Settra needs (creating payment links/requests). Document the rotation procedure in the README even if not automated in v1.

---

## 11. PDF Receipt Generation

### 11.1 Trigger

`generate_receipt` Celery task, enqueued whenever `ReconciliationService.reconcile()` produces a status of `paid`, `partially_paid` (yes — generate an interim receipt showing partial payment, since the client may want proof of what they've paid so far), or `overpaid`.

### 11.2 Implementation

- Use `weasyprint` to render `app/templates/receipt.html` (a Jinja2 template) to PDF. This avoids a headless-browser dependency (no Puppeteer/Playwright needed in the Python stack).
- Template must include: freelancer business name, client name, invoice description, amount paid (crypto amount and USD-equivalent), payment method, tx hash, a block-explorer link (construct this based on `method`/`network` — e.g. mempool.space for BTC, the relevant chain explorer for stablecoins), timestamp, and invoice reference number.
- **Branding hierarchy on the receipt:** the freelancer's business name is the primary identity at the top of the receipt — this is their invoice, issued to their client. "Settra" appears only as a small, quiet "Receipt generated via Settra" line in the footer, matching the frontend's visual design system (dark background, monospace hash treatment per the frontend PRD's Section 8.6 `<ReceiptCard>` spec) but never competing with the freelancer's own business identity for primary visual weight.
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

# Busha
BUSHA_BASE_URL=https://api.sandbox.busha.so
BUSHA_SECRET_KEY=
BUSHA_WEBHOOK_SECRET=

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

Busha's auth model is simpler than the original Bitnob-based plan assumed: there is no shared client ID that carries across environments — sandbox and production are entirely separate Busha accounts with their own independently-issued secret keys (and the base URL itself differs: `api.sandbox.busha.so` vs. the production API host — **[CONFIRM]** the exact production base URL from the live dashboard once a production account exists, since only the sandbox host has been directly confirmed against documentation so far). Build `config.py` so switching `ENVIRONMENT`, `BUSHA_BASE_URL`, and `BUSHA_SECRET_KEY` (plus a separately-registered `BUSHA_WEBHOOK_SECRET` for the production webhook) is the *entire* cutover procedure — no code branches on environment beyond config loading.

### 12.3 Local webhook testing

Busha requires a publicly reachable webhook URL — their own documentation explicitly states that localhost URLs will not work. For local development, use `ngrok http 8000` (or Cloudflare Tunnel) and register the resulting URL under Settings → Developer Tools → Webhooks in the Busha sandbox dashboard. Busha's docs also mention webhook.site as a quick way to inspect raw payloads during initial exploration, before wiring up real signature verification — useful for confirming the actual shape of `payment_request.*` events against Section 16's open questions, but switch to your own ngrok-tunneled endpoint once you're testing real signature verification and reconciliation logic, since webhook.site cannot run your code. Document the ngrok step in the README's "Local Development" section — this is not optional tooling, it is required to test the most important code path in the system.

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
| Webhook deduplication | Integration test | Same dedup key (object id + event type + timestamp, per Section 4.5) delivered twice results in exactly one `Payment` row and one reconciliation run. |
| Late/expired payment honoring original quote | Integration test | Payment arrives after `payment_target.expires_at`; assert the USD-equivalent is computed from the original locked rate, not a freshly fetched one. |
| Busha webhook signature verification | Unit test | Verify the HMAC-SHA256 + base64 construction matches a known test vector built from a sample raw body and secret, confirming the base64 (not hex) encoding specifically — this is the detail most likely to be silently wrong if copied from a different provider's pattern. |

### 13.2 Mocking Busha in tests

`BushaClient` must be injectable/mockable (constructor injection or a FastAPI dependency override) so that all tests above run without making real network calls. Build a `FakeBushaClient` test double implementing the same interface, returning canned responses shaped like the real documented payment-link/payment-request/webhook payloads (Section 5.2, Section 8.4), for use throughout the test suite. Real sandbox calls are for manual/exploratory verification only, never part of the automated test suite.

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
`POST /invoices`, `GET /invoices`, `GET /invoices/{id}` working against the `draft` status only. No Busha integration yet. Verify with manual API calls (curl/Postman) or automated tests.

**Milestone 3 — Busha client + sandbox connectivity**
Build `BushaClient`, confirm the `[CONFIRM]` items in Section 16 against a real sandbox account, get `GET /v1/currencies` returning 200 using a bearer-token secret key. This milestone is "done" when you can make one successful authenticated call to Busha's sandbox from your codebase.

**Milestone 4 — Stablecoin payment target generation (start here, not BTC)**
Implement `POST /public/invoices/{id}/payment-target?method=usdc` end to end: create the one-time payment link, create a payment request against it, extract and store the locked rate, `payment_targets` row created, returned to caller. Stablecoins are the simplest rail to integrate first since BTC's confirmation-depth behavior on Busha's side is still an open question (Section 16).

**Milestone 5 — Webhook receiver + reconciliation (the core of the system)**
Build the full webhook receiver (Section 8), `ReconciliationService` (Section 6) with all unit tests from Section 13.1 passing, Celery worker wired up. Test end to end against the sandbox: generate a USDC payment target, send a real sandbox test payment, watch the `payment_request.pending` → `payment_request.processing` → `payment_request.completed` webhooks arrive in sequence, watch the invoice transition to `paid` only on the `.completed` event.

**Milestone 6 — BTC on-chain**
Add the remaining payment method. By this point the reconciliation/webhook plumbing is proven, so this is mostly additional `BushaClient` target-currency handling plus method-specific fields on `payment_targets`. There is no Lightning milestone — it has been cut from scope entirely (Section 1.1).

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

This branch's integration layer (Section 5) is grounded in Busha's published documentation, which is more concretely specified than the original Bitnob-based plan was — auth, payment-link creation, and webhook signature verification are all documented with real example request/response bodies, not inferred. The items below are the genuine remaining gaps: details not fully covered in the documentation reviewed, that must be verified against a real Busha sandbox account before being trusted in production code. Do not ship Milestone 3 until item 1 is resolved, and do not ship Milestone 5 until items 2–5 are resolved.

1. **`create_payment_request_for_link` exact request/response shape** — Section 5.2's `create_payment_request_for_link` method body was constructed by inference from the documented payment-link and webhook-event examples (which show the *result* of a payment request, not the exact endpoint/body used to create one against an existing link). Confirm the exact path, required fields, and response shape against a live sandbox call before relying on it.
2. **Top-up requests against a `one_time: true` link** — Section 4.3.1 and 7.3.1 assume a second payment request can be created against the same one-time link for a remaining balance after a partial payment. Confirm whether Busha's one-time link type actually permits a second payment request once the first is marked inactive/used, or whether a fresh link must be created for the remaining balance instead. If a fresh link is required, `invoices.busha_link_id` may need to become a one-to-many relationship (a link per amount quoted) rather than the one-to-one assumed in the current schema.
3. **Webhook dedup key field** — confirmed: Busha's documented webhook payloads do not expose one consistent top-level event identifier across all event types the way the original Bitnob-based design assumed. Section 4.5 and 8.1 already build around a composite key (object id + event type + timestamp) instead of a single field — confirm this composite approach actually produces unique, stable keys against real sandbox payloads, and revisit if a cleaner dedicated field turns out to exist that wasn't visible in the documentation reviewed.
4. **Confirmation-count granularity for BTC on-chain payments** — confirm whether Busha's `payment_request.processing` → `payment_request.completed` transition is the only granularity exposed for BTC (i.e., no raw confirmation-count field at all), or whether intermediate confirmation updates are also sent. This determines whether Section 4.4's `confirmations` column should be a true count or a simple 0/1 completion flag (the PRD currently assumes it may need to be the latter — confirm before building confirmation-depth gating logic that won't have data to act on).
5. **Sandbox test payment simulation** — confirm how to trigger a simulated incoming BTC/USDC/USDT payment against a sandbox payment request, so Milestone 5's end-to-end test (generate target → simulate payment → watch webhook → watch reconciliation) can actually be executed without real funds. Busha's docs mention test addresses for off-ramp operations specifically; confirm whether an equivalent exists for inbound payment-request testing, or whether sandbox payment requests settle automatically/manually in some other documented way.
6. **Production base URL** — only the sandbox host (`api.sandbox.busha.so`) was directly confirmed in the documentation reviewed. Confirm the production API host from the live dashboard once a production Busha business account exists and is approved (Busha's onboarding requires KYB/business verification before production API access is granted — budget time for this in any real launch timeline, it is not instant).
7. **Rate limit behavior in practice** — Section 5.5 assumes a default of 100 requests/minute if the `x-rate-limit` header is absent. Confirm this default and the actual per-endpoint limits returned for the specific endpoints Settra calls most (payment link/request creation, transaction listing for the reconciliation sweep), since the sweep job's polling frequency (Section 9.2) should stay comfortably under whatever the real limit turns out to be.
