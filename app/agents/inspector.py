"""AMZ_Designy - InspectorAgent: compliance validation (text + prompt)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from app.config import AppConfig
from app.integrations.poe_client import PoeClient
from app.schemas import ComplianceReport, DesignPrompt, IdeaPackage
from app.utils.validators import scan_for_banned_terms, scan_for_risk_terms

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an Amazon Merch compliance inspector. Review the listing content
and design prompt for policy violations.

Amazon Merch policies prohibit:
- Hate speech, violence, adult content
- Copyrighted / trademarked material (characters, logos, brand names)
- Personal information
- Misleading claims (FDA, official, licensed -- unless true)

Respond with JSON:
{
  "compliant": true/false,
  "issues": ["list of specific issues found"],
  "notes": "overall assessment"
}
"""


class InspectorAgent:
    """Validate idea packages and design prompts against Amazon Merch policies.

    Uses rule-based keyword scanning + LLM compliance review.
    Image vision is NOT in scope (future).
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._poe = PoeClient(config)

    async def inspect(
        self,
        idea_package: IdeaPackage,
        design_prompt: DesignPrompt,
    ) -> ComplianceReport:
        """Run compliance checks and return a ComplianceReport."""
        # Collect all text for scanning
        all_text = " ".join([
            idea_package.final_approved_title,
            " ".join(idea_package.final_approved_bullet_points),
            idea_package.final_approved_description,
            " ".join(idea_package.final_approved_keywords_tags),
            design_prompt.prompt_text,
            design_prompt.color_mood_notes or "",
        ])

        # 1. Rule-based scan
        banned = scan_for_banned_terms(all_text)
        risk = scan_for_risk_terms(all_text)

        # 2. LLM compliance check
        llm_result = await self._llm_compliance_check(
            idea_package, design_prompt,
        )

        # 3. Determine status
        status = self._decide_status(banned, risk, llm_result)

        # 4. Build notes
        notes_parts: list[str] = []
        if banned:
            notes_parts.append(f"BANNED terms found: {', '.join(banned)}")
        if risk:
            notes_parts.append(f"Risk terms found: {', '.join(risk)}")
        if llm_result.get("notes"):
            notes_parts.append(f"LLM: {llm_result['notes']}")
        if llm_result.get("issues"):
            notes_parts.append(
                f"LLM issues: {'; '.join(llm_result['issues'])}",
            )
        if not notes_parts:
            notes_parts.append("All checks passed. No issues detected.")

        report = ComplianceReport(
            idea_niche_name=idea_package.niche_name,
            compliance_status=status,
            compliance_notes=" | ".join(notes_parts),
            risk_terms_detected=banned + risk,
            created_at=datetime.now(),
        )
        logger.info(
            "Inspector result for '%s': %s",
            idea_package.niche_name,
            status,
        )
        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _decide_status(
        self,
        banned: list[str],
        risk: list[str],
        llm_result: dict,
    ) -> Literal["approved", "rejected", "needs_review"]:
        # Banned terms -> always reject
        if banned:
            return "rejected"

        llm_compliant = llm_result.get("compliant", True)

        # LLM says non-compliant -> reject
        if not llm_compliant:
            return "rejected"

        # Risk terms found but LLM says compliant -> needs review
        if risk:
            return "needs_review"

        return "approved"

    async def _llm_compliance_check(
        self,
        idea: IdeaPackage,
        prompt: DesignPrompt,
    ) -> dict:
        """Run LLM compliance review. Returns dict with 'compliant', 'issues', 'notes'."""
        try:
            import json

            user_msg = (
                f"Title: {idea.final_approved_title}\n"
                f"Bullet Points: {chr(10).join(idea.final_approved_bullet_points)}\n"
                f"Description: {idea.final_approved_description}\n"
                f"Keywords: {', '.join(idea.final_approved_keywords_tags)}\n"
                f"Design Prompt: {prompt.prompt_text}\n"
                f"Color/Mood: {prompt.color_mood_notes or 'N/A'}\n"
            )

            raw = await self._poe.call_llm_text(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_msg,
            )
            return json.loads(raw)
        except Exception:
            logger.warning("LLM compliance check failed, assuming compliant")
            return {"compliant": True, "issues": [], "notes": "LLM check unavailable"}
