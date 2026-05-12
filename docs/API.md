# HTTP API conventions

## Base URL and OpenAPI

- Default: `http://localhost:{APP_PORT}` (see `APP_PORT` in `.env`).
- Interactive docs: **`GET /docs`**, schema: **`GET /openapi.json`** (FastAPI defaults).

## Router layout

| Prefix | Module | Tags |
|--------|--------|------|
| `/employees` | `app/api/employees.py` | employees |
| `/services` | `app/api/services.py` | services |
| `/employee-services` | `app/api/employee_services.py` | employee-services |
| `/appointments` | `app/api/appointments.py` | appointments |
| `/availability` | `app/api/availability.py` | availability |
| `/chat` | `app/chat/api.py` | chat |
| `/customers` | `app/chat/api.py` | customers |
| `/webhooks/whatsapp` | `app/chat/whatsapp_api.py` | whatsapp |

## Session and transactions

- Endpoints use **`AsyncSession`** from **`Depends(get_session)`** (`app/db.py`).
- **`get_session`** rolls back on exception; successful routes call **`await session.commit()`** explicitly after mutations.

## Response models and status codes

- Mutations return **`response_model`** where applicable and explicit **`status_code`** (e.g. `201` for creates, `204` for deletes).
- Errors use **`HTTPException`** with `detail` string or structured `detail` (FastAPI default JSON: `{"detail": ...}`).

## Datetime query parameters

- **`GET /appointments`**: `from` and `to` (aliases for `from_time` / `to_time`) are normalized to **`settings.timezone`** via **`ensure_aware_in_timezone`** so naive ISO strings match DB `timestamptz` consistently. See [DATES.md](DATES.md).

## Idempotency

- **POST** creates (employees, etc.) are not globally idempotent unless the DB constraint says so (e.g. unique phone on customers).
- **WhatsApp** inbound deduplication uses BullMQ **`jobId = wa-{message_id}`** (see [QUEUES.md](QUEUES.md)).

## Pagination (current and planned)

- List endpoints today return full lists (no `limit`/`offset`). Adding pagination is tracked in [RECOMMENDATIONS.md](RECOMMENDATIONS.md).

## CORS

- `app/main.py` configures permissive origins for development (`allow_origins=["*"]`). Tighten for production (same file; backlog in RECOMMENDATIONS).
