# salon-bot

Pre-launch: **no backward compatibility** for old Alembic revisions or mixed schema states. After migration graph changes, **wipe the DB and migrate from scratch**.

## API (dev)

```bash
cp .env.example .env
docker compose up -d db
uv sync --all-groups
uv run alembic upgrade head
uv run python main.py
```

- **`DATABASE_URL`** (required): SQLAlchemy async URL for the app — see [`.env.example`](.env.example).
- **`DB_*`** in `.env` are for Docker Compose Postgres only; they do not build URLs automatically.

## Hard reset database (when migrations change)

```bash
docker compose down -v
docker compose up -d db
uv run alembic upgrade head
```

Then run checks:

```bash
uv run mypy .
uv run ruff check .
uv run pytest -q
```

## Tests

Uses database **`salon_bot_test`** on the same Postgres service. Initial volume create runs [`scripts/init-test-db.sh`](scripts/init-test-db.sh).

**`TEST_DATABASE_URL`** is required (see `.env.example`). Root [`conftest.py`](conftest.py) loads `.env`, checks the URL looks like a test DB, then sets `DATABASE_URL` for the app during pytest.

If `salon_bot_test` is missing (old volume):

```bash
docker compose exec db psql -U user -d postgres -c 'CREATE DATABASE salon_bot_test;'
uv run pytest
```
