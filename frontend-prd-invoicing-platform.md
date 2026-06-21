# Frontend PRD — Settra (Bitcoin & Stablecoin Invoicing Platform)

**Product name:** Settra
**Tagline:** "Invoice in dollars. Get paid in crypto. Reconcile automatically."
**Version:** 1.0
**Stack:** Vite + React + TypeScript + Tailwind CSS
**Companion document:** `PRD.md` (backend spec) — this document assumes that API contract and references it directly. Do not invent endpoint shapes that contradict it.
**Audience:** Engineering agent building this end-to-end from scratch

---

## How to use this document

This is a build spec for a coding agent, not a mood board. Every visual decision below (palette, type, motion) is a decision already made — do not "explore alternatives" or substitute a different font/palette because it seems easier to source. Where something is explicitly left to your judgment, it says so. Everywhere else, build exactly what's specified.

The backend is not deployed yet. Build against the documented API contract in Section 4 (mirrored from the backend PRD), behind a single API client module that can be pointed at a real backend later by changing one base URL. Use a mock data layer (Section 4.5) so every screen is fully interactive and demoable before the real backend exists.

---

## Table of Contents

1. Product Scope & Site Map
2. Design System (palette, type, tokens)
3. Motion System (animation library choice, principles, the signature animation)
4. API Integration Layer & Mocking Strategy
5. Marketing Site — Page-by-Page Spec
6. Freelancer Dashboard — Page-by-Page Spec
7. Public Client Payment Page — Page-by-Page Spec
8. Component Library
9. Project Structure
10. Responsive & Accessibility Requirements
11. Build Order / Milestones
12. Open Questions / Things to Confirm

---

## 1. Product Scope & Site Map

### 1.1 Three distinct surfaces, one design system

This is not one app — it's three surfaces sharing a single visual language, each with a different emotional register:

| Surface | Audience | Tone | Auth |
|---|---|---|---|
| Marketing site | Prospective freelancers, evaluators (e.g. Bitnob themselves) | Cinematic, confident, the full design system at full intensity | None |
| Freelancer dashboard | Logged-in freelancers, used daily | Same palette, quieter execution — a tool, not a pitch | JWT-authenticated |
| Public payment page | Clients paying an invoice, often first-time crypto users, often on mobile | Calm, reassuring, the "proof" animation is functional, not decorative | None (secured by unguessable invoice UUID) |

### 1.2 Full site map

```
Marketing (public)
├── /                      Landing page — hero animation, how it works, receipt showcase
├── /pricing               (stub acceptable for v1 — see Milestone notes)
├── /docs                  (stub acceptable for v1)
├── /login
└── /signup

Dashboard (authenticated)
├── /dashboard                          Overview: outstanding total, paid this month, flagged overpayments
├── /dashboard/invoices                 List view, filterable by status
├── /dashboard/invoices/new             Creation form
├── /dashboard/invoices/:id             Detail view — status, targets, payment ledger, receipt
├── /dashboard/overpayments             Aging queue (PRD Section 4.6)
└── /dashboard/settings                 Business name, enabled payment methods, account

Public payment page (no auth, unguessable UUID)
└── /pay/:invoiceId                     Method selection → payment screen → confirmation → receipt
```

### 1.3 What this PRD does NOT cover

- The actual backend implementation (see `PRD.md`).
- Payment-provider-specific wallet integrations beyond rendering what the backend returns (QR codes, BOLT11 strings, addresses) — this frontend never talks to Bitnob directly, only to your own backend.
- A full docs/pricing CMS — these routes can be simple static pages in v1, the design system still applies but no special animation budget goes here.

---

## 2. Design System

### 2.1 Why these specific choices (read before substituting anything)

The most common tell of an AI-generated or templated design is the typeface pairing: Inter or a generic geometric sans for everything, no display/body/mono distinction, no real personality in the headline type. This system deliberately avoids that. Do not substitute Inter for the display role under any circumstance — Inter is used here only for body copy, where its neutrality is correct, not for headlines, where it would flatten the whole design back into the generic default.

### 2.2 Color palette — exact tokens

Define these as CSS custom properties in `:root` and as Tailwind theme extensions. Use the token names below verbatim in code and in Tailwind config so there's one vocabulary across design, code, and this document.

```css
:root {
  --color-ink:        #0A0A0B;  /* primary background — near-black, slightly warm, never pure #000 */
  --color-ink-raised:  #121316;  /* panel/card surfaces in the dashboard — one step lighter than ink */
  --color-line:        #1E2024;  /* hairline borders, dividers — barely-there separation */
  --color-white:       #F5F5F4;  /* headline text, primary text on dark */
  --color-silver:       #C8CDD3;  /* body text, secondary text, line art on dark */
  --color-silver-dim:   #6B6F76;  /* tertiary text, placeholders, disabled states */
  --color-signal:       #7CFF9B;  /* CONFIRMED/PAID state ONLY — see 2.2.1 */
  --color-signal-dim:   #2A4A33;  /* signal color at low opacity, for subtle backgrounds behind paid badges */
  --color-amber:         #E8A33D;  /* PENDING/AWAITING state ONLY — see 2.2.1 */
  --color-amber-dim:     #4A3A20;  /* amber at low opacity, for subtle backgrounds behind pending badges */
  --color-danger:        #FF6B6B;  /* errors, overpaid-flag, destructive actions only */
}
```

#### 2.2.1 The two-color status rule (non-negotiable)

`--color-signal` (green) and `--color-amber` (amber) are the only saturated colors in the entire system, and each has exactly one meaning, everywhere, with no exceptions:

- **Signal green** = payment confirmed / paid / success. Never used as a generic "positive" UI color (e.g. never used for a generic "Save" button, never used for a marketing CTA outside the context of an actual paid/confirmed state).
- **Amber** = awaiting / pending / countdown running. Never used for warnings unrelated to payment timing.
- **Danger red** = reserved for actual errors and the overpaid-flag state, used sparingly.

If a component needs a "primary action" color that isn't tied to a payment state (e.g. the "Get started" button on the marketing site, the "Create invoice" button in the dashboard), use `--color-white` text on a `--color-ink-raised` or bordered-ghost button, NOT signal green. This is what keeps green meaningful — by the time a user sees green anywhere in this product, they should instantly know money has been confirmed, with zero ambiguity. Violating this rule is the single fastest way to make the product feel cheaper than it is.

### 2.3 Typography

| Role | Typeface | Where it's used | Notes |
|---|---|---|---|
| Display | **General Sans** (Fontshare, free, self-hostable) | Hero headlines, section titles, large dashboard numbers (e.g. "$12,400 outstanding") | Tight letter-spacing (-0.02em to -0.03em at large sizes), weight 600–700 only. This is the typeface that gives the product personality — it has slightly distinctive letterforms (notice the 'a' and 'g') that a generic geometric sans lacks, which is exactly why it reads as designed rather than default. |
| Body | **Inter** | Paragraph copy, form labels, table cells, nav links | Weight 400–500. Inter is correct here precisely because body text should be neutral and highly legible — the personality budget is spent on Display and Mono, not here. |
| Monospace / data | **Berkeley Mono** if licensed, otherwise **JetBrains Mono** (free, self-hostable) as fallback | Transaction hashes, invoice references, BOLT11 strings, wallet addresses, crypto amounts (e.g. "0.00071 BTC"), countdown timers | This is a functional choice, not decorative: monospace makes hashes and addresses scannable and character-distinguishable (critical so a 0 isn't confused with an O, a 1 with an l). Every appearance of monospace text on this site signals "this is a real, verifiable data string" — train the user to trust that visual cue. |

Load via `@font-face` with self-hosted files (Fontshare and JetBrains Mono both permit this) — do not rely on a CDN `<link>` to Google Fonts for General Sans (it isn't on Google Fonts) and prefer self-hosting JetBrains Mono too, for performance and to avoid a render-blocking third-party request on the hero page specifically.

### 2.4 Type scale

```
--text-display-xl:  clamp(2.75rem, 6vw, 5.5rem);   /* hero headline only */
--text-display-lg:  clamp(2rem, 4vw, 3.25rem);     /* section titles */
--text-display-md:  1.75rem;                        /* dashboard big numbers, card titles */
--text-body-lg:      1.125rem;                       /* hero subhead, lead paragraphs */
--text-body:          1rem;                           /* default body */
--text-body-sm:       0.875rem;                       /* secondary text, captions */
--text-mono-lg:        1.125rem;                       /* large hash/amount display, e.g. receipt hero */
--text-mono:            0.9375rem;                      /* table cells, inline hashes */
--text-mono-sm:         0.8125rem;                      /* compact contexts, list rows */
```

Line height: 1.1 for all display sizes, 1.5 for body, 1.4 for mono (mono needs slightly more breathing room since monospace characters read denser).

### 2.5 Spacing, radius, elevation

- Spacing scale: standard Tailwind scale (4px base unit), no customization needed — don't reinvent this.
- Border radius: `--radius-sm: 6px` (badges, small buttons), `--radius-md: 12px` (cards, inputs), `--radius-lg: 20px` (large panels, the hero invoice card). Avoid `radius: 0` (too brutalist for this brief) and avoid fully-rounded "pill everything" (too soft) — the 6/12/20 system reads as considered and matches the "glossy" quality requested, since mid-radius corners catch the gradient/glow treatment in 2.6 better than sharp corners do.
- Elevation: this is a dark UI, so elevation is communicated via subtle background lightness steps (`--color-ink` → `--color-ink-raised`) plus a 1px `--color-line` border, NOT drop shadows (shadows barely read on near-black backgrounds). Reserve a soft glow (a blurred box-shadow using `--color-signal` or `--color-amber` at low opacity) specifically for the active/pulsing payment-target card on the public pay page — this is the one place a glow effect is earned, because it's communicating "this is alive and listening," not just decorating a panel.

### 2.6 The "glossy" quality — how to actually achieve it

"Glossy" on a near-black background comes from three specific techniques, not from gradients everywhere:

1. **A very subtle top-edge highlight** on raised panels: a 1px inset border in `--color-line` at the top, slightly lighter than the side/bottom borders, simulating a light source from above. This alone does most of the "glossy panel" work.
2. **A faint radial gradient glow behind the hero invoice card** — `--color-signal` or `--color-amber` at ~8% opacity, large blur radius, positioned behind the card, never as a background fill of a whole section.
3. **Specular highlight on the QR code container on the pay page** — a thin diagonal light-catching gradient line that sweeps across on load (a one-time animation, not a loop) — this is a classic "premium hardware product page" technique (think Apple product pages) applied to a payment QR, which is exactly the unexpected, considered touch that sells "glossy."

Do not use glass-morphism (blurred translucent panels) — it's overused and will read as templated. The glossy quality here comes from light implied by gradients and edges, not from blur.

---

## 3. Motion System

### 3.1 Animation library — decide using this criteria, then commit

You are choosing between **Framer Motion** and **GSAP**. Don't pick arbitrarily — reason through this:

- **Framer Motion** is the better fit for React-idiomatic, state-driven UI animation: component enter/exit transitions, the dashboard's micro-interactions (hover states, status badge transitions, list item reordering), and anything driven by React state changes (e.g. "this invoice just became `paid`, animate the badge"). It integrates with React's render cycle naturally, which matters a lot for the dashboard and pay-page surfaces where animation is tightly coupled to data/state.
- **GSAP** is the better fit for the hero's choreographed, timeline-based sequence (Section 3.3) where multiple elements need precise, sequenced control independent of component re-renders — it's the standard tool for this exact kind of "cinematic marketing site" sequence and has better scroll-trigger and timeline-scrubbing primitives.

**Recommendation, unless you find a concrete blocker while building: use both, scoped to where each is stronger.** Use GSAP specifically for the hero sequence on the landing page (Section 3.3) and any scroll-triggered marketing-site reveals (Section 5). Use Framer Motion for everything inside the React component tree that's state-driven: dashboard transitions, status badge changes, the pay-page's payment-detected sequence (Section 7), list animations. This is a common, well-supported pairing (GSAP for marketing timelines, Framer Motion for app UI) and avoids forcing one library to do a job it's weaker at. If you find this adds real complexity without real benefit once building, you may consolidate to Framer Motion alone for both — Framer Motion's `useAnimate` and manual timeline controls can approximate GSAP's choreography with more code — but do not consolidate to GSAP alone, since it fights React's component model for the dashboard's state-driven needs.

Install both behind a thin internal wrapper if you do use both, so a future consolidation is a small, contained change.

### 3.2 Motion principles (apply everywhere)

- **Respect `prefers-reduced-motion`.** Every animation in this system must have a reduced-motion fallback: the hero sequence becomes a static final-state image (the "PAID, hash revealed" frame), the pay-page pulsing glow becomes a static border, list transitions become instant. Build this from the start, not as a later pass.
- **Motion communicates state, not decoration.** Before adding any animation, ask: what is this telling the user that they couldn't tell otherwise? If the answer is "nothing, it just looks nice," cut it. The two animations that matter most in this entire product are the hero sequence (Section 3.3) and the payment-confirmed moment on the pay page (Section 7) — spend the animation budget there, keep everything else (hover states, page transitions) understated and fast (150–250ms, ease-out).
- **One signature motif, reused deliberately.** The "hash materializing from scrambled characters into the real value" animation (full spec below) appears in exactly three places: the hero (Beat 3), the pay-page payment-confirmation moment, and — as a smaller, faster variant — when a dashboard invoice row transitions to `paid` in realtime. Reusing this exact motif across all three is what makes the product feel coherent rather than like three different demos. Do not invent a different "success" animation for any of these three contexts.

### 3.3 The hero sequence — full specification

This is the single most important animation in the product. It runs on loop on the landing page hero, structured as three beats inside one continuous invoice card component.

**Total duration: ~6 seconds per loop, with a 1 second hold on Beat 3 before resetting.**

**Beat 1 — Created (0.0s–1.5s)**
- Card fades/scales in from 96% to 100% scale, 0 to 1 opacity (400ms, ease-out).
- Content shown: invoice amount "$500.00" in Display type, "Invoice INV-0492" in mono-sm beneath it in `--color-silver-dim`, a status pill reading "Awaiting payment" in `--color-amber` on `--color-amber-dim` background.
- A small dot beside the status pill pulses (scale 1 → 1.15 → 1, opacity 0.6 → 1 → 0.6, 1.2s loop) — this exact pulsing-dot treatment is reused on the pay page for the "listening for payment" state, so introduce it here first.

**Beat 2 — Quoted, counting down (1.5s–3.8s)**
- The amber status pill cross-fades to a new pill: a small lightning-bolt icon + "0.00071 BTC" in mono type, still amber.
- A thin circular countdown ring animates around a small clock glyph, depleting over the beat's duration (this is a preview/loop, not literally 15 real minutes — compress it for the loop).
- A miniature QR code fades in beside the amount, with the specular sweep highlight from Section 2.6 playing once as it appears.

**Beat 3 — Paid, proof revealed (3.8s–5.8s, then 1s hold)**
- The amber pill cross-fades to signal green: "Paid" with a checkmark that draws itself via SVG `stroke-dashoffset` animation (path drawing left-to-right, 350ms, ease-in-out) rather than a checkmark that just fades in — the drawing motion is what makes it feel verified rather than decorative.
- Below the amount, a new line appears: `tx_hash` label in `--color-silver-dim`, then the hash value itself — **this is the signature motif**: render a string of random hex-looking characters in mono type, then over ~600ms, resolve character-by-character (left to right, staggered ~15ms per character) into the real-looking hash `7f3a91c4...e21bd08f`. Use a monospace tabular-nums treatment so characters don't shift width as they resolve.
- The whole card gets a very faint signal-green glow (per Section 2.6, technique 2) that wasn't present in Beats 1–2, reinforcing "this state is different/special."
- Hold for 1 second, then cross-fade/reset back to Beat 1 to loop.

**Implementation note:** build this as a single React component (`<HeroInvoiceDemo />`) driven by a GSAP timeline with three labeled sections (`beat1`, `beat2`, `beat3`), looped (`repeat: -1`), so the timeline is inspectable/tunable as one object rather than three disconnected animations guessing at sync.

### 3.4 The payment-confirmed moment (pay page) — reuses Beat 3 exactly

When the pay page's polling detects `status: "paid"` (or `partially_paid`/`overpaid`), trigger the **exact same checkmark-draw + hash-resolve animation** from Hero Beat 3, but driven by Framer Motion (since this is state-driven, not a timeline loop) rather than GSAP. Use the real `tx_hash` from the API response, not a placeholder — the resolve-from-scrambled-characters effect should still play even with the real value, scrambling-then-resolving the actual hash rather than a fake one. This is the moment the whole design system has been building trust toward — give it the full treatment: the glow, the drawn checkmark, the resolving hash, no shortcuts.

### 3.5 Secondary motion (dashboard, lower budget)

- Status badge transitions: 200ms cross-fade + color transition when status changes, no bounce/spring.
- List row insertion (new invoice appears at top of list): slide down + fade, 250ms.
- Hover states: background lightness shift only (`--color-ink` → `--color-ink-raised`), 120ms, no scale/transform on hover anywhere in the dashboard — scale-on-hover is a generic template tell, avoid it here specifically (it's fine on marketing-site buttons, not on dense dashboard rows).

---

## 4. API Integration Layer & Mocking Strategy

### 4.1 Single API client module

All HTTP calls go through one module, `src/lib/api/client.ts`. No component or hook constructs a `fetch`/`axios` call directly — every data access goes through typed functions exported from `src/lib/api/`. This is what makes the "swap mock for real backend later" requirement a one-line change rather than a search-and-replace across the codebase.

```typescript
// src/lib/api/client.ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'; // default true until backend exists

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  if (USE_MOCKS) {
    return mockRequest<T>(path, options); // see 4.5
  }
  const token = getAuthToken(); // reads JWT from memory/localStorage, see Section 6 auth notes
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    throw await buildApiError(response); // typed error, never let raw fetch errors leak to components
  }
  return response.json();
}
```

Switching from mock to real backend later is exactly: set `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL` to the deployed backend URL. No other code changes.

### 4.2 Endpoints this frontend consumes (mirrored from `PRD.md` Section 7 — keep in sync)

**Auth**
```
POST /auth/register   { email, password, business_name } -> { token, user }
POST /auth/login       { email, password } -> { token, user }
GET  /auth/me           -> { id, email, business_name, created_at }
```

**Freelancer invoices (authenticated)**
```
POST /invoices                          { client_name, client_email, description, amount_usd, due_date? }
GET  /invoices?status=&page=&page_size=
GET  /invoices/:id
POST /invoices/:id/cancel
POST /invoices/:id/resend
GET  /invoices/:id/receipt
GET  /overpayment-credits
POST /overpayment-credits/:id/resolve   { action: "acknowledged_keep" | "refunded" }
```

**Public (no auth)**
```
GET  /public/invoices/:id
GET  /public/invoices/:id/payment-methods
POST /public/invoices/:id/payment-target?method=btc_onchain|lightning|usdc|usdt
GET  /public/invoices/:id/status        -- polled every 5s on the pay page
GET  /public/invoices/:id/receipt
```

### 4.3 TypeScript types — derive from the backend schema, keep in one file

Define all shared types in `src/lib/api/types.ts`, matching the backend PRD's enums and field names exactly (e.g. `InvoiceStatus`, field names like `amount_received_usd_equiv`) so there's zero translation/renaming layer between what the API returns and what components consume. Do not camelCase backend snake_case fields at the boundary — keep the wire format as the type, since introducing a transform layer is one more place for the mock and the real backend to drift apart.

```typescript
export type InvoiceStatus =
  | 'draft' | 'pending' | 'partially_paid' | 'paid'
  | 'overpaid' | 'expired' | 'cancelled' | 'refunded';

export type PaymentMethod = 'btc_onchain' | 'lightning' | 'usdc' | 'usdt';

export interface Invoice {
  id: string;
  client_name: string;
  client_email: string;
  description: string | null;
  amount_usd: string;             // Decimal serialized as string — never parse to float for display math
  status: InvoiceStatus;
  amount_received_usd_equiv: string;
  overpaid_amount_usd: string;
  due_date: string | null;
  created_at: string;
}

export interface PaymentTarget {
  id: string;
  method: PaymentMethod;
  network: string | null;
  target_value: string;            // BTC address / BOLT11 string / stablecoin address
  rate_locked_usd_to_crypto: string;
  amount_expected_crypto: string;
  expires_at: string;
}

export interface PublicInvoiceStatus {
  status: InvoiceStatus;
  amount_received_usd_equiv: string;
  remaining_usd: string | null;     // present only if partially_paid
  overpaid_amount_usd: string | null;
  active_target_expires_at: string | null;
  payment?: {                        // present once a payment has landed
    tx_hash: string;
    method: PaymentMethod;
    confirmations: number;
  };
}
```

**Important: treat all monetary/crypto amount fields as strings end to end, only converting to numbers at the point of display formatting, using a decimal-safe library** (e.g. `decimal.js` — install it, do not do float arithmetic on money in the frontend, for the same reason the backend PRD mandates `Decimal` over `Float`).

### 4.4 Polling strategy for the pay page

`GET /public/invoices/:id/status` is polled every 5 seconds while `status` is `pending` or `partially_paid`. Stop polling once status reaches a terminal-feeling state for the client (`paid`, `overpaid`, `cancelled`, `refunded`) — `expired` should also stop polling but show a "refresh quote" action rather than continuing to poll a dead target. Implement via a small custom hook (`usePollInvoiceStatus`) using `setInterval` cleaned up on unmount, not a polling library — this is simple enough not to need a dependency.

### 4.5 Mock data layer

Build `src/lib/api/mocks/` with:
- `mockHandlers.ts` — a `mockRequest()` function (referenced in 4.1) that pattern-matches the requested path/method and returns realistic fixture data with a simulated network delay (150–400ms random, via `setTimeout`) so loading states are actually visible and testable during development.
- `fixtures.ts` — a handful of realistic `Invoice` objects covering every status value, so every dashboard list/detail view has real-looking data to render against without the backend existing.
- **Simulate the full pay-page lifecycle in mocks**: when `payment-target` is requested then `status` is polled repeatedly, have the mock transition the invoice from `pending` → `paid` after ~3 polls (about 15 seconds), with a realistic-looking fake `tx_hash`, so the entire payment-confirmed animation (Section 3.4) can be built and demoed end-to-end before the backend exists. This is the only way to validate the most important animation in the product without a live backend.

---

## 5. Marketing Site — Page-by-Page Spec

### 5.1 `/` Landing page

**Nav (sticky, transparent over hero, solid `--color-ink` with bottom hairline once scrolled):**
"Settra" wordmark (Display typeface, set in `--color-white`, weight 700) — "How it works" — "Pricing" — "Docs" — "Sign in" (ghost button) — "Get started" (solid `--color-white` text on `--color-ink-raised` button, per the 2.2.1 rule — not signal green).

**Section 1 — Hero**
- Headline (Display XL): "Invoice in dollars. Get paid in crypto. Reconcile automatically." — three short clauses, one per line on desktop (stacking to two or three lines responsively), each clause doing one job: the promise to the freelancer, the mechanic for the client, and the engineering differentiator that separates this from a basic payment-link tool. Do not shorten this to two clauses — the third clause ("Reconcile automatically") is what signals this isn't just a QR-code generator, it's a system that handles the underpayment/overpayment ledger work in Section 6.5 of the backend PRD, and that claim deserves to be in the headline, not buried in a feature list.
- Subhead (Body LG, `--color-silver`): "Lock a USD rate the moment your client opens the link. They pay with Bitcoin, Lightning, or a stablecoin — you get a cryptographic receipt either way." (Note: this subhead must not just restate the headline in slightly different words — it earns its place by adding the rate-lock mechanic and naming the actual payment methods, which the headline deliberately keeps abstract as "crypto.")
- `<HeroInvoiceDemo />` (Section 3.3) — placed right of headline on desktop (50/50 split), below headline on mobile, full width.
- Primary CTA: "Get started" button. Secondary: "See how it works" (ghost, scrolls to Section 2).
- No supporting stat row beneath the headline (e.g. no "$2M processed / 500 freelancers" band) — per the design skill's caution against the templated "big number, small label" pattern, and because this product has no real numbers yet; don't fabricate them.

**Section 2 — How it works (the earned numbered sequence)**
Three steps, numbered 01/02/03 — this numbering is justified here because it's a real, ordered process the user will actually follow, not decoration:
- 01 — Create. "Set an amount in USD. We lock today's rate the moment your client opens the link."
- 02 — Pay. "Client pays with Bitcoin, Lightning, or a stablecoin. No wallet lecture required."
- 03 — Prove. "A receipt with the transaction hash lands in both inboxes automatically."
Each step gets a small inline visual (not full animation budget): step 01 shows a static mini invoice card, step 02 shows a static QR + method icons row, step 03 shows a static version of the resolved-hash receipt line. These are intentionally calmer than the hero — consistent with "spend boldness in one place."

**Section 3 — The receipt (Polar-style "show the real artifact" section)**
Large, centered receipt card mockup — this is the actual PDF receipt design (see Section 8.6 component spec), shown at a larger-than-life scale with the tx hash prominently in mono type, a scroll-triggered reveal (GSAP ScrollTrigger or Framer Motion's `whileInView`): the card fades/slides up as it enters viewport, and the hash line plays its resolve animation once, triggered the first time it scrolls into view (not looping). Headline above it: "Proof that doesn't ask to be trusted." Subhead: "Every receipt carries the on-chain transaction hash — verifiable by anyone, on any block explorer."

**Section 4 — Payment methods row**
Three method cards (BTC on-chain, Lightning, USDC/USDT) in a simple row, each with an icon, name, and one-line description ("Best for: larger amounts" / "Best for: instant, small payments" / "Best for: zero volatility"). No animation here beyond a standard fade-in-on-scroll — this section is informational, not a moment.

**Section 5 — Final CTA + footer**
Simple, centered: headline repeat or variant ("Get paid the way you actually want to" works as a variant, avoiding a literal copy-paste of the hero line), "Get started" button. Footer: standard link columns (Product, Company, Legal), the "Settra" wordmark small and quiet, copyright line ("© 2026 Settra").

### 5.2 `/login`, `/signup`

Centered single-column forms on the `--color-ink` background, no hero animation (motion budget is for the landing page, not auth screens — keep these fast and quiet). Standard email/password fields, `--color-white`-on-`--color-ink-raised` submit button, inline validation errors in `--color-danger`.

### 5.3 `/pricing`, `/docs`

Stub-acceptable for v1: same nav/footer shell, simple content, no special animation. Do not skip building the page shells even if content is minimal — broken nav links look unfinished in a way that's disproportionately damaging for a product whose whole pitch is "polished and trustworthy."

---

## 6. Freelancer Dashboard — Page-by-Page Spec

### 6.1 Shell

Persistent left sidebar (collapsible on tablet, hidden behind a hamburger on mobile): "Settra" wordmark (smaller scale than the marketing nav, quieter — per Section 1.1's "same palette, quieter execution" rule for the dashboard), nav items (Overview, Invoices, Overpayments, Settings), user menu at bottom (business name, sign out). Main content area on `--color-ink`, panels/cards on `--color-ink-raised` with the top-edge-highlight glossy treatment from Section 2.6.

### 6.2 `/dashboard` Overview

Three stat cards in a row (stack on mobile): "Outstanding" (sum of `pending`/`partially_paid` invoice amounts), "Paid this month" (signal-green accent on the number specifically, since it's literally a paid-state number — this is one of the few places using signal green outside a status badge, and it's justified because the number itself represents confirmed payments), "Unresolved overpayments" (amber if > 0, with a link to `/dashboard/overpayments`).
Below: a compact recent-activity list (last 5 invoices, any status change), each row using Framer Motion's layout animation so a status change animates smoothly if the user has the tab open when a webhook-driven update arrives (requires a polling or websocket connection on this view too — poll `GET /invoices?page_size=5` every 15s while this page is open).

### 6.3 `/dashboard/invoices` List view

Table (or card list on mobile) with columns: Client, Amount, Status (badge), Created, actions menu. Status badges use ONLY the two-color system (signal green for `paid`/`overpaid`, amber for `pending`/`partially_paid`) — `draft`, `cancelled`, `expired`, `refunded` get a neutral `--color-silver-dim` badge, never amber or green, per Section 2.2.1. Filter pills above the table (All, Pending, Paid, Overpaid, etc.) — selecting one is a simple state filter, no animation beyond the standard 200ms cross-fade.

### 6.4 `/dashboard/invoices/new`

Single-column form: Client name, Client email, Description (textarea), Amount (USD, large mono-styled input since it's a number that matters), Due date (optional date picker), payment methods checkboxes (BTC on-chain / Lightning / USDC / USDT). Submit creates the invoice as `draft` per the backend contract — show a success state with the shareable `/pay/:id` link immediately, with a copy-to-clipboard button (small checkmark micro-animation on copy, 600ms, reusing the draw-in checkmark style from Section 3.3 at a much smaller scale and without the hash-resolve part — just the check).

### 6.5 `/dashboard/invoices/:id` Detail view

This is where the ledger concept from the backend PRD becomes visually literal — do not just show a status badge and call it done:
- Header: client name, amount, status badge, shareable link with copy button.
- **A payment ledger table**: every row from the invoice's `payments`, columns Method, Amount (crypto), USD equivalent, Confirmations, Date. Beneath the table, a summary line: "Received: $X of $Y" with a thin horizontal progress bar (signal green fill up to the paid portion, amber for the gap if partially paid, or extending past 100% in a slightly different green shade if overpaid — this visual directly represents the underpayment/overpayment mechanics from the backend PRD, making the ledger-first principle visible, not just a backend implementation detail).
- Payment targets section: shows any active/expired targets (address/BOLT11/etc., expiry), mostly relevant for debugging/transparency.
- Actions: Resend link, Cancel (only enabled if no payments received, per backend rules), Download receipt (only enabled once a receipt exists).

### 6.6 `/dashboard/overpayments`

List of `overpayment_credits`, each row: source invoice, amount, age (highlight in `--color-danger` text, not a full red background, if older than 7 days — per backend Section 4.6.1), and a resolve action (two buttons: "Mark as kept" / "Mark as refunded", which map to `acknowledged_keep` / `refunded`). Resolving a row animates it out of the unresolved list (slide + fade, 250ms) rather than just disappearing instantly.

### 6.7 `/dashboard/settings`

Business name field, enabled payment methods (checkboxes, persisted — wire to a settings endpoint if/when the backend exposes one; if not yet documented in the backend PRD, store as a TODO and use local state for now), account email (read-only), sign out button.

---

## 7. Public Client Payment Page — Page-by-Page Spec

### 7.1 `/pay/:invoiceId` — full flow

This page has no nav, no sidebar — it's a focused, single-purpose screen, centered, max-width ~480px on desktop (mobile-first, since most real payments here will happen on a phone).

**Load state:** skeleton loader (subtle pulsing `--color-ink-raised` blocks, no spinner) while `GET /public/invoices/:id` resolves.

**Step 1 — Invoice summary**
Business name (small, top), then the headline: the USD amount, large, Display type. Description beneath in Body. This is permanent across all subsequent steps (it doesn't disappear once a method is picked — keep it pinned at the top so the client never loses track of what they're paying).

**Step 2 — Method selection**
Cards for each enabled method (from `GET /public/invoices/:id/payment-methods`), stacked vertically on mobile: icon, method name, one-line note ("Instant" for Lightning, "10–60 min to confirm" for BTC on-chain, "Send only on [network]" for stablecoins). Tapping a card calls `POST /public/invoices/:id/payment-target?method=X` and transitions to Step 3. If Lightning is available, visually mark it as recommended (a small "Fastest" tag in amber, not green — amber here means "in-progress/recommended path," not a paid state, so this doesn't violate 2.2.1) but never auto-select/force it — the client always chooses.

**Step 3 — Payment screen**
- QR code, large, centered, rendered from `target_value` (use `qrcode.react`/similar — for Lightning this is the BOLT11 string with a `lightning:` URI scheme so mobile wallets deep-link correctly; for BTC use a `bitcoin:` URI; for stablecoins, the raw address).
- Beneath the QR: the exact crypto amount expected, in mono type, with a copy button.
- The QR container gets the specular-sweep highlight (Section 2.6) once on appearance, and the pulsing amber "listening" dot (Section 3.3 Beat 1 motif) stays active beside a small "Waiting for payment" label for as long as status remains `pending`.
- A countdown timer (mono type) shows time remaining on the rate lock, computed from `active_target_expires_at`. If it hits zero with no payment, transition to an expired state with a "Refresh quote" button (re-calls the payment-target endpoint) rather than a dead end.
- Network warning for stablecoins: a small, clearly visible note ("Only send on [network] — funds sent on another network may be unrecoverable") in `--color-amber`, not buried in fine print.

**Step 4 — Payment confirmed**
Triggered when polling (`usePollInvoiceStatus`, Section 4.4) returns a non-pending status. Plays the full payment-confirmed animation from Section 3.4: amber pulsing stops, checkmark draws in signal green, tx hash resolves character-by-character from the real `payment.tx_hash`. Beneath: "Download receipt" button (primary), and a block-explorer link ("View on [explorer name]") constructed from `method`/`network`. Small reassurance line: "The freelancer has been notified."

**Underpaid variant:** if status is `partially_paid`, instead of the full success treatment, show a calmer intermediate state: a half-filled progress indicator (not the checkmark), "Partial payment received" in amber, remaining balance clearly stated, and a "Pay remaining balance" button that re-triggers Step 2/3 scoped to the remainder (per backend Section 6.7) — same visual language, deliberately less celebratory than full success, so the client doesn't think they're done when they're not.

**Overpaid variant:** show the full success/checkmark treatment (money did arrive, this should still feel resolved and positive for the client), plus a small, non-alarming note: "You sent slightly more than required — noted for the freelancer." No action required from the client here; the freelancer handles resolution on their side.

---

## 8. Component Library

Build these as shared components in `src/components/`, used across all three surfaces rather than re-implemented per-page.

### 8.1 `<StatusBadge status={InvoiceStatus} />`
Maps status to color per Section 2.2.1's two-color rule. Single source of truth for status→color mapping — no other component should hardcode a status color.

### 8.2 `<HashReveal value={string} trigger={"mount" | "inView" | "manual"} size={"sm"|"md"|"lg"} />`
The signature animation component (Section 3.3/3.4). Takes a real hash string, renders scrambled placeholder characters, resolves to the real value on trigger. Used in: hero (Beat 3), pay-page confirmation, receipt component, and dashboard invoice detail (where it can just render in its resolved state immediately, `trigger="manual"` and never fired, since the hash is already known/historical there — don't replay the reveal animation every time someone views an old, already-paid invoice's detail page, that would feel gimmicky on repeat views).

### 8.3 `<HeroInvoiceDemo />`
The full looping three-beat GSAP sequence (Section 3.3). Self-contained, no props needed — it's a fixed demo, not driven by real data.

### 8.4 `<QRPaymentTarget targetValue={string} method={PaymentMethod} amount={string} />`
Renders the QR code, copy button, method-appropriate URI scheme, and the specular-sweep + pulsing-dot treatment.

### 8.5 `<CountdownRing expiresAt={string} onExpire={() => void} />`
The circular depleting countdown used in both the hero (looped/fake) and the real pay page (real `expires_at`).

### 8.6 `<ReceiptCard invoice={Invoice} payment={Payment} variant={"marketing" | "real"} />`
Shared between the marketing site's Section 3 showcase (`variant="marketing"`, fixed fixture data) and the actual pay-page/dashboard receipt display (`variant="real"`, real data) — this is what guarantees the marketing site's "this is what you get" promise visually matches the actual product output exactly, which matters more for trust here than almost anything else on the site.

### 8.7 `<Button variant={"primary"|"ghost"|"danger"} />`, `<Input />`, `<Card />`
Standard primitives, built once, styled per Section 2, used everywhere — do not let individual pages define one-off button/input styles.

---

## 9. Project Structure

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx                      # router setup
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── types.ts
│   │   │   ├── invoices.ts          # typed functions: createInvoice(), getInvoice(), etc.
│   │   │   ├── auth.ts
│   │   │   ├── public.ts            # public endpoint functions
│   │   │   └── mocks/
│   │   │       ├── mockHandlers.ts
│   │   │       └── fixtures.ts
│   │   ├── decimal.ts               # decimal.js wrapper helpers for money formatting
│   │   └── hooks/
│   │       ├── usePollInvoiceStatus.ts
│   │       └── useAuth.ts
│   ├── components/
│   │   ├── StatusBadge.tsx
│   │   ├── HashReveal.tsx
│   │   ├── HeroInvoiceDemo.tsx
│   │   ├── QRPaymentTarget.tsx
│   │   ├── CountdownRing.tsx
│   │   ├── ReceiptCard.tsx
│   │   └── ui/                       # Button, Input, Card primitives
│   ├── pages/
│   │   ├── marketing/
│   │   │   ├── Landing.tsx
│   │   │   ├── Pricing.tsx
│   │   │   └── Docs.tsx
│   │   ├── auth/
│   │   │   ├── Login.tsx
│   │   │   └── Signup.tsx
│   │   ├── dashboard/
│   │   │   ├── Overview.tsx
│   │   │   ├── InvoiceList.tsx
│   │   │   ├── InvoiceNew.tsx
│   │   │   ├── InvoiceDetail.tsx
│   │   │   ├── Overpayments.tsx
│   │   │   └── Settings.tsx
│   │   └── pay/
│   │       └── PayInvoice.tsx
│   ├── styles/
│   │   ├── tokens.css                # the CSS custom properties from Section 2.2
│   │   └── fonts.css                 # @font-face declarations
│   └── assets/
│       └── fonts/                     # self-hosted General Sans + JetBrains Mono files
├── public/
├── tailwind.config.ts                 # extends theme with the token system
├── vite.config.ts
├── .env.example
└── package.json
```

---

## 10. Responsive & Accessibility Requirements

- **Mobile-first for the pay page specifically** — most real client payments will happen on a phone. Build and test this surface at 375px width first, then scale up, not the reverse.
- **Dashboard**: usable down to tablet width (768px) with the sidebar collapsing to icons-only or a hamburger; full table views can scroll horizontally on narrow screens rather than breaking into illegible stacked cards, but provide a card-based fallback at < 480px if time allows.
- **Keyboard navigation**: all interactive elements (buttons, form fields, method-selection cards on the pay page) must be reachable and operable via keyboard, with a visible focus ring using `--color-signal` at reduced opacity (a focus ring is one of the only places a slightly off-label use of signal green is acceptable, since it's a universal, expected UI convention, not a status claim).
- **`prefers-reduced-motion`**: implement the fallbacks described in Section 3.2 for every animation, not just the hero.
- **Color contrast**: `--color-silver` on `--color-ink` and `--color-white` on `--color-ink` must both meet WCAG AA for body text sizes — verify with a contrast checker once the exact hex values are implemented, adjust `--color-silver` lighter if it falls short rather than shipping a failing contrast ratio.
- **Monospace data should remain selectable/copyable** — never render hashes, addresses, or BOLT11 strings as images or canvas-only text; they must be real, selectable DOM text so users can copy them manually as a fallback to the copy button.

---

## 11. Build Order / Milestones

**Milestone 1 — Design system foundation**
Tailwind config with all tokens from Section 2, font files self-hosted and loading correctly, `<Button>`, `<Input>`, `<Card>`, `<StatusBadge>` primitives built and visually verified against a throwaway test page.

**Milestone 2 — API layer + mocks**
Build the full `src/lib/api/` module per Section 4, including the mock layer with realistic fixtures covering every `InvoiceStatus`. Verify by logging mock responses in the console before wiring any UI to them.

**Milestone 3 — Marketing site shell, no hero animation yet**
Build `/`, `/pricing`, `/docs`, `/login`, `/signup` with all content and layout from Section 5, but with `<HeroInvoiceDemo />` as a static placeholder (just Beat 3's final frame, no animation). Get the page fully responsive and content-complete first.

**Milestone 4 — The hero animation**
Build `<HeroInvoiceDemo />` for real, per Section 3.3's full GSAP timeline spec. This is its own milestone because it's the highest-risk, highest-value piece of UI in the whole project — don't let it block other surfaces from progressing in Milestone 3.

**Milestone 5 — Dashboard, full CRUD against mocks**
Build all of Section 6 against the mock API layer. By the end of this milestone, a freelancer can create an invoice, see it in the list, view its detail page, and see realistic-looking ledger data — all from mocks.

**Milestone 6 — Public pay page, full flow against mocks**
Build all of Section 7, using the mock layer's simulated `pending → paid` lifecycle (Section 4.5) to validate the entire method-selection → QR → confirmation flow, including the `<HashReveal>` payment-confirmed animation, end to end without a real backend.

**Milestone 7 — Cross-cutting polish**
Responsive pass (Section 10), `prefers-reduced-motion` fallbacks across every animated component, accessibility pass (focus states, contrast verification), the receipt component shared correctly between marketing Section 3 and the real pay-page/dashboard receipt (Section 8.6).

**Milestone 8 — Backend cutover**
Set `VITE_USE_MOCKS=false`, point `VITE_API_BASE_URL` at the real deployed FastAPI backend, and verify every flow built against mocks in Milestones 5–6 still works against real responses. Expect and budget time for small field-name/shape mismatches between what was assumed here and what the backend actually returns — reconcile against the backend PRD's Section 7 contract, updating either side as needed, and flag any real discrepancy rather than silently patching around it.

---

## 12. Open Questions / Things to Confirm

1. **Berkeley Mono licensing** — confirm whether a license is available/affordable; if not, default straight to JetBrains Mono without treating it as a downgrade, it's a strong, legible choice on its own.
2. **Settings endpoint for payment methods** — the backend PRD doesn't explicitly define a settings/payment-methods-enabled endpoint; confirm with the backend build whether this exists or needs to be added, since Section 6.7 depends on it.
3. **Block explorer URL construction per network** — confirm the exact set of networks Bitnob's sandbox actually supports (per backend PRD Section 16, item 7) before finalizing the explorer-link-building logic in the receipt/confirmation components, since the URL pattern differs per chain.
4. **Whether `/pricing` needs real content** before this is shown to anyone external (e.g. Bitnob) — flag this back rather than assuming a stub is fine for that audience specifically.
