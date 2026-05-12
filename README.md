# salon-bot

FastAPI backend for a salon: REST APIs for employees, services, appointments, and availability; a LangGraph-based chat agent (simulated HTTP chat and WhatsApp via Meta Cloud API); Postgres (SQLAlchemy 2.0 async) and optional Redis/BullMQ for inbound WhatsApp jobs.

**Pre-launch:** there is **no backward compatibility** for old Alembic revisions or mixed schema states. After migration graph changes, **wipe the DB and migrate from scratch**.

## Documentation

| Doc | Purpose |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Conventions for humans and AI agents (layout, do/don't, how to extend) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components and request flows |
| [docs/DATES.md](docs/DATES.md) | Timezone and datetime policy |
| [docs/API.md](docs/API.md) | REST API conventions |
| [docs/DATABASE.md](docs/DATABASE.md) | ORM, migrations, schema notes |
| [docs/QUEUES.md](docs/QUEUES.md) | BullMQ, WhatsApp webhooks, idempotency |
| [docs/AGENT_RUNTIME.md](docs/AGENT_RUNTIME.md) | LangGraph agent, tools, checkpointing |
| [docs/TESTING.md](docs/TESTING.md) | Pytest, DB isolation, chat fakes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Local dev workflow and checks |
| [docs/RECOMMENDATIONS.md](docs/RECOMMENDATIONS.md) | Prioritized backlog (non-critical improvements) |

## Prerequisites

- Python **3.12** (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for installs and commands
- Docker (for Postgres + optional Redis via `compose.yml`)

## Quickstart (API + DB)

```bash
cp .env.example .env
# Edit .env: set DATABASE_URL, TEST_DATABASE_URL, and LLM keys if you use chat.

docker compose up -d db redis
uv sync --all-groups
uv run alembic upgrade head
uv run python main.py
```

- **`DATABASE_URL`** (required): SQLAlchemy **async** URL, e.g. `postgresql+asyncpg://user:password@127.0.0.1:5433/salon_bot` — see [`.env.example`](.env.example).
- **`DB_*`** keys are for Docker Compose Postgres only; they do not build `DATABASE_URL` automatically.

OpenAPI UI: `http://localhost:<APP_PORT>/docs` (default port from `APP_PORT` in `.env`).

## Environment variables (summary)

Full list and comments live in [`.env.example`](.env.example). Groups:

| Area | Variables |
|------|-----------|
| Compose / local Postgres | `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` |
| App DB | `DATABASE_URL` |
| Tests | `TEST_DATABASE_URL` (must contain `test`; root `conftest.py` forces `DATABASE_URL` during pytest) |
| Server | `APP_PORT` |
| Business calendar | `TIMEZONE`, `SLOT_INTERVAL_MINUTES`, `BUSINESS_OPEN_TIME`, `BUSINESS_CLOSE_TIME`, `BUSINESS_DAYS` |
| Chat LLM | `CHAT_LLM_PROVIDER`, `GROQ_*`, `OPENAI_*`, `CHAT_MAX_TOOL_ITERS` (see `app/config.py` for env names) |
| Redis / BullMQ | `REDIS_URL`, `WHATSAPP_QUEUE_NAME`, `WHATSAPP_WORKER_CONCURRENCY`, `WHATSAPP_JOB_ATTEMPTS` |
| WhatsApp (Meta) | `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_GRAPH_API_VERSION` |
| Logging | `LOG_JSON` (`true`/`1` for JSON logs; see `app/logging.py`) |

## Hard reset database (when migrations change)

```bash
docker compose down -v
docker compose up -d db redis
uv run alembic upgrade head
```

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -q
# Optional coverage (see pyproject [tool.coverage]):
uv run pytest --cov=app --cov-report=term-missing
```

Pre-commit runs Ruff, mypy, and pytest (see `.pre-commit-config.yaml`).

## Tests

Uses database **`salon_bot_test`** on the same Postgres service. On first volume init, [`scripts/init-test-db.sh`](scripts/init-test-db.sh) creates `salon_bot_test`.

**`TEST_DATABASE_URL`** is required. Root [`conftest.py`](conftest.py) loads `.env`, refuses non-test URLs, then sets `DATABASE_URL` for the test process.

If `salon_bot_test` is missing (old volume):

```bash
docker compose exec db psql -U user -d postgres -c 'CREATE DATABASE salon_bot_test;'
uv run pytest
```

## Troubleshooting

- **Chat 503 on `/chat/*`:** graph/checkpointer failed at startup; check logs (`chat_runtime_init_failed`). Often missing LLM API key or DB URL for LangGraph Postgres saver.
- **WhatsApp jobs not running:** ensure `REDIS_URL` is set and `docker compose up -d redis`; worker starts in app lifespan when Redis is configured.
- **Webhook 403 with secret set:** `X-Hub-Signature-256` must match HMAC-SHA256 of the **raw** POST body with `WHATSAPP_APP_SECRET` (see [docs/QUEUES.md](docs/QUEUES.md)).
