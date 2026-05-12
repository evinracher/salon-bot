# Contributing

## Setup

```bash
uv sync --all-groups
cp .env.example .env
# Set DATABASE_URL and TEST_DATABASE_URL; optional LLM keys for chat tests that hit the graph.
docker compose up -d db redis
uv run alembic upgrade head
```

## Commands

| Command | Purpose |
|---------|---------|
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format (or `ruff format --check .` in CI) |
| `uv run mypy .` | Static types (`typings/` for third-party stubs) |
| `uv run pytest -q` | Full test suite (Postgres required) |

## Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Ruff is configured in `pyproject.toml` (`[tool.ruff]` / `[tool.ruff.lint]`). Some rules are ignored globally for common FastAPI patterns (e.g. `B008` for `Query`/`Depends` defaults) and per-file for long prompt strings and Alembic revisions.

Pre-commit hooks run Ruff (check + format), mypy, and pytest on every commit (see `.pre-commit-config.yaml`).

- Keep changes focused; reference related **`docs/`** updates when behavior changes.
- Run **`uv run ruff check .`**, **`uv run mypy .`**, and **`uv run pytest`** before pushing.
- For schema changes, include Alembic revision(s) and mention whether a **DB wipe** is required (pre-launch expectation).

## Documentation

- User-facing behavior: update **`README.md`** or the relevant **`docs/*.md`** file.
- Agent/human onboarding: update **`AGENTS.md`** when conventions change.
