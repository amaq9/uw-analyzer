"""Outbound HTTP for connectors, locked down (FR-2.6, SEC-11). Only https, only hosts a connector
names in advance, no redirects, a size cap and a timeout. The caller identifies itself with a
contact address (public registries such as SEC EDGAR require it). Nothing here follows a link
it was not given, so a connector can only ever reach its own registry."""

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from app.research.connectors import PermanentConnectorError, RetryableConnectorError

MAX_BYTES = 30 * 1024 * 1024
TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    body: bytes
    content_type: str


class Fetcher(Protocol):
    def get(
        self,
        url: str,
        *,
        allowed_hosts: frozenset[str],
        redirect_hosts: frozenset[str] = frozenset(),
    ) -> Fetched: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class HttpsFetcher:
    def __init__(self, contact: str, timeout: float = TIMEOUT_SECONDS, max_bytes: int = MAX_BYTES):
        self._user_agent = f"UWAnalyzer-research/1.0 ({contact})"
        self._timeout = timeout
        self._max_bytes = max_bytes
        self._opener = urllib.request.build_opener(_NoRedirect)

    def get(
        self,
        url: str,
        *,
        allowed_hosts: frozenset[str],
        redirect_hosts: frozenset[str] = frozenset(),
    ) -> Fetched:
        """Fetch one https address. At most ONE redirect is followed, and only to a host the
        connector named in `redirect_hosts` (for example a registry's file store)."""
        return self._get(url, allowed_hosts, redirect_hosts, may_redirect=True)

    def _get(
        self,
        url: str,
        allowed_hosts: frozenset[str],
        redirect_hosts: frozenset[str],
        *,
        may_redirect: bool,
    ) -> Fetched:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in allowed_hosts:
            raise PermanentConnectorError("host_not_allowed", "Address is not on the allow-list.")
        request = urllib.request.Request(  # noqa: S310 - scheme and host checked above
            url, headers={"User-Agent": self._user_agent, "Accept": "application/json"}
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:  # noqa: S310
                body = response.read(self._max_bytes + 1)
                status = int(response.status)
                content_type = str(response.headers.get("Content-Type", "application/octet-stream"))
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and may_redirect and redirect_hosts:
                location = exc.headers.get("Location", "")
                return self._get(location, redirect_hosts, frozenset(), may_redirect=False)
            if exc.code == 429 or exc.code >= 500:
                raise RetryableConnectorError(f"http_{exc.code}") from None
            raise PermanentConnectorError(f"http_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RetryableConnectorError("network") from None
        if len(body) > self._max_bytes:
            raise PermanentConnectorError("response_too_large")
        return Fetched(url=url, status=status, body=body, content_type=content_type)
