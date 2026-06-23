# Go-Live Checklist — Lead///Center (tenant-#1 MVP)

This is the honest path from the current branch to a private, deployed dashboard you
(tenant #1 / FLUXO) can log into and use. Items marked **(you)** need accounts/secrets
only you can create. Items marked **(code)** are already done on this branch unless noted.

## What's deployable right now
- (code) Server-rendered Radar feed dashboard with password login (session cookie).
- (code) Credit ledger, scoring, ranked leads, RLS schema, Dockerfile, render.yaml, CI.
- ⚠️ Leads come from a **fake** data provider — flagged "fake data" in the UI. The app is
  fully usable, but the businesses aren't real until step 2 below.

## 1. Real data — the one thing that makes this actually useful **(you + code)**
- (you) Create an **Outscraper** account, get an API key.
- (code, next pass) Write `src/adapters/data/outscraper_adapter.py` implementing
  `DataProviderPort`, swap it in at `src/main.py::build_deps` (one line), set
  `OUTSCRAPER_API_KEY`. Until then the dashboard shows placeholder leads.

## 2. Database **(you)**
- Create a **Supabase** project (managed Postgres).
- Apply the schema + RLS: run `db/schema.sql` against the database (SQL editor or
  `psql "$DATABASE_URL" -f db/schema.sql`).
- Copy the connection string into `DATABASE_URL`.

## 3. Secrets / env on the host **(you)**
Set these (Render dashboard or `render.yaml` `sync:false` vars):
- `LEADCENTER_BACKEND=postgres`
- `DATABASE_URL=...`
- `AUTH_MODE=session`
- `SESSION_SECRET=` long random (`openssl rand -hex 32`)
- `LOGIN_PASSWORD=` your dashboard password
- `TENANT_NAME=FLUXO`, optional `LEADCENTER_FREE_CREDITS=50`
Never commit these. `.env` is git-ignored.

## 4. Deploy **(you)**
- Push to GitHub; connect the repo to **Render** (uses `render.yaml` + `Dockerfile`).
  Railway works too via the Dockerfile. **Not Vercel** — this is a persistent server.
- On boot the app bootstraps the tenant account + grants free credits (idempotent).
- Verify `GET /healthz` returns `{"status":"ok"}`, then log in at `/`.

## 5. Domain (optional for internal use) **(you)**
- Point a subdomain at the host; enable HTTPS (Render does this automatically).

---

## Enabling outreach (step 5) — built, off by default
The find → verify → suppression → send → track pipeline is implemented behind a flag,
on **fake** email adapters. To turn it on:
- Set `OUTREACH_ENABLED=true`.
- Set `OUTREACH_PHYSICAL_ADDRESS` (a real postal address — **required**, CAN-SPAM; sends
  are refused without it), plus `OUTREACH_FROM_NAME/EMAIL` and `OUTREACH_UNSUBSCRIBE_URL`.
- ⚠️ Nothing real is sent until you write a real `EmailSenderPort` adapter (Resend/Postmark)
  and an `EmailFinderPort` (Hunter/site-crawl), and **warm a sending domain with
  SPF/DKIM/DMARC**. The `GET /unsubscribe` endpoint and suppression list are already wired.

## Payments (step 6) — built, on a fake adapter
Packs catalog, checkout, and an **idempotent** webhook→ledger grant are implemented and
seeded at startup. To go real: write a Stripe `PaymentsPort` adapter (Checkout Session +
**signature-verified** webhook on `STRIPE_WEBHOOK_SECRET`), set the keys, and point a
Stripe webhook at `POST /webhooks/stripe`. The ledger's `UNIQUE(stripe_event_id)` already
guarantees a replayed event can't double-grant. Calibrate pack prices once COGS is measured
(an OPEN item in ARCHITECTURE.md).

## Not done yet — required before a PUBLIC launch (later passes)
- **Real adapters** — Outscraper (data), Anthropic Haiku (pitch), Resend/Postmark + Hunter
  (outreach), Stripe (payments). All exist as ports with fakes; each needs your key + a
  small dependency.
- **Reply/bounce ingestion** — inbound tracking (status replied/booked) + bounce webhook.
- **Public auth** — replace the single-password session with Supabase Auth/JWT + signup.
- **Brand** — footer/favicon via `brand.js` (deferred per CLAUDE.md; ask before adding).
