"""AMZ_Designy - pytrends wrapper for Google Trends API calls."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError

from app.schemas import TrendEntry, TrendReport
from app.utils.retries import retry_with_backoff
from app.utils.geo_mapping import get_pytrends_pn, is_supported_geo, DEFAULT_PN
from app.utils.exceptions import (
    TrendsEmptyResultError,
    TrendsRateLimitError,
    TrendsAPIError,
)

logger = logging.getLogger(__name__)

# Seed keywords for degraded mode fallback
DEFAULT_SEED_KEYWORDS = [
    "t shirt design",
    "funny shirt",
    "graphic tee",
    "trending shirts",
    "popular apparel",
]


class PytrendsClient:
    """Robust wrapper around pytrends with retry logic, geo mapping, and fallbacks."""

    def __init__(self, hl: str = "en-US", tz: int = 360) -> None:
        self._hl = hl
        self._tz = tz

    def _new_session(self) -> TrendReq:
        return TrendReq(hl=self._hl, tz=self._tz)

    def _map_geo(self, geo: str) -> str:
        """Map ISO geo code to pytrends pn value with logging."""
        pn = get_pytrends_pn(geo)
        if not is_supported_geo(geo):
            logger.warning(
                "Geo '%s' not in supported mapping, using default '%s'",
                geo, DEFAULT_PN
            )
        else:
            logger.debug("Mapped geo '%s' to pn '%s'", geo, pn)
        return pn

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        exceptions=(ResponseError, TrendsAPIError),
    )
    async def _trending_searches_with_pn(self, pn: str) -> list[str]:
        """Internal method to call trending_searches with pn parameter."""
        pytrends = self._new_session()
        try:
            df = pytrends.trending_searches(pn=pn)
            return df[0].tolist() if not df.empty else []
        except ResponseError as e:
            if "404" in str(e):
                logger.error("trending_searches 404 for pn='%s': %s", pn, e)
                raise TrendsAPIError(f"Invalid pn value '{pn}': {e}") from e
            raise

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        exceptions=(ResponseError, TrendsAPIError),
    )
    async def _daily_trends_with_geo(self, geo: str) -> list[str]:
        """Fallback: try daily_trends endpoint with ISO geo code."""
        pytrends = self._new_session()
        try:
            # daily_trends uses ISO geo codes directly
            df = pytrends.daily_trends(geo=geo.upper())
            if df.empty:
                return []
            # Extract trending searches from the nested structure
            if "trendingSearches" in df.columns:
                queries = []
                for _, row in df.iterrows():
                    trending = row.get("trendingSearches", [])
                    if isinstance(trending, list):
                        for item in trending:
                            if isinstance(item, dict) and "title" in item:
                                queries.append(item["title"]["query"])
                return queries
            return []
        except ResponseError as e:
            logger.error("daily_trends failed for geo='%s': %s", geo, e)
            raise TrendsAPIError(f"daily_trends failed: {e}") from e

    async def trending_searches(
        self,
        geo: str,
        seed_keywords: list[str] | None = None,
    ) -> TrendReport:
        """Return trending searches for a country with fallback strategies.
        
        Strategy:
        1. Try trending_searches with mapped pn value
        2. If that fails, try daily_trends with ISO geo
        3. If all fails, return TrendReport from seed keywords (degraded mode)
        
        Args:
            geo: ISO country code (e.g., "US", "GB", "SA")
            seed_keywords: Fallback keywords for degraded mode
            
        Returns:
            TrendReport with discovered trends (may be from degraded mode)
        """
        from datetime import datetime
        
        seeds = seed_keywords or DEFAULT_SEED_KEYWORDS
        pn = self._map_geo(geo)
        
        logger.info(
            "Starting trend discovery for geo='%s' (pn='%s')",
            geo, pn
        )

        # Strategy 1: trending_searches with pn mapping
        try:
            queries = await self._trending_searches_with_pn(pn)
            if queries:
                logger.info(
                    "trending_searches succeeded: found %d queries for geo='%s'",
                    len(queries), geo
                )
                entries = [
                    TrendEntry(query=q, source="google_trends")
                    for q in queries[:20]
                ]
                return TrendReport(
                    entries=entries,
                    geo=geo,
                    timeframe="today 1-m",
                    created_at=datetime.now(),
                )
            logger.warning("trending_searches returned empty for geo='%s'", geo)
        except TrendsAPIError as e:
            logger.warning(
                "trending_searches failed for geo='%s': %s",
                geo, e
            )
        except Exception as e:
            logger.warning(
                "Unexpected error in trending_searches for geo='%s': %s",
                geo, e
            )

        # Strategy 2: daily_trends fallback
        logger.info("Trying daily_trends fallback for geo='%s'", geo)
        try:
            queries = await self._daily_trends_with_geo(geo)
            if queries:
                logger.info(
                    "daily_trends fallback succeeded: found %d queries for geo='%s'",
                    len(queries), geo
                )
                entries = [
                    TrendEntry(query=q, source="google_trends_daily")
                    for q in queries[:20]
                ]
                return TrendReport(
                    entries=entries,
                    geo=geo,
                    timeframe="today 1-m",
                    created_at=datetime.now(),
                )
            logger.warning("daily_trends returned empty for geo='%s'", geo)
        except Exception as e:
            logger.warning("daily_trends fallback failed for geo='%s': %s", geo, e)

        # Strategy 3: Degraded mode with seed keywords
        logger.warning(
            "All trends endpoints failed for geo='%s', using degraded mode with seeds",
            geo
        )
        entries = [
            TrendEntry(query=kw, source="seed_fallback")
            for kw in seeds[:10]
        ]
        return TrendReport(
            entries=entries,
            geo=geo,
            timeframe="today 1-m",
            created_at=datetime.now(),
        )

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def related_queries(
        self,
        keyword: str,
        geo: str,
        timeframe: str,
    ) -> list[str]:
        """Return top + rising related queries for *keyword*."""
        pytrends = self._new_session()
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
    async def interest_over_time(
        self,
        keyword: str,
        geo: str,
        timeframe: str,
    ) -> tuple[int, float]:
        """Return (avg_volume, growth_rate) for *keyword*.

        avg_volume is a rough scale estimate; growth_rate is the
        percent change between the first and second half of the window.
        Returns (0, 0.0) when data is unavailable.
        """
        pytrends = self._new_session()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        iot = pytrends.interest_over_time()
        if iot.empty or keyword not in iot.columns:
            return 0, 0.0

        series = iot[keyword]
        avg_volume = int(series.mean() * 1000)

        half = len(series) // 2
        if half > 0:
            first_half = series.iloc[:half].mean()
            second_half = series.iloc[half:].mean()
            growth = (
                round(((second_half - first_half) / first_half) * 100, 1)
                if first_half > 0
                else 0.0
            )
        else:
            growth = 0.0

        return avg_volume, growth
