"""DataProviderPort — business discovery. Start adapter: Outscraper. Swappable to
SerpAPI/DataForSEO behind this same port. The core never imports a vendor SDK.
"""
from __future__ import annotations

from typing import Protocol

from src.domain.entities import Business


class DataProviderPort(Protocol):
    def search(self, niche: str, city: str, limit: int) -> list[Business]:
        """Return up to ``limit`` businesses for ``{niche} in {city}``.

        Implementations must raise on failure (never return partial-as-complete);
        the caller bills only after results are persisted.
        """
        ...
