"""Tests for Pydantic schema validation (strict mode, extra=forbid)."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.schemas import (
    AirtableRowIdea,
    AirtableRowNiche,
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheEntry,
    NicheReport,
    NicheScore,
    TrendEntry,
    TrendReport,
)


class TestTrendEntry:
    def test_valid(self):
        e = TrendEntry(query="test query")
        assert e.query == "test query"
        assert e.source == "google_trends"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            TrendEntry(query="test", bogus_field="oops")


class TestTrendReport:
    def test_valid(self):
        r = TrendReport(created_at=datetime.now())
        assert r.entries == []
        assert r.geo == "US"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            TrendReport(created_at=datetime.now(), foo="bar")


class TestNicheScore:
    def test_valid(self):
        s = NicheScore(
            commercial_intent=8, designability=7, audience_size=6,
            competition_level=5, seasonality_risk=4, trademark_risk=3,
        )
        assert isinstance(s.opportunity_score, float)

    def test_opportunity_score_calculation(self):
        s = NicheScore(
            commercial_intent=9, designability=9, audience_size=8,
            competition_level=6, seasonality_risk=3, trademark_risk=4,
        )
        # 0.2*9 + 0.25*9 + 0.2*8 + 0.15*5 + 0.1*8 + 0.1*7 = 7.90
        assert s.opportunity_score == 7.90

    def test_range_validation(self):
        with pytest.raises(ValidationError):
            NicheScore(
                commercial_intent=0, designability=7, audience_size=6,
                competition_level=5, seasonality_risk=4, trademark_risk=3,
            )

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            NicheScore(
                commercial_intent=8, designability=7, audience_size=6,
                competition_level=5, seasonality_risk=4, trademark_risk=3,
                extra=1,
            )


class TestIdeaPackage:
    def test_valid(self, sample_idea_package: IdeaPackage):
        assert sample_idea_package.niche_name == "Retro Gaming Nostalgia Apparel"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            IdeaPackage(
                niche_name="x", audience="y", opportunity_score=1.0,
                final_approved_title="t", final_approved_description="d",
                design_style="s", created_at=datetime.now(),
                unknown="bad",
            )


class TestDesignPrompt:
    def test_valid(self, sample_design_prompt: DesignPrompt):
        assert sample_design_prompt.idea_niche_name == "Retro Gaming Nostalgia Apparel"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            DesignPrompt(
                idea_niche_name="x", prompt_text="p", design_style="s",
                created_at=datetime.now(), extra_field="bad",
            )


class TestComplianceReport:
    def test_valid_statuses(self):
        for status in ("approved", "rejected", "needs_review"):
            r = ComplianceReport(
                idea_niche_name="x", compliance_status=status,
                compliance_notes="n", created_at=datetime.now(),
            )
            assert r.compliance_status == status

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            ComplianceReport(
                idea_niche_name="x", compliance_status="passed",
                compliance_notes="n", created_at=datetime.now(),
            )


class TestAirtableRowIdea:
    def test_valid_with_aliases(self):
        row = AirtableRowIdea(
            run_date=date(2026, 2, 17),
            trend_name="retro gaming shirt",
            niche_name="Retro Gaming",
            audience="Gamers",
            opportunity_score=7.9,
            final_approved_title="Title",
            final_approved_bullet_points="bp1\nbp2",
            final_approved_description="desc",
            final_approved_keywords_tags="kw1, kw2",
            design_prompt="prompt",
            compliance_status="approved",
            compliance_notes="ok",
            risk_terms_detected="",
            design_style="retro",
        )
        fields = row.to_airtable_fields()
        assert fields["Date"] == "2026-02-17"
        assert fields["Trend Name"] == "retro gaming shirt"
        assert fields["Final Approved Keywords/Tags"] == "kw1, kw2"
        assert fields["Status"] == "draft"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            AirtableRowIdea(
                run_date=date.today(), trend_name="x", niche_name="x",
                audience="x", opportunity_score=1.0,
                final_approved_title="x",
                final_approved_bullet_points="x",
                final_approved_description="x",
                final_approved_keywords_tags="x",
                design_prompt="x", compliance_status="approved",
                compliance_notes="x", risk_terms_detected="",
                design_style="x", bogus="bad",
            )


class TestAirtableRowNiche:
    def test_valid_with_aliases(self):
        row = AirtableRowNiche(
            niche_name="Test Niche",
            week_start_date=date(2026, 2, 17),
            weekly_growth_percent=25.0,
            rising_status="rising",
            opportunity_score=7.5,
            notes="test",
        )
        fields = row.to_airtable_fields()
        assert fields["Niche Name"] == "Test Niche"
        assert fields["Weekly Growth %"] == 25.0
        assert fields["Rising Status"] == "rising"
