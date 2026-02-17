"""AMZ_Designy - Poe LLM wrapper for structured and text-based calls."""

from __future__ import annotations

import json
import logging
from typing import Type

from pydantic import BaseModel

from app.config import AppConfig
from app.utils.retries import retry_with_backoff

logger = logging.getLogger(__name__)


class PoeClient:
    """Wraps the Poe API (via fastapi_poe) for LLM calls."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._api_key = config.poe_access_key.get_secret_value()
        self._model = config.llm_model
        self._max_tokens = config.max_tokens
        self._temperature = config.temperature

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    async def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[BaseModel],
    ) -> BaseModel:
        """Make an LLM call and validate the response against *response_model*.

        The LLM is instructed to return JSON matching the Pydantic schema.
        If parsing fails, a retry with a stricter prompt is attempted
        (handled by the retry decorator).
        """
        import fastapi_poe as fp  # deferred to avoid import at module level

        schema_hint = json.dumps(
            response_model.model_json_schema(), indent=2,
        )
        full_system = (
            f"{system_prompt}\n\n"
            "You MUST respond with valid JSON matching this schema exactly:\n"
            f"```json\n{schema_hint}\n```\n"
            "Do NOT include any text outside the JSON block."
        )

        messages = [
            fp.ProtocolMessage(role="system", content=full_system),
            fp.ProtocolMessage(role="user", content=user_message),
        ]

        response_text = ""
        async for partial in fp.get_bot_response(
            messages=messages,
            bot_name=self._model,
            api_key=self._api_key,
        ):
            response_text += partial.text

        # Strip markdown fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        return response_model.model_validate(data)

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    async def call_llm_text(
        self,
        system_prompt: str,
        user_message: str,
    ) -> str:
        """Make an LLM call and return the raw text response."""
        import fastapi_poe as fp

        messages = [
            fp.ProtocolMessage(role="system", content=system_prompt),
            fp.ProtocolMessage(role="user", content=user_message),
        ]

        response_text = ""
        async for partial in fp.get_bot_response(
            messages=messages,
            bot_name=self._model,
            api_key=self._api_key,
        ):
            response_text += partial.text

        return response_text.strip()
