from fastapi import Depends, HTTPException, Request, status


def ensure_chat_available(request: Request) -> None:
    if not getattr(request.app.state, "chat_available", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is unavailable",
        )


def get_compiled_graph(request: Request, _: None = Depends(ensure_chat_available)):
    graph = getattr(request.app.state, "chat_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat graph is not initialized",
        )
    return graph
