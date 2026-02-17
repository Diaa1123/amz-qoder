"""AMZ_Designy - OutputWriter for local file packages."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

from app.config import AppConfig
from app.schemas import (
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheReport,
    TrendReport,
)

logger = logging.getLogger(__name__)


class OutputWriter:
    """Write structured local output packages to disk."""

    def __init__(self, config: AppConfig) -> None:
        self._output_dir = config.output_dir

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def write_package(
        self,
        trend_name: str,
        concept_index: int,
        trend_report: TrendReport,
        niche_report: NicheReport,
        idea_package: IdeaPackage,
        design_prompt: DesignPrompt,
        compliance_report: ComplianceReport,
    ) -> Path:
        """Write all pipeline artifacts to the output directory.

        Returns the path to the concept directory.
        """
        out_dir = self._create_output_structure(trend_name, concept_index)

        # JSON artifacts
        self._write_json(out_dir / "trend_report.json", trend_report)
        self._write_json(out_dir / "niche_report.json", niche_report)
        self._write_json(out_dir / "idea_package.json", idea_package)
        self._write_json(out_dir / "design_prompt.json", design_prompt)
        self._write_json(out_dir / "compliance_report.json", compliance_report)

        # Text artifacts
        self._write_listing_txt(idea_package, out_dir)
        self._write_keywords_txt(idea_package, out_dir)
        self._write_final_summary(idea_package, compliance_report, out_dir)

        logger.info("Output package written to %s", out_dir)
        return out_dir

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_output_structure(
        self,
        trend_name: str,
        concept_index: int,
    ) -> Path:
        today = date.today().isoformat()  # YYYY-MM-DD
        slug = self._slugify(trend_name)
        concept = f"concept_{concept_index:02d}"
        out_dir = self._output_dir / today / slug / concept
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @staticmethod
    def _slugify(name: str) -> str:
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        return slug.strip("-")

    @staticmethod
    def _write_json(path: Path, model) -> None:  # noqa: ANN001
        path.write_text(
            model.model_dump_json(indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _write_listing_txt(idea: IdeaPackage, out_dir: Path) -> None:
        lines = [idea.final_approved_title, ""]
        lines.append("BULLET POINTS:")
        for bp in idea.final_approved_bullet_points:
            lines.append(f"  - {bp}")
        lines.append("")
        lines.append("DESCRIPTION:")
        lines.append(idea.final_approved_description)
        (out_dir / "listing.txt").write_text(
            "\n".join(lines), encoding="utf-8",
        )

    @staticmethod
    def _write_keywords_txt(idea: IdeaPackage, out_dir: Path) -> None:
        (out_dir / "keywords.txt").write_text(
            "\n".join(idea.final_approved_keywords_tags),
            encoding="utf-8",
        )

    @staticmethod
    def _write_final_summary(
        idea: IdeaPackage,
        report: ComplianceReport,
        out_dir: Path,
    ) -> None:
        status_label = report.compliance_status.upper()
        lines = [
            f"PIPELINE SUMMARY - {idea.niche_name}",
            f"Status: {status_label}",
            "",
            f"Title: {idea.final_approved_title}",
            f"Audience: {idea.audience}",
            f"Opportunity Score: {idea.opportunity_score}",
            f"Design Style: {idea.design_style}",
            "",
            f"Compliance: {status_label}",
            f"Notes: {report.compliance_notes}",
        ]
        if report.risk_terms_detected:
            lines.append(
                f"Risk Terms: {', '.join(report.risk_terms_detected)}",
            )
        (out_dir / "final_summary.txt").write_text(
            "\n".join(lines), encoding="utf-8",
        )
