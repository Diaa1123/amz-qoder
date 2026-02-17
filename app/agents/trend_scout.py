"""AMZ_Designy - TrendScoutAgent: discover trends via pytrends."""

from __future__ import annotations

import logging
from datetime import datetime

from app.config import AppConfig
from app.integrations.pytrends_client import PytrendsClient
from app.schemas import TrendEntry, TrendReport

logger = logging.getLogger(__name__)


class TrendScoutAgent:
    """Discover trending search queries from Google Trends."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._pytrends = PytrendsClient()

    async def discover_trends(
        self,
        seed_keywords: list[str],
        geo: str = "US",
        timeframe: str = "today 1-m",
    ) -> TrendReport:
        """Run trend discovery for the given seed keywords.

        Returns a TrendReport with up to 20 entries.
        """
        entries: list[TrendEntry] = []

        # 1. Trending searches (country-level)
        trending = await self._pytrends.trending_searches(geo)
        for query in trending[:10]:
            entries.append(TrendEntry(query=query, source="google_trends"))

        # 2. Related queries for each seed keyword
        for kw in seed_keywords:
            related = await self._pytrends.related_queries(kw, geo, timeframe)
            for query in related:
                if not any(e.query == query for e in entries):
                    entries.append(
                        TrendEntry(query=query, source="google_trends"),
                    )

        # 3. Enrich entries with volume / growth data
        enriched: list[TrendEntry] = []
        for entry in entries[:20]:
            enriched_entry = await self._enrich_entry(entry, geo, timeframe)
            enriched.append(enriched_entry)

        logger.info("TrendScout discovered %d entries", len(enriched))
        return TrendReport(
            entries=enriched,
            geo=geo,
            timeframe=timeframe,
            created_at=datetime.now(),
        )

    async def _enrich_entry(
        self,
        entry: TrendEntry,
        geo: str,
        timeframe: str,
    ) -> TrendEntry:
        """Add volume and growth_rate to a TrendEntry."""
        try:
            avg_volume, growth = await self._pytrends.interest_over_time(
                entry.query, geo, timeframe,
            )
            if avg_volume == 0 and growth == 0.0:
                return entry

            return TrendEntry(
                query=entry.query,
                volume=avg_volume,
                growth_rate=growth,
                category=entry.category,
                source=entry.source,
            )
        except Exception:
            logger.warning(
                "Failed to enrich entry '%s', returning as-is", entry.query,
            )
            return entry
