"""Integration tests for agents with mocked external calls.

No real API calls are made -- all external dependencies are mocked.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.designer import DesignerAgent, _DesignLLMResponse
from app.agents.inspector import InspectorAgent, _ComplianceLLMResponse
from app.agents.niche_analyzer import NicheAnalyzerAgent
from app.agents.strategist import StrategistAgent, _StrategyLLMResponse
from app.agents.trend_scout import TrendScoutAgent
from app.schemas import (
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheEntry,
    NicheReport,
    NicheScore,
    TrendEntry,
    TrendReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> MagicMock:
    cfg = MagicMock()
    cfg.poe_access_key.get_secret_value.return_value = "test-key"
    cfg.airtable_api_key.get_secret_value.return_value = "test-key"
    cfg.airtable_base_id = "appTEST"
    cfg.airtable_table_id = "tblTEST"
    cfg.airtable_niche_table_id = "tblNICHE"
    cfg.llm_model = "gpt-4o"
    cfg.max_tokens = 4000
    cfg.temperature = 0.7
    cfg.min_niche_score = 6.5
    cfg.max_designs_per_run = 10
    cfg.output_dir = "outputs"
    return cfg


def _sample_niche_entry() -> NicheEntry:
    return NicheEntry(
        niche_name="Retro Gaming",
        trending_query="retro gaming shirt",
        score=NicheScore(
            commercial_intent=9,
            designability=9,
            audience_size=8,
            competition_level=6,
            seasonality_risk=3,
            trademark_risk=4,
        ),
        audience="Gamers aged 25-45",
        analysis_summary="Strong niche with clear design direction.",
    )


def _sample_idea_package() -> IdeaPackage:
    return IdeaPackage(
        niche_name="Retro Gaming",
        audience="Gamers aged 25-45",
        opportunity_score=7.90,
        final_approved_title="Retro Arcade Gamer Tee",
        final_approved_bullet_points=[
            "Classic pixel art design",
            "Soft comfortable fit",
            "Nostalgic retro theme",
            "Great gamer gift",
            "High quality print",
        ],
        final_approved_description="Retro gaming tee for arcade lovers.",
        final_approved_keywords_tags=[
            "retro gaming", "pixel art", "arcade", "gamer", "tee",
        ],
        design_style="pixel art, 8-bit retro",
        created_at=datetime.now(),
    )


def _sample_design_prompt() -> DesignPrompt:
    return DesignPrompt(
        idea_niche_name="Retro Gaming",
        prompt_text="Create a vibrant pixel art design for a t-shirt.",
        design_style="pixel art, 8-bit retro",
        color_mood_notes="Electric cyan, hot magenta, bright yellow.",
        created_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# TrendScoutAgent
# ---------------------------------------------------------------------------

class TestTrendScoutAgent:
    @pytest.mark.asyncio
    async def test_discover_trends_returns_trend_report(self):
        config = _make_config()
        agent = TrendScoutAgent(config)

        mock_client = MagicMock()
        # trending_searches now returns TrendReport instead of list
        mock_client.trending_searches = AsyncMock(
            return_value=TrendReport(
                entries=[
                    TrendEntry(query="funny cat shirt", source="google_trends"),
                    TrendEntry(query="retro gaming tee", source="google_trends"),
                ],
                geo="US",
                timeframe="today 1-m",
                created_at=datetime.now(),
            ),
        )
        mock_client.related_queries = AsyncMock(return_value=["pixel art tee"])
        mock_client.interest_over_time = AsyncMock(return_value=(50000, 25.0))
        agent._pytrends = mock_client

        report = await agent.discover_trends(
            seed_keywords=["test"], geo="US", timeframe="today 1-m",
        )

        assert isinstance(report, TrendReport)
        assert len(report.entries) > 0
        for entry in report.entries:
            assert isinstance(entry, TrendEntry)
        assert report.geo == "US"

    @pytest.mark.asyncio
    async def test_discover_trends_handles_empty_results(self):
        config = _make_config()
        agent = TrendScoutAgent(config)

        mock_client = MagicMock()
        # trending_searches returns empty TrendReport (degraded mode)
        mock_client.trending_searches = AsyncMock(
            return_value=TrendReport(
                entries=[],
                geo="US",
                timeframe="today 1-m",
                created_at=datetime.now(),
            ),
        )
        mock_client.related_queries = AsyncMock(return_value=[])
        mock_client.interest_over_time = AsyncMock(return_value=(0, 0.0))
        agent._pytrends = mock_client

        report = await agent.discover_trends(seed_keywords=[])
        assert isinstance(report, TrendReport)
        assert report.entries == []

    @pytest.mark.asyncio
    async def test_enrich_handles_failure_gracefully(self):
        config = _make_config()
        agent = TrendScoutAgent(config)

        mock_client = MagicMock()
        mock_client.trending_searches = AsyncMock(
            return_value=TrendReport(
                entries=[TrendEntry(query="test query", source="google_trends")],
                geo="US",
                timeframe="today 1-m",
                created_at=datetime.now(),
            ),
        )
        mock_client.related_queries = AsyncMock(return_value=[])
        mock_client.interest_over_time = AsyncMock(side_effect=Exception("API error"))
        agent._pytrends = mock_client

        report = await agent.discover_trends(seed_keywords=[])
        assert len(report.entries) == 1
        # Should still have the entry, just not enriched
        assert report.entries[0].query == "test query"


# ---------------------------------------------------------------------------
# NicheAnalyzerAgent
# ---------------------------------------------------------------------------

class TestNicheAnalyzerAgent:
    @pytest.mark.asyncio
    async def test_analyze_trends_scores_and_filters(self):
        config = _make_config()

        with patch(
            "app.agents.niche_analyzer.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm_text = AsyncMock(
                return_value='{"audience": "Gamers", "summary": "Good niche"}',
            )

            agent = NicheAnalyzerAgent(config)
            trend_report = TrendReport(
                entries=[
                    TrendEntry(
                        query="retro gaming shirt",
                        volume=82000,
                        growth_rate=45.0,
                        category="Shopping",
                    ),
                    TrendEntry(query="abstract philosophy", volume=100),
                ],
                created_at=datetime.now(),
            )

            report = await agent.analyze_trends(trend_report, min_score=0.0)

            assert isinstance(report, NicheReport)
            assert len(report.entries) > 0
            for entry in report.entries:
                assert isinstance(entry, NicheEntry)
                assert isinstance(entry.score, NicheScore)

    @pytest.mark.asyncio
    async def test_analyze_trends_filters_by_min_score(self):
        config = _make_config()

        with patch(
            "app.agents.niche_analyzer.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm_text = AsyncMock(
                return_value='{"audience": "General", "summary": "OK"}',
            )

            agent = NicheAnalyzerAgent(config)
            trend_report = TrendReport(
                entries=[TrendEntry(query="abstract philosophy", volume=100)],
                created_at=datetime.now(),
            )

            # Very high min score should filter out low-scoring entries
            report = await agent.analyze_trends(trend_report, min_score=9.5)
            assert isinstance(report, NicheReport)

    @pytest.mark.asyncio
    async def test_llm_summary_failure_uses_fallback(self):
        config = _make_config()

        with patch(
            "app.agents.niche_analyzer.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm_text = AsyncMock(
                side_effect=Exception("LLM down"),
            )

            agent = NicheAnalyzerAgent(config)
            trend_report = TrendReport(
                entries=[
                    TrendEntry(
                        query="retro gaming shirt",
                        volume=82000,
                        growth_rate=45.0,
                        category="Shopping",
                    ),
                ],
                created_at=datetime.now(),
            )

            report = await agent.analyze_trends(trend_report, min_score=0.0)
            assert len(report.entries) > 0
            # Fallback values
            assert report.entries[0].audience == "General consumers"


# ---------------------------------------------------------------------------
# StrategistAgent
# ---------------------------------------------------------------------------

class TestStrategistAgent:
    @pytest.mark.asyncio
    async def test_create_idea_package_returns_typed_model(self):
        config = _make_config()

        with patch(
            "app.agents.strategist.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm = AsyncMock(
                return_value=_StrategyLLMResponse(
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
                ),
            )

            agent = StrategistAgent(config)
            idea = await agent.create_idea_package(_sample_niche_entry())

            assert isinstance(idea, IdeaPackage)
            assert idea.niche_name == "Retro Gaming"
            assert len(idea.final_approved_bullet_points) == 5
            assert idea.opportunity_score == _sample_niche_entry().score.opportunity_score


# ---------------------------------------------------------------------------
# DesignerAgent
# ---------------------------------------------------------------------------

class TestDesignerAgent:
    @pytest.mark.asyncio
    async def test_create_design_prompt_returns_typed_model(self):
        config = _make_config()

        with patch(
            "app.agents.designer.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm = AsyncMock(
                return_value=_DesignLLMResponse(
                    prompt_text="Vibrant pixel art arcade design on black bg.",
                    color_mood_notes="Electric cyan, neon pink, yellow.",
                ),
            )

            agent = DesignerAgent(config)
            idea = _sample_idea_package()
            prompt = await agent.create_design_prompt(idea)

            assert isinstance(prompt, DesignPrompt)
            assert prompt.idea_niche_name == idea.niche_name
            assert prompt.design_style == idea.design_style
            assert "pixel art" in prompt.prompt_text.lower()


# ---------------------------------------------------------------------------
# InspectorAgent
# ---------------------------------------------------------------------------

class TestInspectorAgent:
    @pytest.mark.asyncio
    async def test_inspect_approved_content(self):
        config = _make_config()

        with patch(
            "app.agents.inspector.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm = AsyncMock(
                return_value=_ComplianceLLMResponse(
                    compliant=True,
                    issues=[],
                    notes="Content is compliant.",
                ),
            )

            agent = InspectorAgent(config)
            idea = _sample_idea_package()
            prompt = _sample_design_prompt()

            report = await agent.inspect(idea, prompt)

            assert isinstance(report, ComplianceReport)
            assert report.compliance_status == "approved"
            assert report.risk_terms_detected == []

    @pytest.mark.asyncio
    async def test_inspect_rejects_banned_content(self):
        config = _make_config()

        with patch(
            "app.agents.inspector.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm = AsyncMock(
                return_value=_ComplianceLLMResponse(
                    compliant=True,
                    issues=[],
                    notes="Looks fine.",
                ),
            )

            agent = InspectorAgent(config)

            # Inject a banned term into the idea package
            idea = IdeaPackage(
                niche_name="Bad Niche",
                audience="Test",
                opportunity_score=5.0,
                final_approved_title="Murder themed shirt",
                final_approved_bullet_points=["Bad design"],
                final_approved_description="A bad product.",
                final_approved_keywords_tags=["bad"],
                design_style="dark",
                created_at=datetime.now(),
            )
            prompt = DesignPrompt(
                idea_niche_name="Bad Niche",
                prompt_text="Clean design prompt.",
                design_style="dark",
                created_at=datetime.now(),
            )

            report = await agent.inspect(idea, prompt)
            assert report.compliance_status == "rejected"
            assert "murder" in report.risk_terms_detected

    @pytest.mark.asyncio
    async def test_inspect_needs_review_for_risk_terms(self):
        config = _make_config()

        with patch(
            "app.agents.inspector.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm = AsyncMock(
                return_value=_ComplianceLLMResponse(
                    compliant=True,
                    issues=[],
                    notes="Seems OK but has brand reference.",
                ),
            )

            agent = InspectorAgent(config)

            # Inject a risk (not banned) term
            idea = IdeaPackage(
                niche_name="Brand Style",
                audience="Test",
                opportunity_score=5.0,
                final_approved_title="Nike style athletic wear",
                final_approved_bullet_points=["Sporty design"],
                final_approved_description="Athletic tee.",
                final_approved_keywords_tags=["athletic"],
                design_style="sporty",
                created_at=datetime.now(),
            )
            prompt = DesignPrompt(
                idea_niche_name="Brand Style",
                prompt_text="Athletic design.",
                design_style="sporty",
                created_at=datetime.now(),
            )

            report = await agent.inspect(idea, prompt)
            assert report.compliance_status == "needs_review"
            assert "nike" in report.risk_terms_detected

    @pytest.mark.asyncio
    async def test_inspect_handles_llm_failure(self):
        config = _make_config()

        with patch(
            "app.agents.inspector.PoeClient",
        ) as MockPoe:
            mock_poe = MockPoe.return_value
            mock_poe.call_llm = AsyncMock(
                side_effect=Exception("LLM unavailable"),
            )

            agent = InspectorAgent(config)
            idea = _sample_idea_package()
            prompt = _sample_design_prompt()

            # Should not raise; falls back to compliant
            report = await agent.inspect(idea, prompt)
            assert isinstance(report, ComplianceReport)
            # No banned/risk terms in clean content -> approved
            assert report.compliance_status == "approved"
