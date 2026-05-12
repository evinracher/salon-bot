"""Inline stubs for bullmq (no upstream py.typed)."""

from typing import Any

class Queue:
    def __init__(self, name: str, connection: str | dict[str, object]) -> None: ...
    async def add(
        self,
        name: str,
        data: dict[str, Any],
        opts: dict[str, object] | None = None,
    ) -> Any: ...
    async def close(self) -> None: ...

class Worker:
    def __init__(
        self,
        name: str,
        processor: Any,
        opts: dict[str, Any],
    ) -> None: ...
    async def close(self) -> None: ...
