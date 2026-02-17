"""AMZ_Designy - Pydantic data contracts.

All models use strict validation (extra="forbid").
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Trend models
# ---------------------------------------------------------------------------

class TrendEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    volume: Optional[int] = None
    growth_rate: Optional[float] = None
    category: Optional[str] = None
    source: str = "google_trends"


class TrendReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[TrendEntry] = Field(default_factory=list)
    geo: str = "US"
    timeframe: str = "today 1-m"
    created_at: datetime


# ---------------------------------------------------------------------------
# Niche models
# ---------------------------------------------------------------------------

class NicheScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commercial_intent: int = Field(..., ge=1, le=10)
    designability: int = Field(..., ge=1, le=10)
    audience_size: int = Field(..., ge=1, le=10)
    competition_level: int = Field(..., ge=1, le=10)
    seasonality_risk: int = Field(..., ge=1, le=10)
    trademark_risk: int = Field(..., ge=1, le=10)

    @property
    def opportunity_score(self) -> float:
        weights = [0.2, 0.25, 0.2, 0.15, 0.1, 0.1]
        scores = [
            self.commercial_intent,
            self.designability,
            self.audience_size,
            11 - self.competition_level,
            11 - self.seasonality_risk,
            11 - self.trademark_risk,
        ]
        return round(sum(w * s for w, s in zip(weights, scores)), 2)


class NicheEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche_name: str
    trending_query: str
    score: NicheScore
    audience: str
    analysis_summary: str


class NicheReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[NicheEntry] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Strategy / Design / Compliance models
# ---------------------------------------------------------------------------

class IdeaPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche_name: str
    audience: str
    opportunity_score: float
    final_approved_title: str
    final_approved_bullet_points: list[str] = Field(default_factory=list)
    final_approved_description: str
    final_approved_keywords_tags: list[str] = Field(default_factory=list)
    design_style: str
    created_at: datetime


class DesignPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_niche_name: str
    prompt_text: str
    design_style: str
    color_mood_notes: Optional[str] = None
    created_at: datetime


class ComplianceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_niche_name: str
    compliance_status: Literal["approved", "rejected", "needs_review"]
    compliance_notes: str
    risk_terms_detected: list[str] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Airtable row models (aliases = exact Airtable column names)
# ---------------------------------------------------------------------------

class AirtableRowIdea(BaseModel):
    """Maps to the Airtable Ideas table."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_date: date = Field(..., alias="Date")
    trend_name: str = Field(..., alias="Trend Name")
    niche_name: str = Field(..., alias="Niche Name")
    audience: str = Field(..., alias="Audience")
    opportunity_score: float = Field(..., alias="Opportunity Score")
    final_approved_title: str = Field(..., alias="Final Approved Title")
    final_approved_bullet_points: str = Field(
        ..., alias="Final Approved Bullet Points",
    )  # newline-separated
    final_approved_description: str = Field(
        ..., alias="Final Approved Description",
    )
    final_approved_keywords_tags: str = Field(
        ..., alias="Final Approved Keywords/Tags",
    )  # comma-separated
    design_prompt: str = Field(..., alias="Design Prompt")
    compliance_status: Literal["approved", "rejected", "needs_review"] = Field(
        ..., alias="Compliance Status",
    )
    compliance_notes: str = Field(..., alias="Compliance Notes")
    risk_terms_detected: str = Field(
        ..., alias="Risk Terms Detected",
    )  # comma-separated
    design_style: str = Field(..., alias="Design Style")
    status: Literal["draft", "ready", "published", "rejected"] = Field(
        "draft", alias="Status",
    )

    def to_airtable_fields(self) -> dict:
        """Serialize using aliases (Airtable column names with spaces)."""
        data = self.model_dump(by_alias=True, mode="json")
        return data


class AirtableRowNiche(BaseModel):
    """Maps to the Airtable Weekly Niche table."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    niche_name: str = Field(..., alias="Niche Name")
    week_start_date: date = Field(..., alias="Week Start Date")
    weekly_growth_percent: float = Field(..., alias="Weekly Growth %")
    rising_status: Literal["rising", "stable", "declining"] = Field(
        ..., alias="Rising Status",
    )
    opportunity_score: float = Field(..., alias="Opportunity Score")
    notes: str = Field(..., alias="Notes")

    def to_airtable_fields(self) -> dict:
        """Serialize using aliases (Airtable column names with spaces)."""
        data = self.model_dump(by_alias=True, mode="json")
        return data
