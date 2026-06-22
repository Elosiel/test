"""Postgres UnitOfWork (psycopg 3). One database transaction per ``with`` block.

RLS model: each transaction sets the GUC ``app.current_account_id`` via
``SET LOCAL``; the policies in db/schema.sql scope every row to it. Because the
tables use FORCE ROW LEVEL SECURITY, even the table owner is subject to the
policies — so the boundary holds regardless of the connecting role.

This adapter is intentionally thin; the contract/integration tests carry the
weight of proving it behaves like the in-memory UnitOfWork.
"""
from __future__ import annotations

import json

import psycopg

from src.domain.entities import CreditLedgerEntry, Lead, LeadStatus, Run


class _LeadRepo:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def add(self, lead: Lead) -> None:
        self._cur.execute(
            """
            INSERT INTO leads (id, account_id, run_id, name, category, address, phone,
                               website, email, email_verified, rating, review_count,
                               opportunity, fit, confidence, rank, primary_gap,
                               hot_signal, fresh_pain_json, pitch, status, source, created_at)
            VALUES (%(id)s, %(account_id)s, %(run_id)s, %(name)s, %(category)s, %(address)s,
                    %(phone)s, %(website)s, %(email)s, %(email_verified)s, %(rating)s,
                    %(review_count)s, %(opportunity)s, %(fit)s, %(confidence)s, %(rank)s,
                    %(primary_gap)s, %(hot_signal)s, %(fresh_pain)s, %(pitch)s, %(status)s,
                    %(source)s, %(created_at)s)
            """,
            {
                "id": lead.id,
                "account_id": lead.account_id,
                "run_id": lead.run_id,
                "name": lead.name,
                "category": lead.category,
                "address": lead.address,
                "phone": lead.phone,
                "website": lead.website,
                "email": lead.email,
                "email_verified": lead.email_verified,
                "rating": lead.rating,
                "review_count": lead.review_count,
                "opportunity": lead.opportunity,
                "fit": lead.fit,
                "confidence": lead.confidence,
                "rank": lead.rank,
                "primary_gap": lead.primary_gap,
                "hot_signal": lead.hot_signal,
                "fresh_pain": json.dumps(lead.fresh_pain) if lead.fresh_pain else None,
                "pitch": lead.pitch,
                "status": lead.status.value,
                "source": lead.source,
                "created_at": lead.created_at,
            },
        )

    def list_for_account(self, account_id: str) -> list[Lead]:
        # RLS already scopes to the current account; account_id arg is a belt-and-braces filter.
        self._cur.execute(
            "SELECT id, account_id, run_id, name, category, rating, review_count, "
            "opportunity, fit, confidence, rank, status, source "
            "FROM leads WHERE account_id = %s ORDER BY rank DESC, created_at",
            (account_id,),
        )
        rows = self._cur.fetchall()
        return [
            Lead(
                id=r[0], account_id=r[1], run_id=r[2], name=r[3], category=r[4],
                rating=float(r[5]) if r[5] is not None else None, review_count=r[6],
                opportunity=r[7], fit=r[8], confidence=r[9], rank=float(r[10]),
                status=LeadStatus(r[11]), source=r[12],
            )
            for r in rows
        ]


class _RunRepo:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def add(self, run: Run) -> None:
        self._cur.execute(
            """
            INSERT INTO runs (id, account_id, territory_id, "limit", cost_credits,
                              summary_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (run.id, run.account_id, run.territory_id, run.limit, run.cost_credits,
             json.dumps(run.summary), run.created_at),
        )


class _CreditRepo:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def record(self, entry: CreditLedgerEntry) -> None:
        self._cur.execute(
            """
            INSERT INTO credit_ledger (id, account_id, delta, reason, stripe_event_id,
                                       balance_after, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (entry.id, entry.account_id, entry.delta, entry.reason,
             entry.stripe_event_id, entry.balance_after, entry.created_at),
        )

    def balance(self, account_id: str) -> int:
        self._cur.execute(
            "SELECT COALESCE(SUM(delta), 0) FROM credit_ledger WHERE account_id = %s",
            (account_id,),
        )
        return int(self._cur.fetchone()[0])


class PostgresUnitOfWork:
    """Opens a connection + transaction per ``with`` block, scoped to one account."""

    def __init__(self, dsn: str, account_id: str) -> None:
        self._dsn = dsn
        self._account_id = account_id

    def __enter__(self) -> "PostgresUnitOfWork":
        self._conn = psycopg.connect(self._dsn)
        self._cur = self._conn.cursor()
        # Scope this transaction to the account for RLS. SET LOCAL is transaction-bound.
        self._cur.execute(
            "SELECT set_config('app.current_account_id', %s, true)", (self._account_id,)
        )
        self.leads = _LeadRepo(self._cur)
        self.runs = _RunRepo(self._cur)
        self.credits = _CreditRepo(self._cur)
        self._committed = False
        return self

    def commit(self) -> None:
        self._conn.commit()
        self._committed = True

    def rollback(self) -> None:
        self._conn.rollback()

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if not self._committed:
                self.rollback()
        finally:
            self._cur.close()
            self._conn.close()
        return False
