# Agent runtime (LangGraph + LangChain)

## High-level design

- The agent is built with **`langchain.agents.create_agent`** in **`app/chat/agent/graph.py`** (not a hand-authored `StateGraph` with explicit nodes in this repo).
- **Checkpointing:** **`AsyncPostgresSaver.from_conn_string`** — conversation state keyed by LangGraph **`thread_id`**.
- **Thread id:** **`runner._thread_config`** sets **`configurable.thread_id = str(conversation.id)`** so each `Conversation` row maps to one checkpoint thread.

## Model selection

- **`build_chat_model()`** chooses Groq or OpenAI from **`settings.chat_llm_provider`**.
- Groq optional **`RunnableWithFallbacks`** on **`groq.RateLimitError`** when **`GROQ_FALLBACK_MODELS`** is set.

## State schema

- **`SalonState`** (`app/chat/agent/state.py`) extends LangChain **`AgentState`** with optional fields: `flow`, `employee_id`, `service_id`, `preferred_service_id`, `preferred_employee_id`, plus `remaining_steps` for the managed reducer.

## Middleware

1. **`SanitizeToolMessagesMiddleware`** — coerces **`ToolMessage`** content so Groq/OpenAI get non-empty string JSON where needed; runs **`ensure_tool_call_responses`** (`message_repair.py`) so every `tool_calls` id has a reply.
2. **`SafeToolErrorResponseMiddleware`** — catches tool exceptions and returns a **`ToolMessage`** with JSON `{"error": {"type", "message"}}` instead of failing the whole turn.

## DB session inside tools

- **`current_session`** (`ContextVar`) in **`app/chat/agent/runtime.py`** is set in **`run_turn`** before **`graph.ainvoke`** and reset in `finally`.
- Tools call **`_get_session()`** which requires the ContextVar (raises if unset — e.g. wrong call context).

## Preference patching

- Tools call **`merge_salon_state_patch(preferred_service_id=..., preferred_employee_id=...)`** into a dict bag; **`run_turn`** calls **`graph.aupdate_state`** after invoke if the bag is non-empty.

## Prompting

- **`salon_system_prompt`** (`prompts.py`) includes **`settings.timezone`**, tool documentation, Spanish UX hints for availability blocks, and an injected **authoritative local datetime** ISO string from **`run_turn`** so relative phrases ("hoy", "mañana") anchor to server time in the salon zone.

## Manual owner messages

- **`inject_manual_ai_message`** appends an **`AIMessage`** via **`aupdate_state`** (used for operator overrides / testing).

## Related tests

- `tests/chat/test_runner.py`, `tests/chat/test_chat_api.py`, `tests/chat/test_message_repair.py`, `tests/chat/test_chat_model_factory.py`
