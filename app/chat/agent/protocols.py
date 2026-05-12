"""Typing-only protocols for compiled LangGraph agents used outside the graph module."""

from __future__ import annotations

from typing import Any, Protocol


class CompiledSalonAgent(Protocol):
    """Minimal surface used by ``runner`` and tests (``ainvoke``, checkpoint helpers)."""

    async def ainvoke(
        self,
        input: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def aupdate_state(
        self,
        config: dict[str, Any],
        values: dict[str, Any],
        as_node: str | None = None,
        task_id: str | None = None,
    ) -> Any: ...

    async def aget_state(
        self, config: dict[str, Any], *, subgraphs: bool = False
    ) -> Any: ...
