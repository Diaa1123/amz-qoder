"""AMZ_Designy - Application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    # API Keys
    poe_access_key: SecretStr = Field(..., description="Poe API access key")
    airtable_api_key: SecretStr = Field(
        ..., description="Airtable personal access token",
    )
    airtable_base_id: str = Field(..., description="Airtable base ID")
    airtable_table_id: str = Field(..., description="Airtable Ideas table ID")
    airtable_niche_table_id: str = Field(
        ..., description="Airtable Weekly Niche table ID",
    )

    # LLM
    llm_model: str = Field(default="gpt-4o", description="LLM model identifier")
    image_model: str = Field(
        default="dall-e-3", description="Image generation model",
    )
    max_tokens: int = Field(default=4000, description="Max tokens for LLM responses")
    temperature: float = Field(default=0.7, description="LLM temperature (0.0-1.0)")

    # Pipeline
    min_niche_score: float = Field(
        default=6.5, description="Minimum opportunity score threshold",
    )
    max_designs_per_run: int = Field(
        default=10, description="Max design packages per weekly run",
    )
    auto_publish: bool = Field(
        default=False, description="Auto-publish approved ideas to Airtable",
    )

    # Storage
    output_dir: Path = Field(
        default=Path("./outputs"), description="Local output directory",
    )

    # Scheduler
    daily_run_time: str = Field(default="09:00", description="Daily job time (HH:MM)")
    weekly_run_day: int = Field(
        default=0, description="Weekly job day (0=Monday)",
    )
    timezone: str = Field(default="Asia/Riyadh", description="Scheduler timezone")

    # Monitoring
    log_level: str = Field(default="INFO", description="Logging level")
