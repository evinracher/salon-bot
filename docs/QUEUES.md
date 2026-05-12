# Queues (BullMQ) and WhatsApp webhooks

## Redis and BullMQ

- When **`REDIS_URL`** is non-empty, **`start_whatsapp_worker`** (`app/chat/whatsapp_queue.py`) constructs a **`Queue`** and **`Worker`** bound to **`settings.whatsapp_queue_name`**.
- When **`REDIS_URL`** is empty (default in tests via `tests/conftest.py`), enqueue is a no-op log and the worker is not started.

## Job payload

Inbound jobs use name **`whatsappInbound`** with data:

- `wa_id` — sender WhatsApp ID (digits)
- `text` — message body
- `profile_name` — optional display name from webhook contacts map
- `message_id` — Meta message id (`wamid.*`)

## Idempotency and retries

- **`jobId`**: `wa-{message_id}` so duplicate webhook deliveries dedupe in Redis when Meta retries.
- **`attempts`**: from **`WHATSAPP_JOB_ATTEMPTS`** (default 3).
- **`backoff`**: exponential, base delay 1000 ms (see `whatsapp_queue.py`).
- **`removeOnComplete`** / **`removeOnFail`**: bounded retention (age + count) to avoid unbounded Redis growth.

## Processor contract

- **`process_whatsapp_inbound_job`** (`app/chat/whatsapp_processor.py`):
  - Invalid payload (missing `wa_id` / `text`): logs and **returns** (no retry).
  - Chat graph unavailable: **`RuntimeError`** so BullMQ can retry (until attempts exhausted).
  - Success path: DB commit during turn processing; outbound send uses httpx separately (send failures may still occur after DB work — see backlog for outbox pattern).

## Webhook verification (GET)

- Meta sends `hub.mode`, `hub.verify_token`, `hub.challenge`.
- App compares **`hub.verify_token`** to **`WHATSAPP_VERIFY_TOKEN`** and returns the challenge as plain text.

## Webhook POST security

When **`WHATSAPP_APP_SECRET`** is set (Meta App Secret, used for app-level webhooks):

1. Read the **raw** request body bytes.
2. Compute **`HMAC-SHA256(secret, raw_body)`** and compare to the **`X-Hub-Signature-256`** header value **`sha256=<hex>`** using a constant-time compare.
3. On mismatch or missing header (when secret is set), respond **`403 Forbidden`**.
4. When the secret is **empty**, signature verification is **skipped** (local dev convenience); still return **`200`** for malformed JSON to avoid aggressive Meta retries where appropriate.

Configure the same secret in the Meta developer dashboard and in `.env` as **`WHATSAPP_APP_SECRET`**.

## Related files

- `app/chat/whatsapp_api.py` — HTTP layer
- `app/chat/whatsapp_queue.py` — enqueue + worker lifecycle
- `app/chat/whatsapp_processor.py` — job handler
- `app/chat/whatsapp_client.py` — outbound Graph API
- `app/chat/whatsapp_schemas.py` — minimal dict parsing of Meta payloads
