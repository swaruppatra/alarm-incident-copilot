import httpx

from apps.frontend.config import get_settings


class CopilotClientError(Exception):
    """Raised when the copilot-backend is unreachable or returns an error response."""


def _post(path: str, json_body: dict) -> dict:
    """POST to the copilot-backend and return the decoded JSON body.

    Args:
        path (str): the endpoint path, e.g. "/chat".
        json_body (dict): the request body.

    Returns:
        dict: the decoded JSON response.

    Raises:
        CopilotClientError: on a network failure or a non-2xx response.
    """
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.backend_url}{path}", json=json_body, timeout=settings.request_timeout_seconds
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise CopilotClientError(f"Backend returned {exc.response.status_code}: {detail}") from exc
    except httpx.RequestError as exc:
        raise CopilotClientError(f"Could not reach the copilot backend at {settings.backend_url}: {exc}") from exc
    return response.json()


def chat(message: str, thread_id: str) -> dict:
    """Send one user message to the copilot backend.

    Args:
        message (str): the user's message.
        thread_id (str): the conversation thread id.

    Returns:
        dict: the backend's ChatResponse, decoded from JSON.
    """
    return _post("/chat", {"message": message, "thread_id": thread_id})


def confirm(thread_id: str, approved: bool, edited_args: dict | None = None) -> dict:
    """Resolve a pending write confirmation.

    Args:
        thread_id (str): the thread id whose pending write is being decided.
        approved (bool): True to execute the pending write, False to discard it.
        edited_args (dict | None): the user's edited version of the pending write's args, if any.

    Returns:
        dict: the backend's ChatResponse, decoded from JSON.
    """
    return _post("/confirm", {"thread_id": thread_id, "approved": approved, "edited_args": edited_args})


def get_history(thread_id: str) -> dict:
    """Fetch a thread's chat history and current state from the backend.

    Used to restore a conversation after the browser loses its own local
    state (e.g. a WebSocket reconnect resets gr.State), since the thread's
    actual context is still sitting in the backend's checkpointer.

    Args:
        thread_id (str): the conversation thread id.

    Returns:
        dict: the backend's HistoryResponse, decoded from JSON.
    """
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.backend_url}/history/{thread_id}", timeout=settings.request_timeout_seconds)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CopilotClientError(f"Backend returned {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise CopilotClientError(f"Could not reach the copilot backend at {settings.backend_url}: {exc}") from exc
    return response.json()


def health() -> bool:
    """Check whether the copilot backend is reachable and healthy.

    Args:
        None

    Returns:
        bool: True if the backend responded 200 to /health.
    """
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.backend_url}/health", timeout=5.0)
        return response.status_code == 200
    except httpx.RequestError:
        return False
