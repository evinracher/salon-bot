"""One linear pass: after each AI tool-call batch, every id must have a ToolMessage."""

from __future__ import annotations

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage

_EMPTY_TOOL = "{}"


def ensure_tool_call_responses(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Copy ``messages``; for any ``AIMessage.tool_calls`` missing a ``ToolMessage``, append ``{}``."""
    out: list[AnyMessage] = []
    i, n = 0, len(messages)
    while i < n:
        m = messages[i]
        if not isinstance(m, AIMessage) or not (m.tool_calls or []):
            out.append(m)
            i += 1
            continue

        out.append(m)
        j = i + 1
        by_id: dict[str, ToolMessage] = {}
        while j < n:
            nxt = messages[j]
            if not isinstance(nxt, ToolMessage):
                break
            by_id[nxt.tool_call_id] = nxt
            j += 1

        for tc in m.tool_calls or []:
            tid = tc["id"]
            if tid in by_id:
                out.append(by_id[tid])
            else:
                out.append(
                    ToolMessage(
                        content=_EMPTY_TOOL,
                        tool_call_id=tid,
                        name=tc.get("name") or "",
                    )
                )
        i = j
    return out
