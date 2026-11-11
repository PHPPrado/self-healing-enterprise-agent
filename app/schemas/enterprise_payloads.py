"""Pydantic v2 guardrail schemas for enterprise payloads.

These models are the deterministic guardrails: any LLM-generated payload must
validate against them before reaching the cloud adapter.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrderItem(BaseModel):
    """A single line item in a purchase order."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sku: str = Field(..., min_length=3, max_length=32, description="Stock keeping unit code")
    quantity: int = Field(..., gt=0, le=10_000, description="Ordered quantity")
    unit_price: float = Field(..., gt=0, description="Unit price in the order currency")

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{2,31}", value):
            raise ValueError("sku must start with an alphanumeric and contain only A-Z, 0-9, '-'")
        return value


class CreatePurchaseOrderSchema(BaseModel):
    """Strict schema for a CreatePurchaseOrder enterprise tool call."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    order_id: uuid.UUID = Field(..., description="Unique purchase order identifier (UUID)")
    amount: float = Field(..., gt=0, description="Total order amount, must be positive")
    currency: Literal["USD", "EUR", "BRL", "GBP"] = Field(default="USD", description="ISO currency code")
    vendor_code: str = Field(..., description="Vendor code in format VEN-XXXX")
    items: list[OrderItem] = Field(..., min_length=1, description="At least one order item")
    priority: Literal["low", "normal", "high", "critical"] = Field(default="normal")
    requested_by: str = Field(..., min_length=2, max_length=64)
    created_at: datetime | None = Field(default=None)

    @field_validator("vendor_code")
    @classmethod
    def validate_vendor_code(cls, value: str) -> str:
        if not re.fullmatch(r"VEN-\d{4}", value):
            raise ValueError("vendor_code must match pattern VEN-XXXX (e.g. VEN-1234)")
        return value

    @field_validator("amount")
    @classmethod
    def validate_amount_precision(cls, value: float) -> float:
        # guard against absurd precision / NaN
        if value != value:  # NaN check
            raise ValueError("amount cannot be NaN")
        return round(value, 2)

    @model_validator(mode="after")
    def validate_total_consistency(self) -> "CreatePurchaseOrderSchema":
        computed = round(sum(i.quantity * i.unit_price for i in self.items), 2)
        if abs(computed - self.amount) > 0.01:
            raise ValueError(
                f"amount ({self.amount}) does not match sum of items ({computed})"
            )
        return self

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            # assume UTC if naive
            return value.replace(tzinfo=timezone.utc)
        return value


class UpdateInventorySchema(BaseModel):
    """Strict schema for an inventory adjustment tool call."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    warehouse_id: str = Field(..., min_length=3, max_length=16)
    sku: str = Field(..., min_length=3, max_length=32)
    delta: int = Field(..., description="Positive to add stock, negative to remove")
    reason: str = Field(..., min_length=3, max_length=128)

    @field_validator("warehouse_id")
    @classmethod
    def validate_warehouse_id(cls, value: str) -> str:
        if not re.fullmatch(r"WH-[A-Z0-9]{3,8}", value):
            raise ValueError("warehouse_id must match WH-XXX (alphanumeric)")
        return value


# Registry mapping tool name -> schema. Extensible.
TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "create_purchase_order": CreatePurchaseOrderSchema,
    "update_inventory": UpdateInventorySchema,
}


def get_schema(tool_name: str) -> type[BaseModel]:
    if tool_name not in TOOL_SCHEMAS:
        raise KeyError(f"Unknown tool schema: {tool_name}")
    return TOOL_SCHEMAS[tool_name]
