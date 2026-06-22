"""EmailFinderPort — find (and verify) a contact email for a business. Start with a
free/site-crawl source; swappable to Hunter/Dropcontact behind this port.

``verified`` must be True before any send — the core never sends to an unverified
address. The finder returns None when no email could be found.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FoundEmail:
    email: str
    verified: bool
    source: str


class EmailFinderPort(Protocol):
    def find(self, *, business_name: str, website: str | None) -> FoundEmail | None: ...
