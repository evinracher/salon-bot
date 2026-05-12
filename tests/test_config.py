import pytest

from app.config import Settings


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        Settings(
            database_url="postgresql+asyncpg://u:p@127.0.0.1:5433/salon_bot_test",
            timezone="Not/A_Valid_Zone_Name_XYZ",
        )
