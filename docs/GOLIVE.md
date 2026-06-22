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

## Not done yet — required before a PUBLIC launch (later passes)
- **Backend step 3** — `fresh_pain` signal detector (and it unlocks Opportunity's Vigor).
- **Backend step 4** — Pitch generation (Anthropic `AIPort`; needs `ANTHROPIC_API_KEY`).
- **Backend step 5** — Outreach: email find → verify → suppression → send → track, with
  CAN-SPAM compliance and **SPF/DKIM/DMARC** on the sending domain (needs an email vendor).
- **Backend step 6** — Stripe credit packs + idempotent webhook ledger.
- **Public auth** — replace the single-password session with Supabase Auth/JWT + signup.
- **Brand** — footer/favicon via `brand.js` (deferred per CLAUDE.md; ask before adding).
