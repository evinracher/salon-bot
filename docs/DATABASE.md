# Database and ORM

## Engine and sessions

- **`app/db.py`**: `create_async_engine(settings.database_url, ...)`, **`async_sessionmaker(..., expire_on_commit=False)`**, dependency **`get_session`** yielding a session with rollback-on-error.
- **Local Postgres (Docker):** `asyncpg_connect_args` disables SSL for `127.0.0.1` / `localhost` URLs (see `app/db.py`).

## Declarative base and naming

- **`Base`** subclasses `DeclarativeBase` with **`MetaData(naming_convention=...)`** for consistent PK/FK/UQ/IX/CK names across autogenerate and hand-written migrations.

## ORM style

- Use **`Mapped[T]`** and **`mapped_column`** for columns.
- Timestamps: **`DateTime(timezone=True)`** with **`server_default=func.now()`** and **`onupdate=func.now()`** where needed.
- Foreign keys: specify **`ondelete`** explicitly (`CASCADE`, `RESTRICT`, etc.) to match product rules.

## Core tables (conceptual)

- **employees**, **services**, **employee_services** (junction), **customers**, **appointments**
- **conversations** (`app/chat/models/conversation.py`) — one row per customer in current schema (`customer_id` unique)

## Alembic

- Config: **`alembic.ini`**, env: **`alembic/env.py`** (async engine + `run_sync` for migrations).
- **`target_metadata = Base.metadata`**; models are imported in `env.py` so metadata is populated (including `Conversation`).

### Dev workflow

```bash
uv run alembic revision --autogenerate -m "describe_change"
uv run alembic upgrade head
```

This repository is **pre-launch**: when the migration graph is rewritten, expect to **drop volumes** and **`alembic upgrade head`** from scratch (see README).

## LangGraph checkpoints

- Checkpoint tables live in the same Postgres database as the app (connection string derived in `app/chat/agent/graph.py`).
- Tests truncate core business tables but **not** checkpoint tables by default; see [RECOMMENDATIONS.md](RECOMMENDATIONS.md) if you need a clean checkpoint slate in CI.

## Indexes

- Appointment range queries may benefit from composite indexes on `(employee_id, start_time)`; not all are present yet — see [RECOMMENDATIONS.md](RECOMMENDATIONS.md).
