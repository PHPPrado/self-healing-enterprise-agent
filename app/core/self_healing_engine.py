"""Core self-healing execution engine.

Implements the loop: Try -> Validate -> Catch -> Reflect -> Retry.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from app.adapters.base import BaseCloudAdapter
from app.config import settings
from app.core.llm_client import LLMClient
from app.guardrails import get_default_pipeline
from app.guardrails.exceptions import FactualValidationError
from app.guardrails.pipeline import ValidatorPipeline
from app.schemas.agent_response import CorrectionAttempt
from app.schemas.enterprise_payloads import get_schema

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an enterprise operations agent. You must respond with a single JSON "
    "object that conforms exactly to the provided tool schema. Do not include "
    "markdown, explanations, or extra keys. Only output valid JSON."
)


def _format_errors(errors: list[dict[str, Any]]) -> str:
    lines = []
    for err in errors:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        inp = err.get("input", None)
        lines.append(f"- field '{loc}': {msg} (received: {inp!r})")
    return "\n".join(lines)


class SelfHealingAgentEngine:
    """Orchestrates LLM generation, Pydantic validation, and self-correction."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        adapter: BaseCloudAdapter | None = None,
        max_retries: int | None = None,
        schema_provider: Callable[[str], type[BaseModel]] = get_schema,
        guardrail_provider: Callable[[str], ValidatorPipeline] = get_default_pipeline,
    ) -> None:
        self.llm = llm_client or LLMClient()
        self.adapter = adapter
        self.max_retries = (
            max_retries if max_retries is not None else settings.max_self_healing_retries
        )
        self._schema_provider = schema_provider
        self._guardrail_provider = guardrail_provider

    async def _get_adapter(self) -> BaseCloudAdapter:
        if self.adapter is not None:
            return self.adapter
        from app.adapters.cloud_adapter import get_cloud_adapter

        self.adapter = get_cloud_adapter()
        return self.adapter


    async def execute(
        self,
        user_goal: str | None = None,
        tool_name: str = "create_purchase_order",
        goal: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if user_goal is None:
            user_goal = goal or kwargs.get("instruction") or kwargs.get("request") or ""
        if not user_goal:
            user_goal = "Execute the requested enterprise operation."

        schema = self._schema_provider(tool_name)
        adapter = await self._get_adapter()
        pipeline = self._guardrail_provider(tool_name)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Goal: {user_goal}\n"
                    f"Tool: {tool_name}\n"
                    f"Required JSON schema (Pydantic): {schema.__name__}\n"
                    "Generate the JSON payload now."
                ),
            },
        ]

        correction_history: list[CorrectionAttempt] = []
        attempts = 0
        final_payload: dict[str, Any] | None = None
        last_raw: str | None = None
        last_errors: list[dict[str, Any]] | None = None

        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            attempts = attempt

            try:
                raw = await self.llm.complete(messages)
            except Exception as exc:  # noqa: BLE001
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "attempts": attempts,
                    "max_retries": self.max_retries,
                    "correction_history": [c.model_dump(mode="json") for c in correction_history],
                    "final_payload": None,
                    "execution_result": None,
                    "error": f"LLM call failed: {exc}",
                }

            last_raw = raw
            parsed: dict[str, Any] | None = None
            parse_error: str | None = None
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("LLM response is not a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                parse_error = str(exc)

            validation_errors: list[dict[str, Any]] | None = None
            model_instance: BaseModel | None = None
            validation_ok = False

            if parse_error is not None:
                validation_errors = [
                    {"loc": [], "msg": f"Invalid JSON: {parse_error}", "input": raw}
                ]
            else:
                try:
                    model_instance = schema.model_validate(parsed)
                except ValidationError as exc:
                    validation_errors = []
                    for e in exc.errors():
                        validation_errors.append(
                            {
                                "loc": [str(p) for p in e.get("loc", ())],
                                "msg": e.get("msg"),
                                "type": e.get("type"),
                                "input": e.get("input", None),
                            }
                        )
                    model_instance = None
                else:
                    # Layer 2: factual/semantic validation via guardrail pipeline (MCP).
                    payload_for_validation = model_instance.model_dump(mode="json")
                    try:
                        await pipeline.validate_payload(
                            payload_for_validation,
                            {
                                "tool_name": tool_name,
                                "payload": payload_for_validation,
                                "schema": schema,
                            },
                        )
                        validation_ok = True
                    except FactualValidationError as exc:
                        validation_errors = list(exc.errors) if exc.errors else [
                            {
                                "loc": [],
                                "msg": str(exc),
                                "type": "factual",
                                "input": payload_for_validation,
                            }
                        ]
                    except Exception as exc:  # noqa: BLE001
                        validation_errors = [
                            {
                                "loc": [],
                                "msg": str(exc),
                                "type": "factual_error",
                                "input": payload_for_validation,
                            }
                        ]

            raw_payload_for_record = parsed if parsed is not None else {"_raw": raw}
            correction_history.append(
                CorrectionAttempt(
                    attempt_number=attempt,
                    raw_payload=raw_payload_for_record,
                    validation_errors=validation_errors,
                    succeeded=validation_ok,
                )
            )

            if validation_ok and model_instance is not None:
                final_payload = model_instance.model_dump(mode="json")
                try:
                    exec_result = await adapter.execute(tool_name, final_payload)
                except Exception as exc:  # noqa: BLE001
                    return {
                        "success": False,
                        "tool_name": tool_name,
                        "attempts": attempts,
                        "max_retries": self.max_retries,
                        "correction_history": [c.model_dump(mode="json") for c in correction_history],
                        "final_payload": final_payload,
                        "execution_result": None,
                        "error": f"Adapter execution failed: {exc}",
                    }
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "attempts": attempts,
                    "max_retries": self.max_retries,
                    "correction_history": [c.model_dump(mode="json") for c in correction_history],
                    "final_payload": final_payload,
                    "execution_result": exec_result,
                    "error": None,
                }

            last_errors = validation_errors
            err_text = _format_errors(validation_errors or [])
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous JSON failed validation. "
                        "Fix the following errors and return ONLY the corrected JSON object.\n"
                        f"VALIDATION ERRORS:\n{err_text}\n"
                        "Do not include any explanation."
                    ),
                }
            )

        return {
            "success": False,
            "tool_name": tool_name,
            "attempts": attempts,
            "max_retries": self.max_retries,
            "correction_history": [c.model_dump(mode="json") for c in correction_history],
            "final_payload": final_payload,
            "execution_result": None,
            "error": "Max self-healing retries exhausted. Last errors: "
            + (_format_errors(last_errors) if last_errors else "unknown"),
        }
