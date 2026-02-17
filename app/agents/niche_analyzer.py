"""AMZ_Designy - NicheAnalyzerAgent: score and filter trends."""

from __future__ import annotations

import logging
from datetime import datetime

from app.config import AppConfig
from app.integrations.poe_client import PoeClient
from app.schemas import (
    NicheEntry,
    NicheReport,
    NicheScore,
    TrendEntry,
    TrendReport,
)
from app.scoring.trend_scoring import (
    score_audience_size,
    score_commercial_intent,
    score_competition_level,
    score_designability,
    score_seasonality_risk,
    score_trademark_risk,
)

logger = logging.getLogger(__name__)


class NicheAnalyzerAgent:
    """Score and filter trends for Merch viability.

    Scoring is deterministic (rule-based). LLM summary is optional.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._poe = PoeClient(config)

    async def analyze_trends(
        self,
        trend_report: TrendReport,
        min_score: float = 6.5,
    ) -> NicheReport:
        """Score each trend entry and filter by min_score."""
        entries: list[NicheEntry] = []

        for trend in trend_report.entries:
            score = self._compute_niche_score(trend)
            if score.opportunity_score < min_score:
                logger.debug(
                    "Skipping '%s' (score %.2f < %.2f)",
                    trend.query,
                    score.opportunity_score,
                    min_score,
                )
                continue

            niche = NicheEntry(
                niche_name=trend.query.title(),
                trending_query=trend.query,
                score=score,
                audience="",
                analysis_summary="",
            )

            # Optional LLM summary (informational only)
            summary = await self._generate_llm_summary(niche)
            niche = niche.model_copy(
                update={
                    "audience": summary.get("audience", "General consumers"),
                    "analysis_summary": summary.get("summary", ""),
                },
            )
            entries.append(niche)

        # Sort by opportunity score descending
        entries.sort(
            key=lambda e: e.score.opportunity_score, reverse=True,
        )

        logger.info(
            "NicheAnalyzer: %d/%d entries passed (min_score=%.1f)",
            len(entries),
            len(trend_report.entries),
            min_score,
        )
        return NicheReport(entries=entries, created_at=datetime.now())

    def _compute_niche_score(self, entry: TrendEntry) -> NicheScore:
        """Deterministic scoring from data signals only."""
        return NicheScore(
            commercial_intent=score_commercial_intent(entry),
            designability=score_designability(entry),
            audience_size=score_audience_size(entry),
            competition_level=score_competition_level(entry),
            seasonality_risk=score_seasonality_risk(entry),
            trademark_risk=score_trademark_risk(entry),
        )

    async def _generate_llm_summary(
        self,
        entry: NicheEntry,
    ) -> dict[str, str]:
        """Optional LLM call for a human-readable summary.

        Does NOT influence the score. Returns dict with 'audience' and
        'summary' keys. Falls back to empty strings on failure.
        """
        try:
            prompt = (
                f"Niche: {entry.niche_name}\n"
                f"Query: {entry.trending_query}\n"
                f"Opportunity Score: {entry.score.opportunity_score}\n\n"
                "Provide a 2-sentence analysis summary and a one-line "
                "target audience description for this Amazon Merch niche.\n"
                'Respond as JSON: {{"audience": "...", "summary": "..."}}'
            )
            import json

            raw = await self._poe.call_llm_text(
                system_prompt="You are a niche analysis assistant.",
                user_message=prompt,
            )
            return json.loads(raw)
        except Exception:
            logger.warning(
                "LLM summary failed for '%s', using empty", entry.niche_name,
            )
            return {"audience": "General consumers", "summary": ""}
