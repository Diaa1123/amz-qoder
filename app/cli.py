"""AMZ_Designy - Dev/testing CLI entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.config import AppConfig
from app.orchestrator import create_pipeline, daily_pipeline, weekly_pipeline
from app.utils.logger import get_logger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AMZ_Designy CLI (dev/testing)",
    )
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "create"],
        required=True,
        help="Pipeline mode to run",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Keyword for create mode",
    )
    args = parser.parse_args()

    if args.mode == "create" and not args.keyword:
        parser.error("--keyword is required for create mode")

    config = AppConfig()  # type: ignore[call-arg]
    logger = get_logger("cli", config.log_level)

    logger.info("Running %s pipeline via CLI", args.mode)

    if args.mode == "daily":
        result = asyncio.run(daily_pipeline(config))
        logger.info("Done. Niches found: %d", len(result.entries))

    elif args.mode == "weekly":
        record_ids = asyncio.run(weekly_pipeline(config))
        logger.info("Done. Ideas published: %d", len(record_ids))

    elif args.mode == "create":
        rec_id = asyncio.run(create_pipeline(config, args.keyword))
        if rec_id:
            logger.info("Done. Airtable record: %s", rec_id)
        else:
            logger.info("Done. Package created but not approved for Airtable.")


if __name__ == "__main__":
    main()
