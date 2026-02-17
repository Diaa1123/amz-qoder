"""AMZ_Designy - FastAPI + Poe bot production server."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import AppConfig
from app.integrations.poe_bot import DesignyPoeBot
from app.jobs.scheduler import init_scheduler, shutdown_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _load_config() -> AppConfig:
    return AppConfig()  # type: ignore[call-arg]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start scheduler on startup, stop on shutdown."""
    config = _load_config()
    init_scheduler(config)
    logger.info("AMZ_Designy server started")
    yield
    await shutdown_scheduler()
    logger.info("AMZ_Designy server stopped")


app = FastAPI(title="AMZ_Designy", lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# Poe webhook -- registered at module level (Railway env vars always present).
_config = _load_config()
_bot = DesignyPoeBot(_config)
app.add_api_route("/poe/webhook", _bot.get_endpoint(), methods=["POST"])
