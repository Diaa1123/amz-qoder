"""AMZ_Designy - Airtable read/write client via pyairtable."""

from __future__ import annotations

import logging
from datetime import date

from pyairtable import Api

from app.config import AppConfig
from app.schemas import (
    AirtableRowIdea,
    AirtableRowNiche,
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheEntry,
)
from app.utils.retries import retry_with_backoff

logger = logging.getLogger(__name__)


class AirtableClient:
    """Read/write to Airtable Ideas and Weekly Niche tables."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        api = Api(config.airtable_api_key.get_secret_value())
        self._ideas_table = api.table(
            config.airtable_base_id, config.airtable_table_id,
        )
        self._niche_table = api.table(
            config.airtable_base_id, config.airtable_niche_table_id,
        )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_idea_row(
        run_date: date,
        trend_name: str,
        idea: IdeaPackage,
        prompt: DesignPrompt,
        report: ComplianceReport,
    ) -> AirtableRowIdea:
        return AirtableRowIdea(
            run_date=run_date,
            trend_name=trend_name,
            niche_name=idea.niche_name,
            audience=idea.audience,
            opportunity_score=idea.opportunity_score,
            final_approved_title=idea.final_approved_title,
            final_approved_bullet_points="\n".join(
                idea.final_approved_bullet_points,
            ),
            final_approved_description=idea.final_approved_description,
            final_approved_keywords_tags=", ".join(
                idea.final_approved_keywords_tags,
            ),
            design_prompt=prompt.prompt_text,
            compliance_status=report.compliance_status,
            compliance_notes=report.compliance_notes,
            risk_terms_detected=", ".join(report.risk_terms_detected),
            design_style=idea.design_style,
            status="draft",
        )

    @staticmethod
    def _to_niche_row(
        entry: NicheEntry,
        week_start: date,
    ) -> AirtableRowNiche:
        growth = 0.0
        rising: str = "stable"
        # Derive growth / rising status from the score heuristics
        opp = entry.score.opportunity_score
        if opp >= 7.0:
            rising = "rising"
            growth = 25.0
        elif opp >= 5.0:
            rising = "stable"
            growth = 10.0
        else:
            rising = "declining"
            growth = -5.0

        return AirtableRowNiche(
            niche_name=entry.niche_name,
            week_start_date=week_start,
            weekly_growth_percent=growth,
            rising_status=rising,
            opportunity_score=opp,
            notes=entry.analysis_summary,
        )

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def write_idea(
        self,
        run_date: date,
        trend_name: str,
        idea: IdeaPackage,
        prompt: DesignPrompt,
        report: ComplianceReport,
    ) -> str:
        """Write an idea row to the Ideas table. Returns the record ID."""
        row = self._to_idea_row(run_date, trend_name, idea, prompt, report)
        fields = row.to_airtable_fields()
        logger.info("Writing idea to Airtable: %s", idea.niche_name)
        record = self._ideas_table.create(fields)
        record_id: str = record["id"]
        logger.info("Created Airtable Ideas record: %s", record_id)
        return record_id

    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    async def write_weekly_niche(
        self,
        entry: NicheEntry,
        week_start: date,
    ) -> str:
        """Write a niche row to the Weekly Niche table. Returns record ID."""
        row = self._to_niche_row(entry, week_start)
        fields = row.to_airtable_fields()
        logger.info("Writing niche to Airtable: %s", entry.niche_name)
        record = self._niche_table.create(fields)
        record_id: str = record["id"]
        logger.info("Created Airtable Niche record: %s", record_id)
        return record_id

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def read_weekly_niches(self, week_start: date) -> list[dict]:
        """Fetch all niche records for the given week."""
        formula = f"{{Week Start Date}} = '{week_start.isoformat()}'"
        records = self._niche_table.all(formula=formula)
        return [r["fields"] for r in records]
