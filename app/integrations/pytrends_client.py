"""AMZ_Designy - pytrends wrapper for Google Trends API calls."""

from __future__ import annotations

import logging

from pytrends.request import TrendReq

from app.utils.retries import retry_with_backoff

logger = logging.getLogger(__name__)


class PytrendsClient:
    """Thin wrapper around pytrends with retry logic."""

    def __init__(self, hl: str = "en-US", tz: int = 360) -> None:
        self._hl = hl
        self._tz = tz

    def _new_session(self) -> TrendReq:
        return TrendReq(hl=self._hl, tz=self._tz)

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def trending_searches(self, geo: str) -> list[str]:
        """Return top trending searches for a country."""
        pytrends = self._new_session()
        df = pytrends.trending_searches(pn=geo.lower())
        return df[0].tolist() if not df.empty else []

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
