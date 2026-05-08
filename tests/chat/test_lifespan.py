import pytest

from app.db import dispose_db_runtime, get_engine, init_db_runtime
from app.main import app


@pytest.mark.asyncio
async def test_lifespan_initializes_and_cleans_runtime_state() -> None:
    await dispose_db_runtime()
    async with app.router.lifespan_context(app):
        assert app.state.db_session_maker is not None
        assert get_engine() is app.state.db_engine
    with pytest.raises(RuntimeError, match="Database engine is not initialized"):
        get_engine()
    init_db_runtime()
