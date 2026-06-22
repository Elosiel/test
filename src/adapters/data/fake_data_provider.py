"""A deterministic in-process DataProviderPort. Honesty rule: this is clearly
labelled fake data, never presented as real. It lets the spine run end-to-end and
back the application tests before the Outscraper adapter exists.
"""
from __future__ import annotations

from src.domain.entities import Business


class FakeDataProvider:
    """Generates ``limit`` synthetic businesses for any niche+city."""

    def search(self, niche: str, city: str, limit: int) -> list[Business]:
        return [
            Business(
                name=f"{niche.title()} Co #{i} ({city.title()})",
                category=niche,
                address=f"{100 + i} Main St, {city.title()}",
                phone=f"+1-555-01{i:02d}",
                website=f"https://example.test/{niche}/{i}",
                rating=round(3.0 + (i % 5) * 0.4, 1),
                review_count=10 + i,
                source="fake",
                external_id=f"fake-{niche}-{city}-{i}",
            )
            for i in range(limit)
        ]
