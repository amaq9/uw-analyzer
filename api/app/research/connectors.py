"""Connector interface (FR-2.6, FR-2.7). A connector reaches ONE registered source and returns a
provenance reference for what it fetched. Only the executor calls connectors, and only an executed
call can be logged as access; no model output and no API request can mark a source as accessed.

No real connector ships yet. The product never simulates one: a planned step whose source has no
connector here is recorded as SKIPPED with that reason."""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.research.plan import Category


class RetryableConnectorError(Exception):
    """A temporary failure (network, rate limit). The executor may try again."""


class PermanentConnectorError(Exception):
    """A failure that retrying will not fix (bad request, refused access, no unique match).

    `code` is a short machine-readable reason kept in the call log, e.g. no_unique_match."""

    def __init__(self, code: str = "", message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class ConnectorRequest:
    case_id: uuid.UUID
    tenant_id: str
    category: Category
    source_key: str
    jurisdictions: list[str]
    legal_name: str | None
    registration_number: str | None
    industry: str | None = None


@dataclass(frozen=True)
class ConnectorResult:
    provenance_ref: str  # where the returned material is kept or can be fetched again
    items: int = 0


class Connector(Protocol):
    """A connector may also set `timeout_seconds` when one call needs longer than the executor's
    default (e.g. it downloads whole lists)."""

    key: str  # the registry key of the source it reaches
    version: str

    def describe(self, request: ConnectorRequest) -> str:
        """Plain-language statement of what this call does, logged before it runs."""
        ...

    def execute(self, request: ConnectorRequest) -> ConnectorResult: ...


@dataclass
class ConnectorSet:
    """The connectors this deployment actually has, by source key. Empty until real ones exist."""

    connectors: dict[str, Connector] = field(default_factory=dict)

    def get(self, source_key: str) -> Connector | None:
        return self.connectors.get(source_key)
