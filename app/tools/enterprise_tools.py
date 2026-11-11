"""Executable enterprise business logic triggered after successful self-correction."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def dispatch_purchase_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Simulate dispatching a validated purchase order to an ERP system."""
    logger.info("dispatch_purchase_order", extra={"order_id": payload.get("order_id")})
    return {
        "erp_reference": f"ERP-PO-{str(payload.get('order_id'))[:8]}",
        "vendor_code": payload.get("vendor_code"),
        "amount": payload.get("amount"),
        "currency": payload.get("currency"),
        "items_count": len(payload.get("items", [])),
        "status": "dispatched",
    }


def adjust_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    """Simulate applying an inventory delta."""
    logger.info("adjust_inventory", extra={"sku": payload.get("sku")})
    return {
        "warehouse_id": payload.get("warehouse_id"),
        "sku": payload.get("sku"),
        "delta_applied": payload.get("delta"),
        "reason": payload.get("reason"),
        "status": "applied",
    }


TOOL_DISPATCHERS: dict[str, Any] = {
    "create_purchase_order": dispatch_purchase_order,
    "update_inventory": adjust_inventory,
}


def run_tool(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name not in TOOL_DISPATCHERS:
        raise KeyError(f"No dispatcher registered for tool: {tool_name}")
    return TOOL_DISPATCHERS[tool_name](payload)
