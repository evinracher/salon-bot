# Testing

## Layout

- **`tests/`** — REST and shared services (`test_appointments.py`, `test_availability.py`, `test_datetime_utils.py`, …).
- **`tests/chat/`** — chat API, runner, WhatsApp webhook/processor/schemas, fake graph fixtures.

## Environment

- Root **`conftest.py`**: loads `.env`, requires **`TEST_DATABASE_URL`** containing `test`, sets **`DATABASE_URL`** for the process.
- **`tests/conftest.py`**:
  - **`_disable_whatsapp_bullmq_redis`**: forces **`settings.redis_url = ""`** so the app lifespan does not require Redis unless a test overrides.
  - **`_alembic_upgrade`**: session-scoped `alembic upgrade head` against the test DB URL.
  - **`_truncate_tables`**: autouse async fixture truncates core tables **before and after** each test (`TRUNCATE ... RESTART IDENTITY CASCADE`).
  - **`client`**: **`httpx.AsyncClient`** with **`ASGITransport(app=app)`**.

## Async pytest

- Configured in **`pyproject.toml`**: `asyncio_mode = "auto"`, session-scoped default loop for async fixtures.

## Faking the LangGraph graph

- **`tests/chat/conftest.py`** defines **`fake_graph`** and **`FakeGraph`** with **`ainvoke`**, **`aget_state`**, **`aupdate_state`** to avoid live LLM/Postgres saver during HTTP tests.

## Running tests

```bash
uv run pytest -q
uv run pytest tests/chat -q
uv run pytest tests/test_appointments.py -q
```

## Coverage

- Dev dependency **`pytest-cov`**; configuration under **`[tool.coverage.*]`** in `pyproject.toml`.
- Example: `uv run pytest --cov=app --cov-report=term-missing`
