"""MCP-backed factual validator."""
from __future__ import annotations

import re
from typing import Any

from app.guardrails.base_validator import BaseValidator
from app.guardrails.exceptions import FactualValidationError
from app.guardrails.mcp_client import MCPClient


class MCPValidator(BaseValidator):
    """Layer-2 validator that delegates fact-checking to an MCP server.

    Acts as an MCP client: it calls a named MCP tool (``mcp_tool``) passing the
    LLM-generated value (and surrounding context) and interprets the result.
    Expected result shape (dict): ``{"valid": bool, "message": str, "errors": [...]}``.
    """

    name = "mcp"

    def __init__(
        self,
        mcp_tool: str,
        client: MCPClient | None = None,
        field_name: str | None = None,
    ) -> None:
        self.mcp_tool = mcp_tool
        self.client = client
        self.field_name = field_name

    async def _get_client(self) -> MCPClient:
        if self.client is not None:
            return self.client
        from app.guardrails import get_default_mcp_client

        return get_default_mcp_client()

    async def validate(
        self, field_value: Any, context: dict[str, Any] | None = None
    ) -> None:
        ctx = context or {}
        field = ctx.get("field") or self.field_name
        payload = ctx.get("payload")
        client = await self._get_client()

        arguments: dict[str, Any] = {
            "value": field_value,
            "field": field,
            "payload": payload,
            "tool_name": ctx.get("tool_name"),
        }

        try:
            result = await client.call_tool(self.mcp_tool, arguments)
        except Exception as exc:  # noqa: BLE001
            raise FactualValidationError(
                [
                    {
                        "loc": [field] if field else [],
                        "msg": f"MCP call failed: {exc}",
                        "type": "mcp_error",
                        "input": field_value,
                    }
                ]
            )

        ok = True
        message: str | None = None
        errors: list[dict[str, Any]] | None = None

        if isinstance(result, dict):
            if "valid" in result:
                ok = bool(result.get("valid"))
            elif "ok" in result:
                ok = bool(result.get("ok"))
            message = result.get("message") or result.get("error")
            errors = result.get("errors")
        elif isinstance(result, (list, tuple)):
            # Heuristic: treat empty list as ok.
            ok = len(result) == 0
            message = str(result) if result else None
        else:
            ok = bool(getattr(result, "valid", True))

        if ok:
            return

        err_list: list[dict[str, Any]]
        if errors:
            err_list = [dict(e) for e in errors]
        else:
            err_list = [
                {
                    "loc": [field] if field else [],
                    "msg": message or "Factual validation failed via MCP",
                    "type": "factual",
                    "input": field_value,
                }
            ]

        for e in err_list:
            e.setdefault("loc", [field] if field else [])
            e.setdefault("msg", message or "invalid")
            e.setdefault("type", "factual")
            e.setdefault("input", field_value)

        raise FactualValidationError(err_list)


# Convenience: a regex helper used by default mock server (re-export).
__all__ = ["MCPValidator", "re"]
