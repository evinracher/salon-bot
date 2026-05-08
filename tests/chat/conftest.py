import pytest

from app.main import app


@pytest.fixture(autouse=True)
def _default_chat_runtime_available() -> None:
    app.state.chat_available = True
    if getattr(app.state, "chat_graph", None) is None:
        app.state.chat_graph = object()
