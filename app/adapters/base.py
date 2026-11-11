"""Abstract base class defining the CloudAdapter contract.

All cloud adapters (Mock, AWS, OCI, GCP, Azure) must implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseCloudAdapter(ABC):
    """Contract for executing enterprise operations against a cloud backend."""

    provider_name: str = "BASE"

    @abstractmethod
    async def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a validated enterprise operation.

        Args:
            tool_name: The logical tool name (e.g. "create_purchase_order").
            payload: The validated (and serialized) payload.

        Returns:
            A dict describing the execution result.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is reachable/healthy."""
