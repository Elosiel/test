# Lead///Center

Multi-tenant lead-gen SaaS. This repo contains build-order **steps 1-2** (spine +
scoring) plus a **deployable tenant-#1 MVP**: a server-rendered Radar feed dashboard
with password login. See `ARCHITECTURE.md` for the full contract, `CLAUDE.md` for the
working standards, and `docs/GOLIVE.md` for the deploy checklist.

## What works today

- **`RunScan`**: DISCOVER → write N leads → spend N credits, atomically, with
  confirm-before-spend and per-run caps.
- **Scoring**: deterministic opportunity / fit / confidence → ranked leads.
- **Radar feed dashboard** (`/`): log in, run a scan, see ranked leads + credit balance.
- Tenant isolation enforced by Postgres RLS (`db/schema.sql`). Runs against an in-memory
  store with no database for local dev.
- ⚠️ Discovery uses a **fake** data provider (flagged "fake data" in the UI) until the
  Outscraper adapter is wired — see `docs/GOLIVE.md`.

## Layout

```
src/domain/        pure entities + errors (no framework/vendor imports)
src/ports/         interfaces: DataProviderPort, repos, UnitOfWork
src/application/   credits.py (metering), run_scan.py (use case)
src/adapters/      fake data provider, in-memory + Postgres UnitOfWork
src/delivery/api/  FastAPI JSON app (DTOs + routes)
src/delivery/web/  server-rendered Radar feed (HTML, brand-styled)
src/delivery/auth.py  session-cookie + dev-header auth
src/config.py      env-driven config (secrets read here only)
src/main.py        composition root: wires adapters -> ports, bootstraps tenant
db/schema.sql      tables + Row-Level Security policies
Dockerfile · render.yaml · .github/workflows/ci.yml   deploy + CI
tests/             unit · application · api · web · arch · integration (RLS)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
# Dashboard (session auth) — in-memory backend, no DB:
AUTH_MODE=session SESSION_SECRET=$(openssl rand -hex 32) LOGIN_PASSWORD=letmein \
  uvicorn src.main:app --reload
# open http://localhost:8000/ and log in with the password above

# JSON API (dev-header auth, default):
uvicorn src.main:app --reload
curl -s localhost:8000/scans -H 'X-Account-Id: <uuid>' \
  -H 'content-type: application/json' \
  -d '{"niche":"plumbers","city":"austin","limit":5,"confirmed":true}'
```

> `AUTH_MODE=dev_header` (default) trusts the `X-Account-Id` header — local/tests only.
> `AUTH_MODE=session` is the production path (password login + signed cookie). Supabase
> Auth/JWT replaces it for the public SaaS. Vendor adapters (Outscraper, Anthropic,
> Stripe, email) are not wired yet — discovery uses a labelled fake data provider.

## Deploy

See `docs/GOLIVE.md`. Summary: apply `db/schema.sql` to a Supabase Postgres, set the
env secrets (`DATABASE_URL`, `SESSION_SECRET`, `LOGIN_PASSWORD`, `AUTH_MODE=session`,
`LEADCENTER_BACKEND=postgres`), and deploy the `Dockerfile` to Render/Railway (**not**
Vercel — persistent server).

## Test

```bash
pytest                              # unit + application + api + arch (no DB needed)
lint-imports                        # enforce the ports/layers rule
pytest --cov=src --cov-report=term-missing

# RLS tests need a real Postgres:
docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest tests/integration -q
```
