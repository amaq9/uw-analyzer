"""Snapshots: the exact bytes a connector received, kept in private storage with a SHA-256, so every
later claim can point at what was really read (P-01, P-02, FR-3.1 provenance). Keys are random and
under the tenant and case; nothing from the response ever becomes part of a path."""

import hashlib
import io
import uuid
from dataclasses import dataclass

from app.documents.storage import ObjectStorage


@dataclass(frozen=True)
class Snapshot:
    ref: str  # snapshot://<key>#sha256=<hash>
    key: str
    sha256: str
    size: int


class SnapshotStore:
    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    def save(self, tenant_id: str, case_id: uuid.UUID, content: bytes) -> Snapshot:
        digest = hashlib.sha256(content).hexdigest()
        key = f"snapshots/{tenant_id}/{case_id}/{uuid.uuid4().hex}"
        self._storage.put(key, io.BytesIO(content), len(content))
        return Snapshot(
            ref=f"snapshot://{key}#sha256={digest}", key=key, sha256=digest, size=len(content)
        )

    def read(self, key: str) -> bytes:
        if not key.startswith("snapshots/"):
            raise ValueError("Not a snapshot key.")
        return b"".join(self._storage.get(key))
