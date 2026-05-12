from fastapi import Depends, HTTPException, Request, status


def ensure_chat_available(request: Request) -> None:
    if not request.app.state.chat_available:
        err = getattr(request.app.state, "chat_init_error", None)
        detail = (
            f"Chat service is unavailable: {err}"
            if err
            else "Chat service is unavailable"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


def get_compiled_graph(request: Request, _: None = Depends(ensure_chat_available)):
    graph = request.app.state.chat_graph
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat graph is not initialized",
        )
    return graph
