import pytest
from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.chat.agent.graph import build_chat_model
from app.config import settings


def test_build_chat_model_groq_single_when_no_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_fallback_models", "")
    monkeypatch.setattr(settings, "groq_model", "llama-3.1-8b-instant")
    monkeypatch.setattr(settings, "groq_api_key", "")
    m = build_chat_model()
    assert isinstance(m, ChatGroq)
    assert m.model_name == "llama-3.1-8b-instant"


def test_build_chat_model_groq_chain_with_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_llm_provider", "groq")
    monkeypatch.setattr(
        settings,
        "groq_fallback_models",
        " llama-3.1-8b-instant , llama-3.3-70b-specdec ",
    )
    monkeypatch.setattr(settings, "groq_model", "primary-model")
    monkeypatch.setattr(settings, "groq_api_key", "")
    m = build_chat_model()
    assert isinstance(m, RunnableWithFallbacks)
    assert len(m.fallbacks) == 2  # type: ignore[attr-defined]


def test_build_chat_model_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "chat_llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-dummy-key-for-unit-test")
    m = build_chat_model()
    assert isinstance(m, ChatOpenAI)
    assert m.model_name == "gpt-4o-mini"


def test_build_chat_model_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "chat_llm_provider", "azure")
    with pytest.raises(ValueError, match="Unsupported chat_llm_provider"):
        build_chat_model()
