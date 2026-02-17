"""Tests for OutputWriter file structure."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.io.outputs import OutputWriter
from app.schemas import (
    ComplianceReport,
    DesignPrompt,
    IdeaPackage,
    NicheReport,
    TrendReport,
)


@pytest.fixture
def writer(tmp_path: Path) -> OutputWriter:
    config = MagicMock()
    config.output_dir = tmp_path
    return OutputWriter(config)


@pytest.mark.asyncio
async def test_write_package_creates_all_files(
    writer: OutputWriter,
    sample_trend_report: TrendReport,
    sample_niche_report: NicheReport,
    sample_idea_package: IdeaPackage,
    sample_design_prompt: DesignPrompt,
    sample_compliance_report: ComplianceReport,
):
    out_dir = await writer.write_package(
        trend_name="retro gaming shirt",
        concept_index=1,
        trend_report=sample_trend_report,
        niche_report=sample_niche_report,
        idea_package=sample_idea_package,
        design_prompt=sample_design_prompt,
        compliance_report=sample_compliance_report,
    )

    expected_files = [
        "trend_report.json",
        "niche_report.json",
        "idea_package.json",
        "design_prompt.json",
        "compliance_report.json",
        "listing.txt",
        "keywords.txt",
        "final_summary.txt",
    ]
    for fname in expected_files:
        assert (out_dir / fname).exists(), f"Missing: {fname}"


@pytest.mark.asyncio
async def test_json_files_are_valid(
    writer: OutputWriter,
    sample_trend_report: TrendReport,
    sample_niche_report: NicheReport,
    sample_idea_package: IdeaPackage,
    sample_design_prompt: DesignPrompt,
    sample_compliance_report: ComplianceReport,
):
    out_dir = await writer.write_package(
        trend_name="test trend",
        concept_index=1,
        trend_report=sample_trend_report,
        niche_report=sample_niche_report,
        idea_package=sample_idea_package,
        design_prompt=sample_design_prompt,
        compliance_report=sample_compliance_report,
    )

    for fname in [
        "trend_report.json", "niche_report.json", "idea_package.json",
        "design_prompt.json", "compliance_report.json",
    ]:
        content = (out_dir / fname).read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_slugify_and_path_format(
    writer: OutputWriter,
    sample_trend_report: TrendReport,
    sample_niche_report: NicheReport,
    sample_idea_package: IdeaPackage,
    sample_design_prompt: DesignPrompt,
    sample_compliance_report: ComplianceReport,
):
    out_dir = await writer.write_package(
        trend_name="Funny Cat Shirts!!!",
        concept_index=3,
        trend_report=sample_trend_report,
        niche_report=sample_niche_report,
        idea_package=sample_idea_package,
        design_prompt=sample_design_prompt,
        compliance_report=sample_compliance_report,
    )

    # Path should contain slugified name and zero-padded index
    assert "funny-cat-shirts" in str(out_dir)
    assert "concept_03" in str(out_dir)


@pytest.mark.asyncio
async def test_keywords_txt_one_per_line(
    writer: OutputWriter,
    sample_trend_report: TrendReport,
    sample_niche_report: NicheReport,
    sample_idea_package: IdeaPackage,
    sample_design_prompt: DesignPrompt,
    sample_compliance_report: ComplianceReport,
):
    out_dir = await writer.write_package(
        trend_name="test",
        concept_index=1,
        trend_report=sample_trend_report,
        niche_report=sample_niche_report,
        idea_package=sample_idea_package,
        design_prompt=sample_design_prompt,
        compliance_report=sample_compliance_report,
    )

    lines = (out_dir / "keywords.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(sample_idea_package.final_approved_keywords_tags)
