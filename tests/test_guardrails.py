"""Tests for layered guardrails."""
from __future__ import annotations

import pytest

from app.guardrails.base_validator import BaseValidator
from app.guardrails.exceptions import FactualValidationError
from app.guardrails.mcp_client import InMemoryMCPClient, InMemoryMCPServer
from app.guardrails.mcp_validator import MCPValidator
from app.guardrails.pipeline import ValidatorPipeline


class _PassValidator(BaseValidator):
    async def validate(self, field_value, context=None):
        return None


class _FailValidator(BaseValidator):
    async def validate(self, field_value, context=None):
        raise FactualValidationError(
            [{"loc": ["x"], "msg": "bad", "type": "factual", "input": field_value}]
        )


@pytest.mark.asyncio
async def test_pipeline_runs_registered_validator_and_raises():
    pipeline = ValidatorPipeline()
    pipeline.register(_FailValidator(), field="x")
    with pytest.raises(FactualValidationError) as exc:
        await pipeline.validate_payload({"x": 1}, {"payload": {"x": 1}})
    assert exc.value.errors[0]["msg"] == "bad"


@pytest.mark.asyncio
async def test_pipeline_passes_when_validator_ok():
    pipeline = ValidatorPipeline()
    pipeline.register(_PassValidator(), field="x")
    await pipeline.validate_payload({"x": 1}, {"payload": {"x": 1}})


@pytest.mark.asyncio
async def test_mcp_validator_uses_client():
    server = InMemoryMCPServer(
        {"check": lambda args: {"valid": args.get("value") == "ok", "message": "nope"}}
    )
    client = InMemoryMCPClient(server)
    v = MCPValidator(mcp_tool="check", client=client, field_name="field")
    await v.validate("ok", {"field": "field", "payload": {"field": "ok"}})
    with pytest.raises(FactualValidationError):
        await v.validate("bad", {"field": "field", "payload": {"field": "bad"}})


@pytest.mark.asyncio
async def test_default_pipeline_vendor_validation():
    from app.guardrails import get_default_pipeline

    pipeline = get_default_pipeline("create_purchase_order")
    # valid vendor passes
    await pipeline.validate_payload(
        {"vendor_code": "VEN-1234"}, {"payload": {"vendor_code": "VEN-1234"}}
    )
    with pytest.raises(FactualValidationError):
        await pipeline.validate_payload(
            {"vendor_code": "VEN-12"}, {"payload": {"vendor_code": "VEN-12"}}
        )
