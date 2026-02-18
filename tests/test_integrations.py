"""Integration tests for AirtableClient and PytrendsClient with mocks."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.agents.niche_analyzer import NicheAnalyzerAgent
from app.agents.trend_scout import TrendScoutAgent
from app.integrations.airtable_client import AirtableClient
from app.integrations.pytrends_client import PytrendsClient, DEFAULT_SEED_KEYWORDS
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
from app.utils.geo_mapping import get_pytrends_pn, is_supported_geo, ISO_TO_PYTRENDS_PN
from app.utils.exceptions import TrendsAPIError


# ---------------------------------------------------------------------------
# Geo Mapping Tests
# ---------------------------------------------------------------------------

class TestGeoMapping:
    def test_get_pytrends_pn_us(self):
        """US should map to united_states."""
        assert get_pytrends_pn("US") == "united_states"
        assert get_pytrends_pn("us") == "united_states"

    def test_get_pytrends_pn_gb(self):
        """GB should map to united_kingdom."""
        assert get_pytrends_pn("GB") == "united_kingdom"
        assert get_pytrends_pn("gb") == "united_kingdom"

    def test_get_pytrends_pn_sa(self):
        """SA should map to saudi_arabia."""
        assert get_pytrends_pn("SA") == "saudi_arabia"

    def test_get_pytrends_pn_unknown_defaults_to_us(self):
        """Unknown geo codes should default to united_states."""
        assert get_pytrends_pn("XX") == "united_states"
        assert get_pytrends_pn("ZZ") == "united_states"
        assert get_pytrends_pn("UNKNOWN") == "united_states"

    def test_is_supported_geo_true(self):
        """Supported geos should return True."""
        assert is_supported_geo("US") is True
        assert is_supported_geo("GB") is True
        assert is_supported_geo("SA") is True

    def test_is_supported_geo_false(self):
        """Unsupported geos should return False."""
        assert is_supported_geo("XX") is False
        assert is_supported_geo("ZZ") is False

    def test_iso_mapping_completeness(self):
        """Verify key countries are in the mapping."""
        key_countries = ["US", "GB", "SA", "AE", "CA", "AU", "DE", "FR", "JP"]
        for country in key_countries:
            assert country in ISO_TO_PYTRENDS_PN, f"{country} should be in mapping"


# ---------------------------------------------------------------------------
# PytrendsClient
# ---------------------------------------------------------------------------

class TestPytrendsClient:
    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_success(self, MockTrendReq: MagicMock):
        """Test successful trending_searches returns TrendReport."""
        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.return_value = pd.DataFrame(
            {0: ["cat shirt", "dog hoodie", "funny tee"]},
        )

        client = PytrendsClient()
        result = await client.trending_searches("US")

        assert isinstance(result, TrendReport)
        assert len(result.entries) == 3
        assert result.entries[0].query == "cat shirt"
        assert result.entries[0].source == "google_trends"
        assert result.geo == "US"
        # Verify pn mapping was applied
        mock_instance.trending_searches.assert_called_once_with(pn="united_states")

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_with_geo_mapping(self, MockTrendReq: MagicMock):
        """Test that ISO geo codes are properly mapped to pn values."""
        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.return_value = pd.DataFrame(
            {0: ["query1", "query2"]},
        )

        client = PytrendsClient()
        
        # Test GB mapping
        await client.trending_searches("GB")
        assert mock_instance.trending_searches.call_args[1]["pn"] == "united_kingdom"
        
        mock_instance.trending_searches.reset_mock()
        
        # Test SA mapping
        await client.trending_searches("SA")
        assert mock_instance.trending_searches.call_args[1]["pn"] == "saudi_arabia"

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_empty_triggers_fallback(
        self, MockTrendReq: MagicMock
    ):
        """Test that empty trending_searches triggers fallback to realtime_trends."""
        mock_instance = MockTrendReq.return_value
        # First call returns empty
        mock_instance.trending_searches.return_value = pd.DataFrame()
        # realtime_trending_searches returns data
        mock_instance.realtime_trending_searches.return_value = pd.DataFrame({
            0: ["realtime query 1", "realtime query 2"],
        })

        client = PytrendsClient()
        result = await client.trending_searches("US")

        assert isinstance(result, TrendReport)
        assert len(result.entries) == 2
        assert result.entries[0].query == "realtime query 1"
        assert result.entries[0].source == "google_trends_realtime"
        # Verify realtime_trending_searches was called
        mock_instance.realtime_trending_searches.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_failure_triggers_degraded_mode(
        self, MockTrendReq: MagicMock
    ):
        """Test that complete failure returns seed keywords in degraded mode."""
        from pytrends.exceptions import ResponseError
        
        mock_instance = MockTrendReq.return_value
        # Both endpoints fail - ResponseError requires message and response
        mock_response = MagicMock()
        mock_instance.trending_searches.side_effect = ResponseError("404 error", mock_response)
        mock_instance.realtime_trending_searches.side_effect = ResponseError("API error", mock_response)

        client = PytrendsClient()
        custom_seeds = ["custom seed 1", "custom seed 2"]
        result = await client.trending_searches("US", seed_keywords=custom_seeds)

        assert isinstance(result, TrendReport)
        assert len(result.entries) == 2
        assert result.entries[0].query == "custom seed 1"
        assert result.entries[0].source == "seed_fallback"
        assert result.geo == "US"

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_default_seeds(self, MockTrendReq: MagicMock):
        """Test degraded mode uses default seeds when none provided."""
        from pytrends.exceptions import ResponseError
        
        mock_instance = MockTrendReq.return_value
        mock_response = MagicMock()
        mock_instance.trending_searches.side_effect = ResponseError("404 error", mock_response)
        mock_instance.daily_trends.side_effect = ResponseError("API error", mock_response)

        client = PytrendsClient()
        result = await client.trending_searches("XX")  # Unknown geo

        assert isinstance(result, TrendReport)
        assert len(result.entries) == len(DEFAULT_SEED_KEYWORDS)
        assert result.entries[0].source == "seed_fallback"

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_respects_extra_forbid(self, MockTrendReq: MagicMock):
        """Verify TrendReport respects extra=forbid in Pydantic model."""
        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.return_value = pd.DataFrame(
            {0: ["test query"]},
        )

        client = PytrendsClient()
        result = await client.trending_searches("US")

        # Verify model validation passes
        assert isinstance(result, TrendReport)
        # Try to create with extra field should fail
        with pytest.raises(ValueError):
            TrendReport(
                entries=[TrendEntry(query="test")],
                geo="US",
                timeframe="today 1-m",
                created_at=datetime.now(),
                extra_field="not allowed",  # type: ignore
            )

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_related_queries(self, MockTrendReq: MagicMock):
        mock_instance = MockTrendReq.return_value
        mock_instance.related_queries.return_value = {
            "cat shirt": {
                "top": pd.DataFrame({"query": ["cute cat", "cat tee", "kitten shirt"]}),
                "rising": pd.DataFrame({"query": ["viral cat"]}),
            },
        }

        client = PytrendsClient()
        result = await client.related_queries("cat shirt", "US", "today 1-m")

        assert "cute cat" in result
        assert "viral cat" in result

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_interest_over_time(self, MockTrendReq: MagicMock):
        mock_instance = MockTrendReq.return_value
        data = pd.DataFrame({"cat shirt": [20, 30, 40, 50]})
        mock_instance.interest_over_time.return_value = data

        client = PytrendsClient()
        volume, growth = await client.interest_over_time(
            "cat shirt", "US", "today 1-m",
        )

        assert volume > 0
        assert isinstance(growth, float)

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_interest_over_time_empty(self, MockTrendReq: MagicMock):
        mock_instance = MockTrendReq.return_value
        mock_instance.interest_over_time.return_value = pd.DataFrame()

        client = PytrendsClient()
        volume, growth = await client.interest_over_time(
            "cat shirt", "US", "today 1-m",
        )

        assert volume == 0
        assert growth == 0.0


# ---------------------------------------------------------------------------
# AirtableClient
# ---------------------------------------------------------------------------

class TestAirtableClient:
    @pytest.mark.asyncio
    @patch("app.integrations.airtable_client.Api")
    async def test_write_idea(self, MockApi: MagicMock):
        config = MagicMock()
        config.airtable_api_key.get_secret_value.return_value = "test-key"
        config.airtable_base_id = "appTEST"
        config.airtable_table_id = "tblTEST"
        config.airtable_niche_table_id = "tblNICHE"

        mock_table = MagicMock()
        mock_table.create.return_value = {"id": "rec_test_123", "fields": {}}
        MockApi.return_value.table.return_value = mock_table

        client = AirtableClient(config)

        idea = IdeaPackage(
            niche_name="Test Niche",
            audience="Test audience",
            opportunity_score=7.5,
            final_approved_title="Test Title",
            final_approved_bullet_points=["bp1", "bp2"],
            final_approved_description="Test description.",
            final_approved_keywords_tags=["kw1", "kw2"],
            design_style="modern",
            created_at=datetime.now(),
        )
        prompt = DesignPrompt(
            idea_niche_name="Test Niche",
            prompt_text="Test prompt.",
            design_style="modern",
            created_at=datetime.now(),
        )
        report = ComplianceReport(
            idea_niche_name="Test Niche",
            compliance_status="approved",
            compliance_notes="OK.",
            risk_terms_detected=[],
            created_at=datetime.now(),
        )

        rec_id = await client.write_idea(
            run_date=date.today(),
            trend_name="test trend",
            idea=idea,
            prompt=prompt,
            report=report,
        )

        assert rec_id == "rec_test_123"
        mock_table.create.assert_called_once()

        # Verify that the fields dict has Airtable column names
        call_args = mock_table.create.call_args[0][0]
        assert "Niche Name" in call_args
        assert "Final Approved Title" in call_args
        assert call_args["Compliance Status"] == "approved"

    @pytest.mark.asyncio
    @patch("app.integrations.airtable_client.Api")
    async def test_write_weekly_niche(self, MockApi: MagicMock):
        config = MagicMock()
        config.airtable_api_key.get_secret_value.return_value = "test-key"
        config.airtable_base_id = "appTEST"
        config.airtable_table_id = "tblTEST"
        config.airtable_niche_table_id = "tblNICHE"

        mock_table = MagicMock()
        mock_table.create.return_value = {"id": "rec_niche_456", "fields": {}}
        MockApi.return_value.table.return_value = mock_table

        client = AirtableClient(config)

        entry = NicheEntry(
            niche_name="Rising Niche",
            trending_query="rising query",
            score=NicheScore(
                commercial_intent=8, designability=8, audience_size=7,
                competition_level=4, seasonality_risk=3, trademark_risk=2,
            ),
            audience="General",
            analysis_summary="Good niche.",
        )

        rec_id = await client.write_weekly_niche(
            entry=entry, week_start=date(2026, 2, 17),
        )

        assert rec_id == "rec_niche_456"
        mock_table.create.assert_called_once()

        call_args = mock_table.create.call_args[0][0]
        assert "Niche Name" in call_args
        assert "Weekly Growth %" in call_args
        assert "Rising Status" in call_args


# ---------------------------------------------------------------------------
# Integration: Degraded Mode -> NicheAnalyzer
# ---------------------------------------------------------------------------

class TestDegradedModeIntegration:
    """Test that degraded mode (seed keywords) produces valid NicheReport."""

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    @patch("app.agents.niche_analyzer.PoeClient")
    async def test_degraded_mode_produces_valid_niche_report(
        self, MockPoe: MagicMock, MockTrendReq: MagicMock
    ):
        """End-to-end test: degraded mode TrendReport -> NicheAnalyzer -> valid NicheReport.

        This ensures that even when pytrends completely fails and we fall back
        to seed keywords, the pipeline doesn't crash and produces valid output.
        """
        from pytrends.exceptions import ResponseError

        # Setup: Mock pytrends to fail completely (triggers degraded mode)
        mock_response = MagicMock()
        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.side_effect = ResponseError(
            "404 error", mock_response
        )
        mock_instance.daily_trends.side_effect = ResponseError(
            "API error", mock_response
        )
        mock_instance.related_queries.return_value = []
        mock_instance.interest_over_time.return_value = (0, 0.0)

        # Setup: Mock LLM for NicheAnalyzer
        mock_poe = MockPoe.return_value
        mock_poe.call_llm_text = AsyncMock(
            return_value='{"audience": "General consumers", "summary": "Good niche"}',
        )

        # Create config
        config = MagicMock()
        config.min_niche_score = 0.0  # Accept all for this test
        config.llm_model = "gpt-4o"
        config.max_tokens = 4000
        config.temperature = 0.7

        # Run TrendScout (will use degraded mode)
        scout = TrendScoutAgent(config)
        custom_seeds = ["funny cat shirt", "retro gaming tee"]
        trend_report = await scout.discover_trends(
            seed_keywords=custom_seeds, geo="US"
        )

        # Verify: TrendReport is valid and contains seed keywords
        assert isinstance(trend_report, TrendReport)
        assert len(trend_report.entries) == 2
        assert trend_report.entries[0].query == "funny cat shirt"
        assert trend_report.entries[0].source == "seed_fallback"
        assert trend_report.geo == "US"

        # Verify: TrendEntry has required fields (query is minimum)
        for entry in trend_report.entries:
            assert isinstance(entry, TrendEntry)
            assert entry.query is not None
            assert entry.query != ""

        # Run NicheAnalyzer (consumes TrendReport)
        analyzer = NicheAnalyzerAgent(config)
        niche_report = await analyzer.analyze_trends(
            trend_report, min_score=0.0
        )

        # Verify: NicheReport is valid even from degraded mode
        assert isinstance(niche_report, NicheReport)
        assert len(niche_report.entries) == 2

        # Verify: NicheEntry objects are properly formed
        for entry in niche_report.entries:
            assert isinstance(entry, NicheEntry)
            assert entry.niche_name is not None
            assert entry.trending_query is not None
            assert isinstance(entry.score, NicheScore)
            # Score should be calculated (not default/empty)
            assert 1 <= entry.score.opportunity_score <= 10

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    @patch("app.agents.niche_analyzer.PoeClient")
    async def test_degraded_mode_with_llm_failure(
        self, MockPoe: MagicMock, MockTrendReq: MagicMock
    ):
        """Test that pipeline survives even when LLM fails in NicheAnalyzer."""
        from pytrends.exceptions import ResponseError

        # Setup: Complete pytrends failure
        mock_response = MagicMock()
        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.side_effect = ResponseError(
            "404 error", mock_response
        )
        mock_instance.daily_trends.side_effect = ResponseError(
            "API error", mock_response
        )
        mock_instance.related_queries.return_value = []
        mock_instance.interest_over_time.return_value = (0, 0.0)

        # Setup: LLM fails
        mock_poe = MockPoe.return_value
        mock_poe.call_llm_text = AsyncMock(side_effect=Exception("LLM down"))

        config = MagicMock()
        config.min_niche_score = 0.0
        config.llm_model = "gpt-4o"
        config.max_tokens = 4000
        config.temperature = 0.7

        # Run pipeline
        scout = TrendScoutAgent(config)
        trend_report = await scout.discover_trends(
            seed_keywords=["test keyword"], geo="US"
        )

        analyzer = NicheAnalyzerAgent(config)
        niche_report = await analyzer.analyze_trends(trend_report, min_score=0.0)

        # Verify: Pipeline didn't crash, produced valid NicheReport
        assert isinstance(niche_report, NicheReport)
        assert len(niche_report.entries) == 1
        # Fallback values used when LLM fails
        assert niche_report.entries[0].audience == "General consumers"
