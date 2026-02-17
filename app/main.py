"""AMZ_Designy - FastAPI + Poe bot production server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import AppConfig
from app.integrations.poe_bot import DesignyPoeBot
from app.jobs.scheduler import init_scheduler, shutdown_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start scheduler on startup, stop on shutdown."""
    config = AppConfig()  # type: ignore[call-arg]
    init_scheduler(config)
    logger.info("AMZ_Designy server started")
    yield
    await shutdown_scheduler()
    logger.info("AMZ_Designy server stopped")


app = FastAPI(title="AMZ_Designy", lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# Poe webhook
_config = None
try:
    _config = AppConfig()  # type: ignore[call-arg]
except Exception:
    pass  # Config loaded at lifespan; this is for the bot route setup

if _config is not None:
    poe_bot = DesignyPoeBot(_config)
    app.post("/poe/webhook")(poe_bot.get_endpoint())
