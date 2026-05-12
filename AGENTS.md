# Agent / contributor guide

Use this file with AI coding agents and new human contributors. Deep dives live under `docs/`.

## Tech stack

- **Python 3.12**, **FastAPI**, **Pydantic v2**, **pydantic-settings**
- **SQLAlchemy 2.0 async** + **asyncpg** (`postgresql+asyncpg://...`)
- **Alembic** (async online migrations)
- **LangGraph** + **LangChain** agents (`create_agent`, Postgres checkpointer)
- **structlog** (+ stdlib logging bridge in `app/logging.py`)
- **BullMQ** (Python) + **Redis** for WhatsApp inbound queue
- **httpx** for outbound WhatsApp Graph API

## Repository layout

```
app/
  main.py           # FastAPI app, lifespan, CORS, routers
  config.py         # Settings (env); single `settings` instance
  db.py             # async engine, sessionmaker, get_session
  logging.py        # structlog + request context middleware
  api/              # REST: employees, services, appointments, availability, ...
  chat/             # Simulated chat, customers router, WhatsApp webhook + queue + agent
  models/           # Core ORM (Employee, Service, Appointment, Customer, ...)
  schemas/          # Pydantic API models
  services/         # Pure/domain helpers (datetime_utils, availability, salon_availability)
alembic/            # migrations
tests/              # pytest; tests/chat/ for agent + WhatsApp
typings/bullmq/     # Inline stubs (upstream lacks py.typed)
docs/               # Architecture, dates, API, DB, queues, agent, testing, recommendations
```

## Conventions (do)

- Use **`AsyncSession`** everywhere in request paths and tools; never block the event loop with sync DB or `time.sleep`.
- Route DB access through **`get_session`** or explicit `async_session_maker()` in workers (see WhatsApp processor).
- Read configuration only from **`app.config.settings`** (or explicit `Settings(...)` in tests). Avoid new `os.getenv` calls except bootstrap/test glue documented in `docs/RECOMMENDATIONS.md`.
- **Datetimes:** see [docs/DATES.md](docs/DATES.md). Prefer **timezone-aware** values; naive values in APIs are interpreted as **wall clock in `settings.timezone`**. Never use `datetime.utcnow()` (deprecated).
- **Logging:** prefer **`structlog.get_logger(__name__)`** for new modules; keep messages structured (`key=value` fields).
- **Types:** annotate public functions; narrow `Any` where LangChain types allow.
- **Migrations:** change ORM + add Alembic revision; this project currently assumes **dev DB reset** when the graph changes (see README).

## Conventions (don't)

- Don't commit **`.env`** or secrets.
- Don't add blocking I/O inside `async def` routes or agent tools.
- Don't bypass **`ensure_aware_in_timezone`** for user-facing appointment bounds when comparing to DB `timestamptz` rows (list filters use it in `app/api/appointments.py`).
- Don't swallow exceptions without logging or re-raise unless the behavior is explicitly documented (e.g. webhook ACK strategy).

## Adding a REST entity (pattern)

1. **`app/models/<name>.py`** — `Mapped[...]`, `DateTime(timezone=True)` for timestamps, FKs with explicit `ondelete`.
2. **Alembic** — `uv run alembic revision --autogenerate -m "..."` then review/edit.
3. **`app/schemas/<name>.py`** — `Create` / `Update` / `Read` with `ConfigDict(from_attributes=True)` on reads.
4. **`app/api/<name>.py`** — router with `SessionDep`, `response_model`, explicit `status_code`, `HTTPException` for 404/409.
5. **`app/main.py`** — `include_router` if new top-level router.
6. **Tests** under `tests/`.

## Adding an agent tool

1. Implement in **`app/chat/agent/tools.py`** using `@tool` and **async** def.
2. Use **`current_session.get()`** from `app/chat/agent/runtime.py` for DB (set only during `run_turn`).
3. For state patches (preferences), call **`merge_salon_state_patch(...)`**; `run_turn` merges into checkpoint after invoke.
4. Register in **`ALL_TOOLS`**.
5. Document behavior in **`docs/AGENT_RUNTIME.md`** if non-obvious.
6. Add tests in **`tests/chat/`** (session + fake graph patterns).

## WhatsApp / BullMQ

- Webhook: **`app/chat/whatsapp_api.py`** — verification GET, POST ACK + enqueue.
- Queue/worker: **`app/chat/whatsapp_queue.py`** — job id `wa-{message_id}` for deduplication.
- Processor: **`app/chat/whatsapp_processor.py`** — DB + `process_inbound_chat_turn` + outbound send.

See [docs/QUEUES.md](docs/QUEUES.md) for signature verification and retry semantics.

## Where to look

| Task | Start here |
|------|------------|
| Change business hours / slots | `app/config.py`, `app/services/availability.py` |
| Appointment validation | `app/api/appointments.py`, `app/services/datetime_utils.py` |
| Agent prompt / model | `app/chat/agent/prompts.py`, `app/chat/agent/graph.py` |
| Tool SQL | `app/chat/agent/tools.py` |
| Env var | `app/config.py`, `.env.example` |
