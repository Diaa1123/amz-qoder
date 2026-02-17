"""AMZ_Designy - DesignerAgent: generate design prompts via LLM."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.config import AppConfig
from app.integrations.poe_client import PoeClient
from app.schemas import DesignPrompt, IdeaPackage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a Merch design prompt engineer. Create detailed prompts for AI image
generation (DALL-E 3 or similar) targeting Amazon Merch t-shirt designs.

Rules:
- Prompt must describe a print-ready design suitable for t-shirts.
- Include style direction, composition, and color guidance.
- NEVER reference specific game titles, movie characters, or trademarked IP.
- Focus on generic themes that evoke the intended mood.
- Describe the design as centered, suitable for dark or light shirt backgrounds.
"""


class _DesignLLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_text: str
    color_mood_notes: str


class DesignerAgent:
    """Generate a design prompt and style metadata via LLM.

    Does NOT render images -- only crafts the prompt.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._poe = PoeClient(config)

    async def create_design_prompt(
        self,
        idea_package: IdeaPackage,
    ) -> DesignPrompt:
        """Generate a DesignPrompt for the given IdeaPackage."""
        user_msg = (
            f"Niche: {idea_package.niche_name}\n"
            f"Title: {idea_package.final_approved_title}\n"
            f"Audience: {idea_package.audience}\n"
            f"Design style: {idea_package.design_style}\n"
            f"Keywords: {', '.join(idea_package.final_approved_keywords_tags[:5])}\n\n"
            "Generate a detailed image prompt and color/mood notes."
        )

        result = await self._poe.call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_msg,
            response_model=_DesignLLMResponse,
        )

        prompt = DesignPrompt(
            idea_niche_name=idea_package.niche_name,
            prompt_text=result.prompt_text,
            design_style=idea_package.design_style,
            color_mood_notes=result.color_mood_notes,
            created_at=datetime.now(),
        )
        logger.info(
            "Designer created DesignPrompt for '%s'", prompt.idea_niche_name,
        )
        return prompt
