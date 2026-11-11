"""Abstract base class for pluggable (factual/semantic) validators."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseValidator(ABC):
    """Plugin interface for Layer-2 validators.

    Implementations must be async and raise ``FactualValidationError`` when the
    value is not factually/semantically valid. Returning normally means "ok".
    """

    name: str = "base"

    @abstractmethod
    async def validate(
        self, field_value: Any, context: dict[str, Any] | None = None
    ) -> None:
        """Validate ``field_value`` against external/semantic sources."""
        raise NotImplementedError
