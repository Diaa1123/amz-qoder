"""Integration tests for AirtableClient and PytrendsClient with mocks."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.integrations.airtable_client import AirtableClient
from app.integrations.pytrends_client import PytrendsClient, DEFAULT_SEED_KEYWORDS
from app.schemas import (
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheEntry,
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
        """Test that empty trending_searches triggers fallback to daily_trends."""
        mock_instance = MockTrendReq.return_value
        # First call returns empty
        mock_instance.trending_searches.return_value = pd.DataFrame()
        # daily_trends returns data
        mock_instance.daily_trends.return_value = pd.DataFrame({
            "trendingSearches": [
                [{"title": {"query": "fallback query 1"}}],
                [{"title": {"query": "fallback query 2"}}],
            ]
        })

        client = PytrendsClient()
        result = await client.trending_searches("US")

        assert isinstance(result, TrendReport)
        assert len(result.entries) == 2
        assert result.entries[0].query == "fallback query 1"
        assert result.entries[0].source == "google_trends_daily"
        # Verify daily_trends was called with ISO geo
        mock_instance.daily_trends.assert_called_once_with(geo="US")

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
        mock_instance.daily_trends.side_effect = ResponseError("API error", mock_response)

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
