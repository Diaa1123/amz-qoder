"""AMZ_Designy - TrendScoutAgent: discover trends via pytrends."""

from __future__ import annotations

import logging
from datetime import datetime

from pytrends.request import TrendReq

from app.config import AppConfig
from app.schemas import TrendEntry, TrendReport
from app.utils.retries import retry_with_backoff

logger = logging.getLogger(__name__)


class TrendScoutAgent:
    """Discover trending search queries from Google Trends."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

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
        trending = await self._fetch_trending_searches(geo)
        for query in trending[:10]:
            entries.append(TrendEntry(query=query, source="google_trends"))

        # 2. Related queries for each seed keyword
        for kw in seed_keywords:
            related = await self._fetch_related_queries(kw, geo, timeframe)
            for query in related:
                if not any(e.query == query for e in entries):
                    entries.append(
                        TrendEntry(query=query, source="google_trends"),
                    )

        # 3. Enrich entries with volume / growth data
        enriched: list[TrendEntry] = []
        for entry in entries[:20]:
            enriched_entry = await self._enrich_entry(
                entry, geo, timeframe,
            )
            enriched.append(enriched_entry)

        logger.info("TrendScout discovered %d entries", len(enriched))
        return TrendReport(
            entries=enriched,
            geo=geo,
            timeframe=timeframe,
            created_at=datetime.now(),
        )

    # ------------------------------------------------------------------
    # pytrends helpers
    # ------------------------------------------------------------------

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def _fetch_trending_searches(self, geo: str) -> list[str]:
        pytrends = TrendReq(hl="en-US", tz=360)
        df = pytrends.trending_searches(pn=geo.lower())
        return df[0].tolist() if not df.empty else []

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def _fetch_related_queries(
        self,
        keyword: str,
        geo: str,
        timeframe: str,
    ) -> list[str]:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        related = pytrends.related_queries()
        queries: list[str] = []
        if keyword in related:
            top = related[keyword].get("top")
            if top is not None and not top.empty:
                queries.extend(top["query"].tolist()[:5])
            rising = related[keyword].get("rising")
            if rising is not None and not rising.empty:
                queries.extend(rising["query"].tolist()[:5])
        return queries

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def _enrich_entry(
        self,
        entry: TrendEntry,
        geo: str,
        timeframe: str,
    ) -> TrendEntry:
        """Add volume and growth_rate to a TrendEntry via interest_over_time."""
        try:
            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload(
                [entry.query], timeframe=timeframe, geo=geo,
            )
            iot = pytrends.interest_over_time()
            if iot.empty or entry.query not in iot.columns:
                return entry

            series = iot[entry.query]
            avg_volume = int(series.mean() * 1000)  # rough scale

            # Growth rate: compare last week vs first week
            half = len(series) // 2
            if half > 0:
                first_half = series.iloc[:half].mean()
                second_half = series.iloc[half:].mean()
                if first_half > 0:
                    growth = round(
                        ((second_half - first_half) / first_half) * 100, 1,
                    )
                else:
                    growth = 0.0
            else:
                growth = 0.0

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
