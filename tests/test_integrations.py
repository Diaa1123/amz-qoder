"""Integration tests for AirtableClient and PytrendsClient with mocks."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.airtable_client import AirtableClient
from app.integrations.pytrends_client import PytrendsClient
from app.schemas import (
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheEntry,
    NicheScore,
)


# ---------------------------------------------------------------------------
# PytrendsClient
# ---------------------------------------------------------------------------

class TestPytrendsClient:
    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches(self, MockTrendReq: MagicMock):
        import pandas as pd

        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.return_value = pd.DataFrame(
            {0: ["cat shirt", "dog hoodie", "funny tee"]},
        )

        client = PytrendsClient()
        result = await client.trending_searches("US")

        assert result == ["cat shirt", "dog hoodie", "funny tee"]
        mock_instance.trending_searches.assert_called_once_with(pn="us")

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_trending_searches_empty(self, MockTrendReq: MagicMock):
        import pandas as pd

        mock_instance = MockTrendReq.return_value
        mock_instance.trending_searches.return_value = pd.DataFrame()

        client = PytrendsClient()
        result = await client.trending_searches("US")
        assert result == []

    @pytest.mark.asyncio
    @patch("app.integrations.pytrends_client.TrendReq")
    async def test_related_queries(self, MockTrendReq: MagicMock):
        import pandas as pd

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
        import pandas as pd

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
        import pandas as pd

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
