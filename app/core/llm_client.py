"""Universal LLM client with built-in Mock mode for zero-setup execution."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_CORRECTION_KEYWORDS = ("validation errors", "fix the following", "corrected json", "previous json failed")


class LLMClient:
    """Thin async wrapper around an LLM provider.

    When ``LLM_API_KEY`` is ``mock`` (or empty) the client runs in Mock mode
    and simulates a self-healing scenario: the first completion returns an
    invalid payload, subsequent (reflection) completions return a valid one.
    """

    def __init__(self) -> None:
        self._call_count = 0
        self._openai_client: Any = None
        if not settings.is_mock_llm:
            self._init_remote_client()

    def _init_remote_client(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for non-mock LLM mode") from exc
        self._openai_client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def complete(self, messages: list[dict[str, str]], temperature: float | None = None) -> str:
        """Return a raw string completion (expected to be JSON for tool calls)."""
        self._call_count += 1
        if settings.is_mock_llm:
            return self._mock_complete(messages)
        return await self._remote_complete(messages, temperature)

    async def _remote_complete(self, messages: list[dict[str, str]], temperature: float | None) -> str:
        assert self._openai_client is not None
        response = await self._openai_client.chat.completions.create(
            model=settings.llm_model_name,
            messages=messages,
            temperature=temperature if temperature is not None else settings.llm_temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        logger.info("llm.remote.complete", extra={"model": settings.llm_model_name})
        return content

    def _mock_complete(self, messages: list[dict[str, str]]) -> str:
        joined = " ".join(m.get("content", "") for m in messages).lower()
        is_correction = any(kw in joined for kw in _CORRECTION_KEYWORDS)

        # First-ever call returns an invalid payload to demonstrate self-healing.
        if not is_correction and self._call_count == 1:
            payload = {
                "order_id": str(uuid.uuid4()),
                "amount": 100.0,
                "currency": "USD",
                "vendor_code": "VEN-12",  # invalid: must be VEN-XXXX
                "items": [{"sku": "ABC-123", "quantity": 2, "unit_price": 50.0}],
                "priority": "high",
                "requested_by": "procurement-bot",
            }
            logger.info("mock_llm returning INVALID payload (attempt %d)", self._call_count)
            return json.dumps(payload)

        payload = {
            "order_id": str(uuid.uuid4()),
            "amount": 100.0,
            "currency": "USD",
            "vendor_code": "VEN-1234",
            "items": [{"sku": "ABC-123", "quantity": 2, "unit_price": 50.0}],
            "priority": "high",
            "requested_by": "procurement-bot",
        }
        logger.info("mock_llm returning VALID payload (attempt %d)", self._call_count)
        return json.dumps(payload)

    async def aclose(self) -> None:
        if self._openai_client is not None:
            await self._openai_client.close()
