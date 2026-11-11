"""Layered guardrails package.

Layer 1: Pydantic v2 (syntactic) -- handled in schemas/engine.
Layer 2: Factual/semantic validators (plugin system) -- this package.
"""
from __future__ import annotations

from typing import Callable

from app.guardrails.base_validator import BaseValidator
from app.guardrails.exceptions import FactualValidationError
from app.guardrails.mcp_client import (
    InMemoryMCPClient,
    InMemoryMCPServer,
    MCPClient,
    SDKMCPClient,
)
from app.guardrails.mcp_validator import MCPValidator
from app.guardrails.pipeline import ValidatorPipeline


def get_default_mcp_client():
    from app.guardrails.default_validators import get_default_mcp_client as _get

    return _get()


def get_default_pipeline(tool_name: str) -> ValidatorPipeline:
    from app.guardrails.default_validators import get_default_pipeline as _get

    return _get(tool_name)


__all__ = [
    "BaseValidator",
    "FactualValidationError",
    "MCPClient",
    "InMemoryMCPClient",
    "InMemoryMCPServer",
    "SDKMCPClient",
    "MCPValidator",
    "ValidatorPipeline",
    "get_default_mcp_client",
    "get_default_pipeline",
]
