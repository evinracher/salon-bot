from fastapi import FastAPI, HTTPException, Request
from langgraph.graph.state import CompiledStateGraph


def ensure_chat_available(request: Request) -> None:
    if not getattr(request.app.state, "chat_available", False):
        raise HTTPException(status_code=503, detail="chat runtime unavailable")


def get_compiled_graph_from_app(app: FastAPI) -> CompiledStateGraph:
    if not getattr(app.state, "chat_available", False):
        raise RuntimeError("Chat runtime unavailable")
    graph = getattr(app.state, "chat_graph", None)
    if graph is None:
        raise RuntimeError("Chat graph is not initialized")
    return graph


def get_compiled_graph(request: Request) -> CompiledStateGraph:
    return get_compiled_graph_from_app(request.app)
