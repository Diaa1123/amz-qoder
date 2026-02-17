"""Integration tests for the orchestrator pipelines with all externals mocked."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.designer import _DesignLLMResponse
from app.agents.inspector import _ComplianceLLMResponse
from app.agents.strategist import _StrategyLLMResponse
from app.orchestrator import run_create, run_daily, run_weekly
from app.schemas import NicheReport, TrendReport


def _make_config(tmp_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.poe_access_key.get_secret_value.return_value = "test-key"
    cfg.airtable_api_key.get_secret_value.return_value = "test-key"
    cfg.airtable_base_id = "appTEST"
    cfg.airtable_table_id = "tblTEST"
    cfg.airtable_niche_table_id = "tblNICHE"
    cfg.llm_model = "gpt-4o"
    cfg.max_tokens = 4000
    cfg.temperature = 0.7
    cfg.min_niche_score = 0.0  # accept all for testing
    cfg.max_designs_per_run = 2
    cfg.output_dir = tmp_path
    return cfg


def _mock_pytrends():
    """Return a mock PytrendsClient."""
    mock = MagicMock()
    mock.trending_searches = AsyncMock(
        return_value=["funny cat shirt", "retro gaming tee"],
    )
    mock.related_queries = AsyncMock(return_value=["pixel art tee"])
    mock.interest_over_time = AsyncMock(return_value=(50000, 25.0))
    return mock


def _mock_poe_client():
    """Return a mock PoeClient that returns valid typed responses."""
    mock = MagicMock()
    mock.call_llm_text = AsyncMock(
        return_value='{"audience": "Gamers aged 25-45", "summary": "Strong niche."}',
    )

    async def call_llm_side_effect(system_prompt, user_message, response_model):
        if response_model is _StrategyLLMResponse:
            return _StrategyLLMResponse(
                title="Retro Arcade Gamer Tee",
                bullet_points=[
                    "Classic 8-bit design",
                    "Soft cotton blend",
                    "Vibrant retro colors",
                    "Great for gamers",
                    "High quality print",
                ],
                description="A retro gaming t-shirt for arcade fans.",
                keywords=["retro", "gaming", "arcade", "pixel", "tee"],
                design_style="pixel art, 8-bit retro",
            )
        elif response_model is _DesignLLMResponse:
            return _DesignLLMResponse(
                prompt_text="Vibrant pixel art arcade design on transparent bg.",
                color_mood_notes="Electric cyan, neon pink.",
            )
        elif response_model is _ComplianceLLMResponse:
            return _ComplianceLLMResponse(
                compliant=True,
                issues=[],
                notes="Content is fully compliant.",
            )
        raise ValueError(f"Unexpected response_model: {response_model}")

    mock.call_llm = AsyncMock(side_effect=call_llm_side_effect)
    return mock


def _mock_airtable():
    """Return a mock AirtableClient."""
    mock = MagicMock()
    mock.write_idea = AsyncMock(return_value="rec_test_123")
    mock.write_weekly_niche = AsyncMock(return_value="rec_niche_456")
    return mock


# ---------------------------------------------------------------------------
# run_daily
# ---------------------------------------------------------------------------

class TestRunDaily:
    @pytest.mark.asyncio
    async def test_daily_returns_niche_report(self, tmp_path: Path):
        config = _make_config(tmp_path)

        with (
            patch("app.orchestrator.TrendScoutAgent") as MockScout,
            patch("app.orchestrator.NicheAnalyzerAgent") as MockAnalyzer,
            patch("app.orchestrator.AirtableClient") as MockAirtable,
        ):
            mock_pytrends = _mock_pytrends()
            mock_poe = _mock_poe_client()

            from app.schemas import TrendEntry

            scout = MockScout.return_value
            scout.discover_trends = AsyncMock(
                return_value=TrendReport(
                    entries=[
                        TrendEntry(query="funny cat shirt", volume=50000, growth_rate=25.0),
                    ],
                    created_at=datetime.now(),
                ),
            )

            analyzer = MockAnalyzer.return_value
            analyzer.analyze_trends = AsyncMock(
                return_value=NicheReport(entries=[], created_at=datetime.now()),
            )

            airtable = MockAirtable.return_value
            airtable.write_weekly_niche = AsyncMock(return_value="rec_123")

            report = await run_daily(config)

            assert isinstance(report, NicheReport)
            scout.discover_trends.assert_called_once()
            analyzer.analyze_trends.assert_called_once()


# ---------------------------------------------------------------------------
# run_weekly
# ---------------------------------------------------------------------------

class TestRunWeekly:
    @pytest.mark.asyncio
    async def test_weekly_returns_record_ids(self, tmp_path: Path):
        config = _make_config(tmp_path)

        with (
            patch("app.orchestrator.TrendScoutAgent") as MockScout,
            patch("app.orchestrator.NicheAnalyzerAgent") as MockAnalyzer,
            patch("app.orchestrator.StrategistAgent") as MockStrategist,
            patch("app.orchestrator.DesignerAgent") as MockDesigner,
            patch("app.orchestrator.InspectorAgent") as MockInspector,
            patch("app.orchestrator.OutputWriter") as MockWriter,
            patch("app.orchestrator.AirtableClient") as MockAirtable,
        ):
            from app.schemas import (
                ComplianceReport,
                DesignPrompt,
                IdeaPackage,
                NicheEntry,
                NicheScore,
            )

            niche_entry = NicheEntry(
                niche_name="Funny Cat",
                trending_query="funny cat shirt",
                score=NicheScore(
                    commercial_intent=9, designability=8, audience_size=8,
                    competition_level=4, seasonality_risk=3, trademark_risk=2,
                ),
                audience="Cat lovers",
                analysis_summary="Strong niche.",
            )

            scout = MockScout.return_value
            scout.discover_trends = AsyncMock(
                return_value=TrendReport(entries=[], created_at=datetime.now()),
            )

            analyzer = MockAnalyzer.return_value
            analyzer.analyze_trends = AsyncMock(
                return_value=NicheReport(
                    entries=[niche_entry],
                    created_at=datetime.now(),
                ),
            )

            strategist = MockStrategist.return_value
            strategist.create_idea_package = AsyncMock(
                return_value=IdeaPackage(
                    niche_name="Funny Cat",
                    audience="Cat lovers",
                    opportunity_score=8.0,
                    final_approved_title="Funny Cat Tee",
                    final_approved_bullet_points=["Cute", "Soft", "Fun", "Gift", "Quality"],
                    final_approved_description="A funny cat tee.",
                    final_approved_keywords_tags=["cat", "funny", "tee"],
                    design_style="cartoon, bright",
                    created_at=datetime.now(),
                ),
            )

            designer = MockDesigner.return_value
            designer.create_design_prompt = AsyncMock(
                return_value=DesignPrompt(
                    idea_niche_name="Funny Cat",
                    prompt_text="Cute cartoon cat.",
                    design_style="cartoon, bright",
                    color_mood_notes="Warm pastels.",
                    created_at=datetime.now(),
                ),
            )

            inspector = MockInspector.return_value
            inspector.inspect = AsyncMock(
                return_value=ComplianceReport(
                    idea_niche_name="Funny Cat",
                    compliance_status="approved",
                    compliance_notes="All clear.",
                    risk_terms_detected=[],
                    created_at=datetime.now(),
                ),
            )

            writer = MockWriter.return_value
            writer.write_package = AsyncMock(return_value=tmp_path)

            airtable = MockAirtable.return_value
            airtable.write_idea = AsyncMock(return_value="rec_weekly_789")

            record_ids = await run_weekly(config)

            assert isinstance(record_ids, list)
            assert "rec_weekly_789" in record_ids
            writer.write_package.assert_called_once()
            airtable.write_idea.assert_called_once()


# ---------------------------------------------------------------------------
# run_create
# ---------------------------------------------------------------------------

class TestRunCreate:
    @pytest.mark.asyncio
    async def test_create_returns_record_id(self, tmp_path: Path):
        config = _make_config(tmp_path)

        with (
            patch("app.orchestrator.NicheAnalyzerAgent") as MockAnalyzer,
            patch("app.orchestrator.StrategistAgent") as MockStrategist,
            patch("app.orchestrator.DesignerAgent") as MockDesigner,
            patch("app.orchestrator.InspectorAgent") as MockInspector,
            patch("app.orchestrator.OutputWriter") as MockWriter,
            patch("app.orchestrator.AirtableClient") as MockAirtable,
        ):
            from app.schemas import (
                ComplianceReport,
                DesignPrompt,
                IdeaPackage,
                NicheEntry,
                NicheScore,
            )

            niche_entry = NicheEntry(
                niche_name="Custom Keyword",
                trending_query="custom keyword",
                score=NicheScore(
                    commercial_intent=7, designability=7, audience_size=5,
                    competition_level=5, seasonality_risk=3, trademark_risk=2,
                ),
                audience="General",
                analysis_summary="Custom niche.",
            )

            analyzer = MockAnalyzer.return_value
            analyzer.analyze_trends = AsyncMock(
                return_value=NicheReport(
                    entries=[niche_entry],
                    created_at=datetime.now(),
                ),
            )

            strategist = MockStrategist.return_value
            strategist.create_idea_package = AsyncMock(
                return_value=IdeaPackage(
                    niche_name="Custom Keyword",
                    audience="General",
                    opportunity_score=6.5,
                    final_approved_title="Custom Keyword Tee",
                    final_approved_bullet_points=["A", "B", "C", "D", "E"],
                    final_approved_description="A custom tee.",
                    final_approved_keywords_tags=["custom", "tee"],
                    design_style="modern",
                    created_at=datetime.now(),
                ),
            )

            designer = MockDesigner.return_value
            designer.create_design_prompt = AsyncMock(
                return_value=DesignPrompt(
                    idea_niche_name="Custom Keyword",
                    prompt_text="Modern clean design.",
                    design_style="modern",
                    color_mood_notes="Cool blues.",
                    created_at=datetime.now(),
                ),
            )

            inspector = MockInspector.return_value
            inspector.inspect = AsyncMock(
                return_value=ComplianceReport(
                    idea_niche_name="Custom Keyword",
                    compliance_status="approved",
                    compliance_notes="All clear.",
                    risk_terms_detected=[],
                    created_at=datetime.now(),
                ),
            )

            writer = MockWriter.return_value
            writer.write_package = AsyncMock(return_value=tmp_path)

            airtable = MockAirtable.return_value
            airtable.write_idea = AsyncMock(return_value="rec_create_abc")

            rec_id = await run_create(config, "custom keyword")

            assert rec_id == "rec_create_abc"
            writer.write_package.assert_called_once()
            airtable.write_idea.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_returns_empty_when_not_approved(self, tmp_path: Path):
        config = _make_config(tmp_path)

        with (
            patch("app.orchestrator.NicheAnalyzerAgent") as MockAnalyzer,
            patch("app.orchestrator.StrategistAgent") as MockStrategist,
            patch("app.orchestrator.DesignerAgent") as MockDesigner,
            patch("app.orchestrator.InspectorAgent") as MockInspector,
            patch("app.orchestrator.OutputWriter") as MockWriter,
            patch("app.orchestrator.AirtableClient") as MockAirtable,
        ):
            from app.schemas import (
                ComplianceReport,
                DesignPrompt,
                IdeaPackage,
                NicheEntry,
                NicheScore,
            )

            niche_entry = NicheEntry(
                niche_name="Rejected Niche",
                trending_query="rejected",
                score=NicheScore(
                    commercial_intent=5, designability=5, audience_size=5,
                    competition_level=5, seasonality_risk=5, trademark_risk=5,
                ),
                audience="Test",
                analysis_summary="Test.",
            )

            analyzer = MockAnalyzer.return_value
            analyzer.analyze_trends = AsyncMock(
                return_value=NicheReport(
                    entries=[niche_entry],
                    created_at=datetime.now(),
                ),
            )

            strategist = MockStrategist.return_value
            strategist.create_idea_package = AsyncMock(
                return_value=IdeaPackage(
                    niche_name="Rejected Niche",
                    audience="Test",
                    opportunity_score=5.0,
                    final_approved_title="Test Tee",
                    final_approved_bullet_points=["A"],
                    final_approved_description="Test.",
                    final_approved_keywords_tags=["test"],
                    design_style="basic",
                    created_at=datetime.now(),
                ),
            )

            designer = MockDesigner.return_value
            designer.create_design_prompt = AsyncMock(
                return_value=DesignPrompt(
                    idea_niche_name="Rejected Niche",
                    prompt_text="Basic design.",
                    design_style="basic",
                    created_at=datetime.now(),
                ),
            )

            inspector = MockInspector.return_value
            inspector.inspect = AsyncMock(
                return_value=ComplianceReport(
                    idea_niche_name="Rejected Niche",
                    compliance_status="rejected",
                    compliance_notes="Failed checks.",
                    risk_terms_detected=["bad"],
                    created_at=datetime.now(),
                ),
            )

            writer = MockWriter.return_value
            writer.write_package = AsyncMock(return_value=tmp_path)

            airtable = MockAirtable.return_value
            airtable.write_idea = AsyncMock()

            rec_id = await run_create(config, "rejected")

            assert rec_id == ""
            # Writer should still be called (local output always written)
            writer.write_package.assert_called_once()
            # Airtable should NOT be called for rejected content
            airtable.write_idea.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_returns_empty_when_no_niches(self, tmp_path: Path):
        config = _make_config(tmp_path)

        with (
            patch("app.orchestrator.NicheAnalyzerAgent") as MockAnalyzer,
        ):
            analyzer = MockAnalyzer.return_value
            analyzer.analyze_trends = AsyncMock(
                return_value=NicheReport(
                    entries=[],
                    created_at=datetime.now(),
                ),
            )

            rec_id = await run_create(config, "empty keyword")
            assert rec_id == ""
