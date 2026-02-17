"""AMZ_Designy - Poe bot command handler."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterable

import fastapi_poe as fp

from app.config import AppConfig
from app.orchestrator import create_pipeline, daily_pipeline, weekly_pipeline

logger = logging.getLogger(__name__)

_HELP_TEXT = """\
**AMZ_Designy Bot Commands**

`/daily` - Run daily trend discovery (TrendScout + NicheAnalyzer)
`/weekly` - Run full weekly pipeline (all 5 agents, end-to-end)
`/create <keyword>` - Create a design package for a specific keyword
`/help` - Show this help message
"""


class DesignyPoeBot(fp.PoeBot):
    """Poe bot for AMZ_Designy pipeline control."""

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self._config = config or AppConfig()  # type: ignore[call-arg]

    async def get_response(
        self,
        request: fp.QueryRequest,
    ) -> AsyncIterable[fp.PartialResponse]:
        """Route incoming messages to command handlers."""
        last_msg = request.query[-1].content.strip()

        if last_msg == "/daily":
            yield fp.PartialResponse(text="Starting daily pipeline...\n")
            result = await self._handle_daily()
            yield fp.PartialResponse(text=result)

        elif last_msg == "/weekly":
            yield fp.PartialResponse(text="Starting weekly pipeline...\n")
            result = await self._handle_weekly()
            yield fp.PartialResponse(text=result)

        elif last_msg.startswith("/create "):
            keyword = last_msg[len("/create "):].strip()
            if not keyword:
                yield fp.PartialResponse(
                    text="Usage: `/create <keyword>`",
                )
                return
            yield fp.PartialResponse(
                text=f"Creating design package for '{keyword}'...\n",
            )
            result = await self._handle_create(keyword)
            yield fp.PartialResponse(text=result)

        elif last_msg == "/help":
            yield fp.PartialResponse(text=_HELP_TEXT)

        else:
            yield fp.PartialResponse(
                text="Unknown command. Type `/help` for available commands.",
            )

    async def _handle_daily(self) -> str:
        try:
            report = await daily_pipeline(self._config)
            return (
                f"Daily pipeline complete.\n"
                f"Niches found: {len(report.entries)}"
            )
        except Exception as e:
            logger.exception("Daily pipeline failed")
            return f"Daily pipeline failed: {e}"

    async def _handle_weekly(self) -> str:
        try:
            record_ids = await weekly_pipeline(self._config)
            return (
                f"Weekly pipeline complete.\n"
                f"Ideas published: {len(record_ids)}"
            )
        except Exception as e:
            logger.exception("Weekly pipeline failed")
            return f"Weekly pipeline failed: {e}"

    async def _handle_create(self, keyword: str) -> str:
        try:
            rec_id = await create_pipeline(self._config, keyword)
            if rec_id:
                return f"Design package created. Airtable record: {rec_id}"
            return "Design package created but not approved for Airtable."
        except Exception as e:
            logger.exception("Create pipeline failed")
            return f"Create pipeline failed: {e}"
