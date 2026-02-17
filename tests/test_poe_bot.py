"""Integration tests for the Poe bot command handler."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.poe_bot import DesignyPoeBot
from app.schemas import NicheReport


def _make_config() -> MagicMock:
    cfg = MagicMock()
    cfg.poe_access_key.get_secret_value.return_value = "test-key"
    cfg.airtable_api_key.get_secret_value.return_value = "test-key"
    cfg.airtable_base_id = "appTEST"
    cfg.airtable_table_id = "tblTEST"
    cfg.airtable_niche_table_id = "tblNICHE"
    cfg.llm_model = "gpt-4o"
    cfg.max_tokens = 4000
    cfg.temperature = 0.7
    cfg.min_niche_score = 6.5
    cfg.max_designs_per_run = 10
    cfg.output_dir = "outputs"
    return cfg


def _make_request(content: str) -> MagicMock:
    """Build a mock fp.QueryRequest with a single message."""
    req = MagicMock()
    msg = MagicMock()
    msg.content = content
    req.query = [msg]
    return req


class TestDesignyPoeBot:
    @pytest.mark.asyncio
    async def test_help_command(self):
        bot = DesignyPoeBot(_make_config())
        responses = [r async for r in bot.get_response(_make_request("/help"))]
        assert any("AMZ_Designy Bot Commands" in r.text for r in responses)

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        bot = DesignyPoeBot(_make_config())
        responses = [r async for r in bot.get_response(_make_request("hello"))]
        assert any("Unknown command" in r.text for r in responses)

    @pytest.mark.asyncio
    @patch("app.integrations.poe_bot.run_daily")
    async def test_daily_command(self, mock_daily: AsyncMock):
        mock_daily.return_value = NicheReport(
            entries=[], created_at=datetime.now(),
        )

        bot = DesignyPoeBot(_make_config())
        responses = [r async for r in bot.get_response(_make_request("/daily"))]

        mock_daily.assert_called_once()
        texts = " ".join(r.text for r in responses)
        assert "complete" in texts.lower() or "pipeline" in texts.lower()

    @pytest.mark.asyncio
    @patch("app.integrations.poe_bot.run_weekly")
    async def test_weekly_command(self, mock_weekly: AsyncMock):
        mock_weekly.return_value = ["rec_1", "rec_2"]

        bot = DesignyPoeBot(_make_config())
        responses = [r async for r in bot.get_response(_make_request("/weekly"))]

        mock_weekly.assert_called_once()
        texts = " ".join(r.text for r in responses)
        assert "2" in texts  # 2 ideas published

    @pytest.mark.asyncio
    @patch("app.integrations.poe_bot.run_create")
    async def test_create_command(self, mock_create: AsyncMock):
        mock_create.return_value = "rec_abc123"

        bot = DesignyPoeBot(_make_config())
        responses = [
            r async for r in bot.get_response(_make_request("/create cat shirt"))
        ]

        mock_create.assert_called_once_with(bot._config, "cat shirt")
        texts = " ".join(r.text for r in responses)
        assert "rec_abc123" in texts

    @pytest.mark.asyncio
    async def test_create_command_no_keyword(self):
        bot = DesignyPoeBot(_make_config())
        responses = [
            r async for r in bot.get_response(_make_request("/create "))
        ]
        texts = " ".join(r.text for r in responses)
        assert "usage" in texts.lower() or "keyword" in texts.lower()

    @pytest.mark.asyncio
    @patch("app.integrations.poe_bot.run_daily")
    async def test_daily_command_error(self, mock_daily: AsyncMock):
        mock_daily.side_effect = RuntimeError("Boom")

        bot = DesignyPoeBot(_make_config())
        responses = [r async for r in bot.get_response(_make_request("/daily"))]

        texts = " ".join(r.text for r in responses)
        assert "failed" in texts.lower()
