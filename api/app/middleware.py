from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.audit.recorder import new_correlation_id
from app.errors import error_response

HEADER = "X-Request-ID"


async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Give every request a correlation ID and echo it back, so a user report can be traced."""
    request.state.correlation_id = new_correlation_id(request.headers.get(HEADER))
    response = await call_next(request)
    response.headers[HEADER] = request.state.correlation_id
    return response


_MULTIPART_OVERHEAD = 1024 * 1024  # form fields and boundaries around the file


def make_upload_size_guard(
    max_bytes: int,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Refuse an oversized upload from its declared length, before the body is read or spooled."""

    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "POST" and request.url.path.endswith("/documents"):
            declared = request.headers.get("content-length")
            if declared is None:
                return error_response(
                    request, 411, "length_required", "Uploads must declare their size."
                )
            if not declared.isdigit() or int(declared) > max_bytes + _MULTIPART_OVERHEAD:
                return error_response(
                    request,
                    413,
                    "payload_too_large",
                    f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
                )
        return await call_next(request)

    return guard
