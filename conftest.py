import os

_db_user = os.getenv("DB_USER", "user")
_db_password = os.getenv("DB_PASSWORD", "password")
_db_host = os.getenv("DB_HOST", "127.0.0.1")
_db_port = os.getenv("DB_PORT", "5433")
_test_db_name = os.getenv("TEST_DB_NAME", "salon_bot_test")

_default_test_url = (
    f"postgresql+asyncpg://{_db_user}:{_db_password}"
    f"@{_db_host}:{_db_port}/{_test_db_name}"
)
_effective_test_url = os.getenv("TEST_DATABASE_URL") or _default_test_url

assert "test" in _effective_test_url, "refusing to run tests against non-test DB"

os.environ["DATABASE_URL"] = _effective_test_url
