# Lead///Center — System Architecture (frozen v1 contract)

> This is the contract Claude Code builds against. Do not deviate without updating this file.
> Decisions marked **OPEN** must be resolved by measurement before they gate revenue.

---

## Purpose & operating decision

A multi-tenant SaaS that turns a **niche + city** (or a manually added business) into ranked, pitch-ready leads with timing signals, then lets the user contact them with AI-drafted email from the dashboard. Metered by credits. Data via a provider port (Outscraper to start); generation via Claude.

**Operating decision (locked):** product-shaped, but **you are tenant #1**. v1's first job is to generate and contact FLUXO's contractor leads. Success metric for the build = FLUXO leads contacted from this dashboard, not "platform shipped." Multi-tenancy is built from day one (cheap via RLS, and it's the path to selling) — this is the one allowed deviation from "don't over-build pre-validation," justified by the product goal.

## ICPs (Rule of One — one of each, first)

- **Platform user (who pays):** small B2B service agencies/freelancers who sell *to local businesses* and need a steady, prioritized list of prospects with a reason-to-reach-out and a ready first email. Start with **yourself / FLUXO** as user #1.
- **Lead (who the user hunts):** local service businesses in a chosen niche + geography with a visible, recent pain signal (e.g., a fresh unanswered negative review) and a gap the user's service fixes.

---

## Pillars

1. **Multi-tenant, account-isolated.** Every row scoped to `account_id`; Postgres **Row-Level Security** is the hard boundary, enforced at the DB, not just the app.
2. **Append-only credit ledger = financial source of truth.** Balance is *derived* (`SUM(delta)`), never a mutable counter. Every grant/spend is a ledger row inside a transaction.
3. **Ports & adapters for everything that costs money or can change** — data provider, AI, payments, **email finder**, **email sender**. Core never imports a vendor SDK.
4. **Deterministic core, AI only at the edges.** Scoring and signal detection are pure, reproducible code. The LLM is used *only* for generation (pitch, brief). Keeps COGS down and scores trustworthy.
5. **On-demand, no always-on infrastructure.** Pipelines run on user action. No schedulers/queues/workers.
6. **Cost-safety is first-class.** Cache external results; per-account caps + rate limits; confirm-before-spend; never bill failed work.
7. **Outreach is a deliverability + compliance subsystem, not a field.** Verify before send; CAN-SPAM compliant; suppression list honored; protect the sending domain.
8. **Honesty constraints baked in.** No mock data presented as real, no silent fallbacks, real sources attributed.

---

## Layered design (dependencies point inward)

```
DELIVERY        FastAPI routes, auth middleware, Radar feed frontend, DTOs
APPLICATION     use cases · credit metering · transaction boundary · confirm-before-spend
DOMAIN (pure)   entities (Account, Territory, Persona, Lead, CreditLedger, Message)
                rules: opportunity, fit, confidence, signal detection
PORTS           DataProviderPort, AIPort, PaymentsPort, EmailFinderPort,
                EmailSenderPort, LeadRepo, CreditRepo, SuppressionRepo, CachePort
ADAPTERS        Outscraper, Anthropic, Stripe, (Hunter/free), (Resend/Gmail),
                Supabase repos, BusinessCache
```

Domain imports nothing from frameworks/vendors. Application is where a credit is spent *inside the same transaction* that writes the result.

---

## Core pipeline

```
DISCOVER ─► ENRICH ─► SIGNAL ─► SCORE ─► PITCH ─► SEND ─► TRACK ─► METER
   │           ▲                                    │
 Places     manual-add                          verify first,
  scan      enters here                         suppression-checked
```

- **DISCOVER** — `DataProviderPort`: search `{niche} in {city}` (+ industry/category filters). User picks geography/industry/city.
- **ENRICH** — reviews + website crawl (gaps) + social presence; also the manual-add entry point.
- **SIGNAL** — v1 single signal: `hot_signal` if a review is ≤14d old, ≤3★, unanswered → `fresh_pain`. Detectors live in `domain/signals.py` as pure functions so more signals (new GBP, hiring, website tech change) are added later without touching the pipeline.
- **SCORE** — deterministic, three components (see below).
- **PITCH** — `AIPort` (Haiku): ≤150 words, **signal-first when a hot_signal exists, else gap-first**, differential positioning.
- **SEND** — `EmailFinderPort` (find) → verify → `SuppressionRepo` check → `EmailSenderPort` (send). Never send unverified or suppressed.
- **TRACK** — capture sent/bounced/replied; move `status` new→contacted→replied→booked.
- **METER** — spend credits per fully processed lead, transactionally; never on failure.

---

## Scoring model (deterministic; addresses the brief directly)

Three independent components, each 0–100, combined into a rank:

- **Opportunity** — does this business have approachable pain? (your Vigor / Vibe / Density.)
- **Fit** — how well does this lead match the **Persona** the user defined for this territory? (category match, size proxy via review_count, geography, keywords.)
- **Confidence** — how complete/trustworthy is the data we hold? (has verified email? website? recent reviews? — drives whether it's safe to contact.)

Rank = weighted blend; weights live in `config.py`. Low-Confidence leads are never auto-sent.

---

## Folder structure

```
src/
  domain/        scoring.py, signals.py, opportunity.py, fit.py, confidence.py, entities.py
  application/   run_scan.py, add_lead.py, enrich.py, pitch.py, find_email.py,
                 send_email.py, track_replies.py, credits.py, batch.py, brief.py, personas.py
  ports/         data_provider.py, ai.py, payments.py, email_finder.py,
                 email_sender.py, repositories.py, suppression.py, cache.py
  adapters/
    data/outscraper_adapter.py
    ai/anthropic_adapter.py
    payments/stripe_adapter.py
    email/finder_adapter.py        # free source first; Hunter/etc. behind same port
    email/sender_adapter.py        # Resend or Postmark; Gmail API optional
    db/supabase_repos.py
    cache/business_cache.py
  delivery/
    api/         auth, scans, leads, personas, credits, outreach, webhooks
    web/         Radar feed frontend
  config.py      FREE_CREDITS, pack prices, MODEL_ID, score weights/thresholds, TTLs, FROM address
  main.py        composition root: wire adapters → ports, read secrets
```

---

## Data model (Postgres / Supabase, all RLS-scoped by `account_id`)

```
accounts        (id, owner_user_id, name, created_at)
personas        (id, account_id, name, target_category, geo, keywords_json,
                 size_hint, notes, created_at)              -- the "who I want" definition
territories     (id, account_id, persona_id, niche, city, created_at)
runs            (id, account_id, territory_id, limit, cost_credits, summary_json, created_at)
leads           (id, account_id, run_id, name, category, address, phone, website, email,
                 email_verified, rating, review_count,
                 opportunity, fit, confidence, rank,
                 primary_gap, hot_signal, fresh_pain_json, pitch,
                 status, source, created_at)   -- status: new|contacted|replied|booked
messages        (id, account_id, lead_id, direction, subject, body, provider_id,
                 state, sent_at, created_at)    -- direction: out|in ; state: queued|sent|bounced|replied
suppression     (id, account_id, email_or_domain, reason, created_at)  -- opt-outs + hard bounces
credit_ledger   (id, account_id, delta, reason, stripe_event_id, balance_after, created_at)
business_cache  (business_id, niche, city, payload_json, fetched_at)
packs           (id, name, credits, price_cents, stripe_price_id, active)
```

---

## External boundaries (adapters)

| Concern | Port | Start with | Swappable to |
|---|---|---|---|
| Business data | `DataProviderPort` | Outscraper | SerpAPI, DataForSEO |
| AI generation | `AIPort` | Anthropic (Haiku) | any LLM |
| Payments | `PaymentsPort` | Stripe | Paddle, Lemon Squeezy |
| Email finding | `EmailFinderPort` | free/site-crawl first | Hunter, Dropcontact |
| Email sending | `EmailSenderPort` | Resend or Postmark | Gmail API, SES |
| Persistence | `*Repo` | Supabase / Postgres | any Postgres |

Note: Outscraper / SerpAPI / DataForSEO all resell Google data; the port protects against a vendor dying, not against the underlying ToS/gray-area category risk. Treat stored Google-derived content conservatively.

---

## Cross-cutting concerns

- **Auth & tenancy** — Supabase Auth; RLS on every table keyed to `account_id`; service key server-side only.
- **Credit metering** — wrap each billable use case; spend in the same transaction that persists the result; reject if balance would go negative; never bill failed work.
- **Caching** — `business_cache` checked before any paid external call; TTL ~7 days.
- **Rate limits / caps** — per-account runs/day and leads/run; free cap = signup grant.
- **Cost-safety** — estimate + explicit confirm before scans and batch sends ("70 leads = 70 credits").
- **Outreach compliance (hard rules)** — every send includes a real physical postal address and a working unsubscribe; unsubscribes + hard bounces go to `suppression` and are checked before every send; no send to unverified email; honest from-name/subject. Protect domain reputation: SPF/DKIM/DMARC on the sending domain, warm it before volume.
- **Payments** — Stripe Checkout; webhook handler **idempotent** on `event.id`; ledger row on success.
- **Secrets** — env only, read at composition root; never in code or shipped to client.
- **Errors** — per-item skip-and-continue; per-run summary (found / enriched / hot / sent / spent).

---

## Hosting & deploy

- **DB + Auth:** Supabase (managed Postgres + RLS).
- **App host:** Railway or Render (FastAPI is a persistent Python server — **not** Vercel; Vercel was for the static landing pages). Replit is acceptable for this stage per the draft.
- **Workflow:** built in Claude Code → `git push` → host auto-deploys. The CLAUDE.md for this repo must encode: the ports rule (core imports no vendor SDK), the RLS-per-table rule, the ledger invariant (balance is derived, spend is transactional), and the outreach compliance rules — so Code can't violate them.

---

## Build order (vertical slice first — prove the spine before the features)

1. **Skeleton + money spine.** Domain entities + ports + DB schema with RLS + the credit ledger. One use case end-to-end: `RunScan` finds N businesses → writes N leads → spends N credits transactionally. No enrichment, no AI yet. Prove isolation + metering work.
2. **Enrich + score.** Add ENRICH and the three-part score. Radar feed renders ranked leads.
3. **Signal.** Add the single `fresh_pain` detector.
4. **Pitch.** Add Haiku pitch generation.
5. **Outreach.** Add find → verify → suppression → send → track, with compliance wired in. This is the riskiest subsystem — build it last and behind a feature flag.
6. **Payments.** Stripe packs + webhook ledger. (Only after you, tenant #1, have used it on FLUXO and seen the cost-per-lead.)

---

## Deliberately NOT building v1

- No microservices — one modular monolith.
- No event bus / queues / workers — synchronous, on-demand.
- No CQRS/event-sourcing beyond the credit ledger.
- No email **sequences / drip cadences** — one AI email per lead. Add cadences only after replies prove the channel.
- No CRM, no team seats, no multi-region, no Kubernetes.

---

## OPEN — must resolve by measurement before charging anyone

1. **Cost per fully processed lead (COGS).** Outscraper call + enrichment + email find/verify + Haiku pitch + send. The build's run-summaries + ledger will produce this number. **You cannot price credit packs until you have it.**
2. **Email find-rate and deliverability reality.** What % of scraped businesses yield a verified email on free sources? What's the bounce/spam rate? If find-rate is low or bounces are high, the "send from dashboard" promise weakens and COGS climbs. Measure on your own FLUXO list first.
3. **Pack pricing.** Derived from #1 once measured (target gross margin per credit).
