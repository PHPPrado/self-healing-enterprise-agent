"""Tests for the self-healing loop."""

from __future__ import annotations

import pytest

from app.core.self_healing_engine import SelfHealingAgentEngine
from app.schemas.enterprise_payloads import CreatePurchaseOrderSchema


@pytest.mark.asyncio
async def test_self_healing_succeeds_on_second_attempt():
    engine = SelfHealingAgentEngine()
    result = await engine.execute(user_goal="Create a purchase order for 2 units")

    assert result["success"] is True
    assert result["attempts"] == 2
    assert result["error"] is None

    history = result["correction_history"]
    assert len(history) == 2
    assert history[0]["succeeded"] is False
    assert history[1]["succeeded"] is True

    # first failure should mention vendor_code
    first_errors = history[0]["validation_errors"]
    assert first_errors is not None
    fields = [str(e.get("loc")) for e in first_errors]
    assert any("vendor_code" in f for f in fields)

    exec_result = result["execution_result"]
    assert exec_result is not None
    assert exec_result["status"] == "success"
    assert exec_result["provider"] == "MOCK"


@pytest.mark.asyncio
async def test_no_http_500_on_initial_failure():
    # The engine must absorb validation errors internally.
    engine = SelfHealingAgentEngine(max_retries=1)
    result = await engine.execute(user_goal="Create a purchase order")
    assert "error" not in result or result.get("success") is True
    assert isinstance(result["attempts"], int)


@pytest.mark.asyncio
async def test_max_retries_zero_fails_gracefully():
    engine = SelfHealingAgentEngine(max_retries=0)
    result = await engine.execute(user_goal="Create a purchase order")
    assert result["success"] is False
    assert result["attempts"] == 1
    assert result["execution_result"] is None
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_final_payload_validates_against_schema():
    engine = SelfHealingAgentEngine()
    result = await engine.execute(user_goal="Create a purchase order")
    assert result["success"] is True
    CreatePurchaseOrderSchema.model_validate(result["final_payload"])


@pytest.mark.asyncio
async def test_update_inventory_tool():
    engine = SelfHealingAgentEngine()
    # mock LLM always returns purchase order payload, so this path exercises schema mismatch;
    # instead validate adapter directly
    from app.adapters.cloud_adapter import MockCloudAdapter

    adapter = MockCloudAdapter()
    res = await adapter.execute(
        "update_inventory",
        {
            "warehouse_id": "WH-ABC123",
            "sku": "ABC-123",
            "delta": 5,
            "reason": "restock",
        },
    )
    assert res["status"] == "success"
    assert res["business_result"]["status"] == "applied"
