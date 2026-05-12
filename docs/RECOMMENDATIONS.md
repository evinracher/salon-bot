# Recommendations backlog

Prioritized improvements **not** implemented in the initial standards pass. Effort is rough (S/M/L).

## P1 — Reliability and performance

| Item | Rationale | Effort |
|------|-----------|--------|
| Engine **`pool_pre_ping=True`**, **`pool_recycle`**, tuned **`pool_size`/`max_overflow`** | Safer long-lived connections behind Uvicorn workers | S |
| B-tree indexes on **`appointments(employee_id, start_time)`** and/or **`appointments(start_time)`** | Faster overlap + range filters at scale | S |
| Shared **`httpx.AsyncClient`** (lifespan) for WhatsApp sends | Connection reuse, timeouts, fewer TLS handshakes | M |
| Truncate LangGraph **checkpoint** tables in test **`_truncate_tables`** (or separate test DB) | Deterministic agent tests when checkpoint state matters | M |

## P1 — Security and operations

| Item | Rationale | Effort |
|------|-----------|--------|
| Replace **`allow_origins=["*"]`** with env-driven allowlist | Production CORS hardening | S |
| Rate limiting on **`/chat`** and/or webhooks | Abuse mitigation | M |
| **`SECURITY.md`** with reporting + secret rotation guidance | Open-source hygiene | S |

## P1 — API ergonomics

| Item | Rationale | Effort |
|------|-----------|--------|
| Pagination (`limit`/`offset`) on list endpoints | Large datasets | M |
| **`Path(..., gt=0)`** on numeric path params | Clearer 422 vs 404 semantics | S |
| Global exception handlers (422/500 JSON shape) | Consistent clients | M |
| FastAPI **`version`**, **`description`**, **`openapi_tags`** | Better `/docs` | S |

## P1 — Pydantic

| Item | Rationale | Effort |
|------|-----------|--------|
| **`ConfigDict(extra="forbid", str_strip_whitespace=True)`** on input models | Stricter API contracts | M |
| **`Annotated[datetime, AwareDatetime]`** (or validators) on appointment bodies | Explicit tz policy in OpenAPI | M |

## P1 — Domain structure

| Item | Rationale | Effort |
|------|-----------|--------|
| Move **`customers_router`** from `app/chat/api.py` to **`app/api/customers.py`** | Clearer REST ownership | M |
| Shared **`app/services/customers.py`** for upsert-by-phone | Single identity strategy for chat + REST | M |

## P1 — Logging

| Item | Rationale | Effort |
|------|-----------|--------|
| Use **structlog** in **`app/chat/bootstrap.py`** instead of stdlib `logging` | Uniform structured logs | S |
| Echo inbound **`X-Request-Id`** (or generate) on **`X-Request-Id`** response header | Cross-service traceability | S |

## P2 — Agent

| Item | Rationale | Effort |
|------|-----------|--------|
| Document or migrate toward explicit **`StateGraph`** if debugging needs improve | Transparency of branches | L |
| Narrow **`Any`** in `SalonState` / middleware generics | mypy signal | M |
| Extend Groq fallbacks beyond **`RateLimitError`** | Transient API errors | S |
| Structured logging inside long tools | Ops visibility | S |

## P2 — Infrastructure

| Item | Rationale | Effort |
|------|-----------|--------|
| **`Dockerfile`** + **`.dockerignore`** for the API | Deployable artifact | M |
| GitHub Actions: ruff, mypy, pytest, **`alembic check`** | CI guardrails | M |
| **`Makefile`** / **`justfile`** for common commands | DX | S |
| **`LICENSE`**, **`CHANGELOG.md`** | Distribution norms | S |

## P2 — Tests

| Item | Rationale | Effort |
|------|-----------|--------|
| DST transition tests for availability/appointments | Correctness in non-fixed-offset zones | M |
| OpenAPI contract snapshot test | Catch accidental API breaks | M |

## P2 — Configuration hygiene

| Item | Rationale | Effort |
|------|-----------|--------|
| Remove unused **`CORS_ALLOWED_ORIGINS`** from local `.env` **or** wire through **`Settings`** | Less confusion | S |
| Align **`.env`** and **`.env.example`** keys/ports | Onboarding friction | S |

## P2 — WhatsApp / jobs

| Item | Rationale | Effort |
|------|-----------|--------|
| Outbox / retry for outbound sends after successful DB commit | Exactly-once-ish user experience | L |
| **`removeOnComplete: True`** vs age/count policy tuning | Redis memory tradeoffs | S |

---

When picking up an item, add a short design note to the PR and update **`docs/`** if user-visible behavior changes.
