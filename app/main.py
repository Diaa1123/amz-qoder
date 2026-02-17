"""AMZ_Designy - FastAPI + Poe bot production server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import fastapi_poe as fp
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import AppConfig
from app.integrations.poe_bot import DesignyPoeBot
from app.jobs.scheduler import init_scheduler, shutdown_scheduler
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Register Poe bot routes, start scheduler on startup, stop on shutdown."""
    config = AppConfig()  # type: ignore[call-arg]

    # Build the Poe bot with its webhook mounted at /poe/webhook
    bot = DesignyPoeBot(
        config,
        path="/poe/webhook",
        access_key=config.poe_access_key.get_secret_value(),
    )
    fp.make_app(bot, app=app, allow_without_key=True)

    init_scheduler(config)
    logger.info("AMZ_Designy server started")
    yield
    await shutdown_scheduler()
    logger.info("AMZ_Designy server stopped")


app = FastAPI(title="AMZ_Designy", lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
