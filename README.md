# Lead///Center

Multi-tenant lead-gen SaaS. This repo currently contains **v1 build-order step 1:
the skeleton + money spine** — domain entities, ports, a derived-balance credit
ledger with transactional spend, the `RunScan` use case, an in-memory backend, a
Postgres + RLS backend, and a thin FastAPI surface. See `ARCHITECTURE.md` for the
full contract and `CLAUDE.md` for the working standards.

## What works today

`RunScan`: DISCOVER businesses → write N leads → spend N credits, atomically, with
confirm-before-spend and per-run caps. Tenant isolation is enforced by Postgres RLS
(`db/schema.sql`). With no database it runs against an in-memory store.

## Layout

```
src/domain/        pure entities + errors (no framework/vendor imports)
src/ports/         interfaces: DataProviderPort, repos, UnitOfWork
src/application/   credits.py (metering), run_scan.py (use case)
src/adapters/      fake data provider, in-memory + Postgres UnitOfWork
src/delivery/api/  FastAPI app (DTOs + routes)
src/config.py      env-driven config (secrets read here only)
src/main.py        composition root: wires adapters -> ports
db/schema.sql      tables + Row-Level Security policies
tests/             unit · application · api · arch · integration (RLS)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
# In-memory backend (default, no DB):
uvicorn src.main:app --reload

curl -s localhost:8000/scans -H 'X-Account-Id: <uuid>' \
  -H 'content-type: application/json' \
  -d '{"niche":"plumbers","city":"austin","limit":5,"confirmed":true}'
```

> Auth is a placeholder `X-Account-Id` header in the spine; Supabase Auth/JWT
> replaces it in a later step. Vendor adapters (Outscraper, Anthropic, Stripe,
> email) are not wired yet — `RunScan` uses a clearly-labelled fake data provider.

## Test

```bash
pytest                              # unit + application + api + arch (no DB needed)
lint-imports                        # enforce the ports/layers rule
pytest --cov=src --cov-report=term-missing

# RLS tests need a real Postgres:
docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest tests/integration -q
```
