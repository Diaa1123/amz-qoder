"""AMZ_Designy - StrategistAgent: generate listing content via LLM."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.config import AppConfig
from app.integrations.poe_client import PoeClient
from app.schemas import IdeaPackage, NicheEntry

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an Amazon Merch-on-Demand listing strategist. Your job is to create
compelling, policy-compliant listing content for t-shirt designs.

Rules:
- Title: max 60 characters, include primary keyword.
- Bullet points: exactly 5 items, each highlighting a unique selling point.
- Description: 150-350 characters, persuasive and keyword-rich.
- Keywords/tags: 10-15 relevant SEO terms.
- Design style: a short phrase describing the visual direction.
- NEVER reference trademarked brands, characters, or copyrighted material.
"""


class _StrategyLLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    bullet_points: list[str]
    description: str
    keywords: list[str]
    design_style: str


class StrategistAgent:
    """Create comprehensive listing content and design briefs via LLM."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._poe = PoeClient(config)

    async def create_idea_package(
        self,
        niche_entry: NicheEntry,
    ) -> IdeaPackage:
        """Generate an IdeaPackage for the given niche."""
        user_msg = (
            f"Niche: {niche_entry.niche_name}\n"
            f"Trending query: {niche_entry.trending_query}\n"
            f"Target audience: {niche_entry.audience}\n"
            f"Opportunity score: {niche_entry.score.opportunity_score}\n"
            f"Analysis: {niche_entry.analysis_summary}\n\n"
            "Generate a complete Amazon Merch listing package."
        )

        result = await self._poe.call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_msg,
            response_model=_StrategyLLMResponse,
        )

        idea = IdeaPackage(
            niche_name=niche_entry.niche_name,
            audience=niche_entry.audience,
            opportunity_score=niche_entry.score.opportunity_score,
            final_approved_title=result.title,
            final_approved_bullet_points=result.bullet_points,
            final_approved_description=result.description,
            final_approved_keywords_tags=result.keywords,
            design_style=result.design_style,
            created_at=datetime.now(),
        )
        logger.info("Strategist created IdeaPackage for '%s'", idea.niche_name)
        return idea
