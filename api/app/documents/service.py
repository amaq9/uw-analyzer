"""The upload pipeline. Order matters and is the safety property: check the file, scan it, store it,
then record it. If any step fails, nothing is left behind and the caller is told plainly."""

import hashlib
import logging
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO, cast

from app.documents.scanner import Scanner, ScannerUnavailableError
from app.documents.schemas import DocumentCategory, DocumentRecord
from app.documents.storage import ObjectStorage, StorageUnavailableError
from app.documents.store import PostgresDocumentStore
from app.documents.validation import RejectedFileError, detect_and_check, sanitize_filename

logger = logging.getLogger("uw.documents")

MAX_DOCUMENTS_PER_CASE = 50
_READ_CHUNK = 64 * 1024


class UploadUnavailableError(Exception):
    """A dependency (scanner or storage) is down. Nothing was saved; retrying later is safe."""


@dataclass
class DocumentService:
    store: PostgresDocumentStore
    storage: ObjectStorage
    scanner: Scanner
    max_bytes: int

    def upload(
        self,
        *,
        case_id: uuid.UUID,
        tenant_id: str,
        uploaded_by: str,
        category: DocumentCategory,
        raw_filename: str | None,
        stream: BinaryIO,
    ) -> DocumentRecord:
        if self.store.count_for_case(case_id) >= MAX_DOCUMENTS_PER_CASE:
            raise RejectedFileError(
                "too_many_documents",
                f"A case can hold at most {MAX_DOCUMENTS_PER_CASE} documents.",
                status=409,
            )
        filename = sanitize_filename(raw_filename)
        with tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024) as spooled:
            buffer = cast(BinaryIO, spooled)
            size, digest = self._copy_limited(stream, buffer)
            file_type = detect_and_check(buffer, filename, size)
            try:
                result = self.scanner.scan(buffer)
            except ScannerUnavailableError:
                raise UploadUnavailableError("scanner") from None
            if not result.clean:
                # The signature is for diagnostics only; it never reaches the user or the audit log.
                logger.warning("upload.infected case=%s signature=%s", case_id, result.signature)
                raise RejectedFileError(
                    "infected", "The file was rejected by the virus scan. Nothing was saved."
                )
            key = f"{tenant_id}/{uuid.uuid4().hex}/{uuid.uuid4().hex}"  # random: no file name in it
            try:
                self.storage.put(key, buffer, size)
            except StorageUnavailableError:
                raise UploadUnavailableError("storage") from None
        try:
            return self.store.add(
                case_id=case_id,
                tenant_id=tenant_id,
                category=category,
                filename=filename,
                content_type=file_type.media_type,
                size_bytes=size,
                sha256=digest,
                storage_key=key,
                uploaded_by=uploaded_by,
            )
        except Exception:
            # The record was not written, so remove the stored object rather than orphan it.
            try:
                self.storage.delete(key)
            except StorageUnavailableError:
                logger.error("upload.orphan_object key_prefix=%s", tenant_id)
            raise

    def open(self, record: DocumentRecord) -> Iterator[bytes]:
        try:
            yield from self.storage.get(record.storage_key)
        except StorageUnavailableError:
            raise UploadUnavailableError("storage") from None

    def _copy_limited(self, src: BinaryIO, dst: BinaryIO) -> tuple[int, str]:
        sha = hashlib.sha256()
        size = 0
        while chunk := src.read(_READ_CHUNK):
            size += len(chunk)
            if size > self.max_bytes:
                raise RejectedFileError(
                    "too_large",
                    f"The file is larger than the {self.max_bytes // (1024 * 1024)} MB limit.",
                    status=413,
                )
            sha.update(chunk)
            dst.write(chunk)
        return size, sha.hexdigest()
