"""API response wrappers for agent execution results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CorrectionAttempt(BaseModel):
    """Record of a single self-correction attempt."""

    model_config = ConfigDict(frozen=True)

    attempt_number: int
    raw_payload: dict[str, Any]
    validation_errors: list[dict[str, Any]] | None = None
    succeeded: bool


class AgentExecutionResponse(BaseModel):
    """Response returned by the agent execution endpoint."""

    model_config = ConfigDict(frozen=True)

    success: bool
    tool_name: str
    attempts: int
    max_retries: int
    correction_history: list[CorrectionAttempt] = Field(default_factory=list)
    final_payload: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    error: str | None = None
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    status: str = "ok"
    cloud_provider: str
    llm_mode: str
