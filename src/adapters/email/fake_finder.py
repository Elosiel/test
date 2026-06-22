"""Deterministic EmailFinderPort. Honesty rule: clearly fake — it derives a
plausible `info@<domain>` from the website and marks it verified. Returns None when
there is no website to derive from (mirrors a real finder's miss). Real Hunter/
site-crawl adapter swaps in behind this port.
"""
from __future__ import annotations

from urllib.parse import urlparse

from src.ports.email_finder import FoundEmail


class FakeEmailFinder:
    def find(self, *, business_name: str, website: str | None) -> FoundEmail | None:
        if not website:
            return None
        host = urlparse(website).netloc or website
        domain = host.split("@")[-1].lstrip("www.").strip("/")
        if not domain:
            return None
        return FoundEmail(email=f"info@{domain}", verified=True, source="fake")
