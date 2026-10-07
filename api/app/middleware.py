from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.audit.recorder import new_correlation_id

HEADER = "X-Request-ID"


async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Give every request a correlation ID and echo it back, so a user report can be traced."""
    request.state.correlation_id = new_correlation_id(request.headers.get(HEADER))
    response = await call_next(request)
    response.headers[HEADER] = request.state.correlation_id
    return response
