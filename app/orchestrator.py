"""AMZ_Designy - Pipeline orchestration."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from app.agents.designer import DesignerAgent
from app.agents.inspector import InspectorAgent
from app.agents.niche_analyzer import NicheAnalyzerAgent
from app.agents.strategist import StrategistAgent
from app.agents.trend_scout import TrendScoutAgent
from app.config import AppConfig
from app.integrations.airtable_client import AirtableClient
from app.io.outputs import OutputWriter
from app.schemas import NicheReport, TrendEntry, TrendReport

logger = logging.getLogger(__name__)

# Default seed keywords when none provided
_DEFAULT_SEEDS = [
    "funny shirt", "trending tee", "graphic t-shirt", "gift idea shirt",
]


async def run_daily(config: AppConfig) -> NicheReport:
    """Daily pipeline: TrendScout -> NicheAnalyzer -> Airtable Weekly Niche.

    Returns the NicheReport.
    """
    run_date = date.today()
    logger.info("Starting daily pipeline for %s", run_date)

    scout = TrendScoutAgent(config)
    analyzer = NicheAnalyzerAgent(config)
    airtable = AirtableClient(config)

    trend_report = await scout.discover_trends(seed_keywords=_DEFAULT_SEEDS)
    niche_report = await analyzer.analyze_trends(
        trend_report, min_score=config.min_niche_score,
    )

    # Derive week start (Monday of current week)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    for entry in niche_report.entries:
        try:
            await airtable.write_weekly_niche(entry, week_start)
        except Exception:
            logger.exception(
                "Failed to write niche '%s' to Airtable", entry.niche_name,
            )

    logger.info(
        "Daily pipeline done: %d niches written", len(niche_report.entries),
    )
    return niche_report


async def run_weekly(config: AppConfig) -> list[str]:
    """Weekly pipeline: full end-to-end for top niches.

    Returns list of Airtable record IDs for created ideas.
    """
    run_date = date.today()
    logger.info("Starting weekly pipeline for %s", run_date)

    # Phase 1: discover + score
    scout = TrendScoutAgent(config)
    analyzer = NicheAnalyzerAgent(config)

    trend_report = await scout.discover_trends(seed_keywords=_DEFAULT_SEEDS)
    niche_report = await analyzer.analyze_trends(
        trend_report, min_score=config.min_niche_score,
    )

    # Phase 2: run full pipeline for top N niches
    strategist = StrategistAgent(config)
    designer = DesignerAgent(config)
    inspector = InspectorAgent(config)
    writer = OutputWriter(config)
    airtable = AirtableClient(config)

    top_niches = niche_report.entries[: config.max_designs_per_run]
    record_ids: list[str] = []

    for idx, niche_entry in enumerate(top_niches, start=1):
        trend_name = niche_entry.trending_query
        try:
            idea = await strategist.create_idea_package(niche_entry)
            prompt = await designer.create_design_prompt(idea)
            report = await inspector.inspect(idea, prompt)

            # Always write local output first
            await writer.write_package(
                trend_name=trend_name,
                concept_index=idx,
                trend_report=trend_report,
                niche_report=niche_report,
                idea_package=idea,
                design_prompt=prompt,
                compliance_report=report,
            )

            # Then write to Airtable (only if approved)
            if report.compliance_status == "approved":
                rec_id = await airtable.write_idea(
                    run_date=run_date,
                    trend_name=trend_name,
                    idea=idea,
                    prompt=prompt,
                    report=report,
                )
                record_ids.append(rec_id)
            else:
                logger.info(
                    "Skipping Airtable for '%s' (status=%s)",
                    niche_entry.niche_name,
                    report.compliance_status,
                )
        except Exception:
            logger.exception(
                "Failed pipeline for niche '%s'", niche_entry.niche_name,
            )

    logger.info(
        "Weekly pipeline done: %d/%d ideas written to Airtable",
        len(record_ids),
        len(top_niches),
    )
    return record_ids


async def run_create(config: AppConfig, keyword: str) -> str:
    """On-demand pipeline for a single keyword.

    Returns the Airtable record ID (empty string if not approved).
    """
    run_date = date.today()
    logger.info("Starting create pipeline for keyword '%s'", keyword)

    # Synthetic TrendEntry
    trend_report = TrendReport(
        entries=[TrendEntry(query=keyword)],
        created_at=datetime.now(),
    )

    analyzer = NicheAnalyzerAgent(config)
    niche_report = await analyzer.analyze_trends(
        trend_report, min_score=0.0,  # accept any score for manual create
    )

    if not niche_report.entries:
        logger.warning("No niches generated for keyword '%s'", keyword)
        return ""

    niche_entry = niche_report.entries[0]
    trend_name = keyword

    strategist = StrategistAgent(config)
    designer = DesignerAgent(config)
    inspector = InspectorAgent(config)
    writer = OutputWriter(config)
    airtable = AirtableClient(config)

    idea = await strategist.create_idea_package(niche_entry)
    prompt = await designer.create_design_prompt(idea)
    report = await inspector.inspect(idea, prompt)

    # Write local output first
    await writer.write_package(
        trend_name=trend_name,
        concept_index=1,
        trend_report=trend_report,
        niche_report=niche_report,
        idea_package=idea,
        design_prompt=prompt,
        compliance_report=report,
    )

    # Then write to Airtable
    if report.compliance_status == "approved":
        rec_id = await airtable.write_idea(
            run_date=run_date,
            trend_name=trend_name,
            idea=idea,
            prompt=prompt,
            report=report,
        )
        logger.info("Create pipeline done: record %s", rec_id)
        return rec_id

    logger.info(
        "Create pipeline done: not approved (status=%s)",
        report.compliance_status,
    )
    return ""
