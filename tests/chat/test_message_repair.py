from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.chat.agent.message_repair import ensure_tool_call_responses


def test_repair_inserts_missing_tool_messages() -> None:
    ai = AIMessage(
        content="",
        tool_calls=[
            {"id": "call_a", "name": "list_services", "args": {}},
            {"id": "call_b", "name": "list_employees", "args": {}},
        ],
    )
    only_b = ToolMessage(content="[]", tool_call_id="call_b", name="list_employees")
    human = HumanMessage(content="next")

    out = ensure_tool_call_responses([ai, only_b, human])
    assert len(out) == 4
    assert isinstance(out[0], AIMessage)
    assert isinstance(out[1], ToolMessage)
    assert out[1].tool_call_id == "call_a"
    assert out[1].content == "{}"
    assert isinstance(out[2], ToolMessage)
    assert out[2].tool_call_id == "call_b"
    assert isinstance(out[3], HumanMessage)


def test_repair_preserves_complete_tool_block() -> None:
    ai = AIMessage(
        content="",
        tool_calls=[{"id": "x", "name": "list_services", "args": {}}],
    )
    tm = ToolMessage(content='{"ok": true}', tool_call_id="x", name="list_services")
    out = ensure_tool_call_responses([ai, tm])
    assert out == [ai, tm]
