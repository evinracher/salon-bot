import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

_test_url = os.getenv("TEST_DATABASE_URL", "").strip()
if not _test_url:
    msg = (
        "TEST_DATABASE_URL must be set for pytest "
        "(postgresql+asyncpg://user:password@host:port/salon_bot_test)"
    )
    raise RuntimeError(msg)

_effective_test_url = _test_url
assert "test" in _effective_test_url.lower(), "refusing to run tests against non-test DB"

os.environ["DATABASE_URL"] = _effective_test_url
