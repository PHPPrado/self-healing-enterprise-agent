"""Default (zero-setup) MCP server + validator pipelines."""
from __future__ import annotations

import re
from typing import Any

from app.guardrails.mcp_client import InMemoryMCPClient, InMemoryMCPServer
from app.guardrails.mcp_validator import MCPValidator
from app.guardrails.pipeline import ValidatorPipeline


def _is_vendor(value: Any) -> bool:
    return bool(re.fullmatch(r"VEN-\d{4}", str(value or "")))


def _is_warehouse(value: Any) -> bool:
    return bool(re.fullmatch(r"WH-[A-Z0-9]{3,8}", str(value or "")))


_DEFAULT_SERVER: InMemoryMCPServer | None = None
_DEFAULT_CLIENT: InMemoryMCPClient | None = None


def get_default_mcp_server() -> InMemoryMCPServer:
    global _DEFAULT_SERVER
    if _DEFAULT_SERVER is None:
        _DEFAULT_SERVER = InMemoryMCPServer(
            {
                "validate_vendor": lambda args: {
                    "valid": _is_vendor(args.get("value")),
                    "message": "vendor not found in ERP master data"
                    if not _is_vendor(args.get("value"))
                    else "vendor ok",
                },
                "validate_warehouse": lambda args: {
                    "valid": _is_warehouse(args.get("value")),
                    "message": "warehouse not found"
                    if not _is_warehouse(args.get("value"))
                    else "warehouse ok",
                },
                "validate_fact": lambda args: {"valid": True, "message": "ok"},
            }
        )
    return _DEFAULT_SERVER


def get_default_mcp_client() -> InMemoryMCPClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = InMemoryMCPClient(get_default_mcp_server())
    return _DEFAULT_CLIENT


def get_default_pipeline(tool_name: str) -> ValidatorPipeline:
    pipeline = ValidatorPipeline()
    client = get_default_mcp_client()
    if tool_name == "create_purchase_order":
        pipeline.register(
            MCPValidator(mcp_tool="validate_vendor", client=client), field="vendor_code"
        )
    elif tool_name == "update_inventory":
        pipeline.register(
            MCPValidator(mcp_tool="validate_warehouse", client=client),
            field="warehouse_id",
        )
    return pipeline
