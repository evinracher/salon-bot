from fastapi import FastAPI, Request
from langgraph.graph.state import CompiledStateGraph


def get_compiled_graph_from_app(app: FastAPI) -> CompiledStateGraph:
    graph = getattr(app.state, "chat_graph", None)
    if graph is None:
        raise RuntimeError("Chat graph is not initialized")
    return graph


def get_compiled_graph(request: Request) -> CompiledStateGraph:
    return get_compiled_graph_from_app(request.app)
