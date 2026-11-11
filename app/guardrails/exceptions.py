"""Custom exceptions for layered (factual/semantic) guardrails."""
from __future__ import annotations

from typing import Any


class FactualValidationError(Exception):
    """Raised when Layer-2 factual/semantic validation fails.

    ``errors`` is a list of dicts shaped like Pydantic's error dicts so the
    reflection loop can format them uniformly (loc/msg/input).
    """

    def __init__(
        self,
        errors: list[dict[str, Any]] | None = None,
        message: str | None = None,
    ) -> None:
        self.errors: list[dict[str, Any]] = list(errors or [])
        super().__init__(message or "Factual validation failed")

    def to_validation_errors(self) -> list[dict[str, Any]]:
        return self.errors
