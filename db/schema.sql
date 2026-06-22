-- Lead///Center — v1 spine schema (Postgres / Supabase).
-- Every tenant table is RLS-scoped to app.current_account_id and uses
-- FORCE ROW LEVEL SECURITY so even the table owner is subject to the policies.
--
-- The connecting code sets the account per transaction with:
--   SELECT set_config('app.current_account_id', '<uuid>', true);
--
-- Only the tables needed by the spine (accounts, personas, territories, runs,
-- leads, credit_ledger) are created here. Outreach/payments tables land with
-- their build steps.

-- A NULL or unset GUC must not match any account_id. current_setting(..., true)
-- returns NULL when unset; '' -> NULL keeps policies from matching everything.
CREATE OR REPLACE FUNCTION current_account_id() RETURNS uuid
    LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.current_account_id', true), '')::uuid
$$;

CREATE TABLE IF NOT EXISTS accounts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id text NOT NULL,
    name          text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS personas (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      uuid NOT NULL REFERENCES accounts(id),
    name            text NOT NULL,
    target_category text,
    geo             text,
    keywords_json   jsonb NOT NULL DEFAULT '[]',
    size_hint       text,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS territories (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  uuid NOT NULL REFERENCES accounts(id),
    persona_id  uuid REFERENCES personas(id),
    niche       text NOT NULL,
    city        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id    uuid NOT NULL REFERENCES accounts(id),
    territory_id  uuid,
    "limit"       integer NOT NULL,
    cost_credits  integer NOT NULL,
    summary_json  jsonb NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      uuid NOT NULL REFERENCES accounts(id),
    run_id          uuid,
    name            text NOT NULL,
    category        text,
    address         text,
    phone           text,
    website         text,
    email           text,
    email_verified  boolean NOT NULL DEFAULT false,
    rating          numeric,
    review_count    integer,
    opportunity     integer NOT NULL DEFAULT 0,
    fit             integer NOT NULL DEFAULT 0,
    confidence      integer NOT NULL DEFAULT 0,
    rank            numeric NOT NULL DEFAULT 0,
    primary_gap     text,
    hot_signal      boolean NOT NULL DEFAULT false,
    fresh_pain_json jsonb,
    pitch           text,
    status          text NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'contacted', 'replied', 'booked')),
    source          text NOT NULL DEFAULT 'unknown',
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Append-only financial source of truth. Balance is SUM(delta), never stored.
CREATE TABLE IF NOT EXISTS credit_ledger (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      uuid NOT NULL REFERENCES accounts(id),
    delta           integer NOT NULL,
    reason          text NOT NULL,
    stripe_event_id text UNIQUE,           -- idempotency key for Stripe webhooks
    balance_after   integer NOT NULL,       -- audit only; SUM(delta) is authoritative
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_leads_account ON leads(account_id);
CREATE INDEX IF NOT EXISTS idx_ledger_account ON credit_ledger(account_id);

-- ---------------------------------------------------------------------------
-- Row-Level Security: the hard tenant boundary, enforced at the DB.
-- ---------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['personas','territories','runs','leads','credit_ledger']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS account_isolation ON %I', t);
        EXECUTE format(
            'CREATE POLICY account_isolation ON %I USING (account_id = current_account_id()) '
            'WITH CHECK (account_id = current_account_id())', t);
    END LOOP;
END $$;
