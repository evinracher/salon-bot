# salon-bot

## API (dev)

```bash
cp .env.example .env
docker compose up -d db
uv sync --all-groups
uv run alembic upgrade head
uv run python main.py
```

- DB config is loaded from `.env` (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).
- You can also override with full URLs via `DATABASE_URL` and `TEST_DATABASE_URL`.

## Tests

Uses database **`salon_bot_test`** on the same Postgres service. Initial volume create runs `scripts/init-test-db.sh`. If `salon_bot_test` is missing (old volume):

```bash
docker compose exec db psql -U user -d postgres -c 'CREATE DATABASE salon_bot_test;'
uv run pytest
```
