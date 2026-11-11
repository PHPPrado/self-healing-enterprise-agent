"""MCP (Model Context Protocol) client abstractions.

Provides a transport-agnostic ``MCPClient`` interface plus an in-memory
implementation (zero-setup / tests) and an optional SDK-backed client that
uses the official ``mcp`` package when installed.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class MCPClient(ABC):
    """Transport-agnostic MCP client interface."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a tool on the MCP server and return its result."""


class InMemoryMCPServer:
    """A tiny in-memory MCP server for zero-setup execution and tests."""

    def __init__(self, tools: dict[str, Callable[[dict[str, Any]], Any]] | None = None):
        self._tools: dict[str, Callable[[dict[str, Any]], Any]] = dict(tools or {})

    def register(self, name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._tools[name] = handler

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown MCP tool: {name}")
        handler = self._tools[name]
        result = handler(arguments)
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[misc]
        return result


class InMemoryMCPClient(MCPClient):
    def __init__(self, server: InMemoryMCPServer):
        self.server = server

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self.server.call_tool(name, arguments)


class SDKMCPClient(MCPClient):
    """Optional client backed by the official ``mcp`` SDK (stdio transport)."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env
        self._session: Any = None
        self._cm: Any = None

    async def _ensure(self) -> None:
        if self._session is not None:
            return
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("mcp package is required for SDKMCPClient") from exc

        params = StdioServerParameters(command=self.command, args=self.args, env=self.env)
        self._cm = stdio_client(params)
        read, write = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        await self._ensure()
        assert self._session is not None
        result = await self._session.call_tool(name, arguments)
        content = getattr(result, "content", result)
        return content

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)
            self._cm = None
