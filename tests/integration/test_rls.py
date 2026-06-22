"""P0 — RLS tenant isolation against a REAL Postgres. Skipped unless DATABASE_URL
is set. This is the hard security boundary; it cannot be proven with the in-memory
fake, only at the database.

Run locally e.g.:
    docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest tests/integration -q
"""
from __future__ import annotations

import os
import pathlib

import pytest

psycopg = pytest.importorskip("psycopg")

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="set DATABASE_URL to run RLS tests"),
]

SCHEMA = (pathlib.Path(__file__).resolve().parents[2] / "db" / "schema.sql").read_text()


@pytest.fixture
def conn():
    c = psycopg.connect(DATABASE_URL)
    with c.cursor() as cur:
        cur.execute(SCHEMA)
    c.commit()
    yield c
    c.rollback()
    c.close()


def _new_account(conn, name: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO accounts (owner_user_id, name) VALUES (%s, %s) RETURNING id",
            (f"user-{name}", name),
        )
        account_id = cur.fetchone()[0]
    conn.commit()
    return str(account_id)


def _insert_lead(conn, account_id: str, name: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_account_id', %s, false)", (account_id,))
        cur.execute(
            "INSERT INTO leads (account_id, name) VALUES (%s, %s)", (account_id, name)
        )
    conn.commit()


def _visible_lead_names(conn, account_id: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_account_id', %s, false)", (account_id,))
        cur.execute("SELECT name FROM leads ORDER BY name")
        return [r[0] for r in cur.fetchall()]


def test_account_cannot_see_another_accounts_leads(conn):
    a = _new_account(conn, "acct-a")
    b = _new_account(conn, "acct-b")
    _insert_lead(conn, a, "lead-A")
    _insert_lead(conn, b, "lead-B")

    assert _visible_lead_names(conn, a) == ["lead-A"]
    assert _visible_lead_names(conn, b) == ["lead-B"]


def test_no_account_context_sees_nothing(conn):
    a = _new_account(conn, "acct-a")
    _insert_lead(conn, a, "lead-A")
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_account_id', '', false)")
        cur.execute("SELECT count(*) FROM leads")
        assert cur.fetchone()[0] == 0


def test_cannot_insert_lead_for_another_account(conn):
    a = _new_account(conn, "acct-a")
    b = _new_account(conn, "acct-b")
    # Acting as A, try to write a row owned by B -> WITH CHECK must reject it.
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_account_id', %s, false)", (a,))
        with pytest.raises(psycopg.errors.Error):
            cur.execute("INSERT INTO leads (account_id, name) VALUES (%s, %s)", (b, "evil"))
    conn.rollback()
