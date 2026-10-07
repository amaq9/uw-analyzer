"""Checks on an uploaded file before it is scanned or stored (SEC-07).

The file's own bytes decide what it is. The name, extension and the browser's content type are only
hints that must agree with the bytes. Anything not on the allow-list is refused.
"""

import re
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

MAX_ZIP_ENTRIES = 2000
MAX_ZIP_UNCOMPRESSED = 250 * 1024 * 1024
MAX_ZIP_RATIO = 200
MAX_FILENAME = 150
_PDF_SCAN_BYTES = 2 * 1024 * 1024
# Active content has no place in a financial statement and is a risk when a person opens the file.
_PDF_ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile)\b")


@dataclass(frozen=True)
class FileType:
    key: str  # short name used in the API
    media_type: str
    extensions: tuple[str, ...]


PDF = FileType("pdf", "application/pdf", (".pdf",))
DOCX = FileType(
    "docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    (".docx",),
)
XLSX = FileType(
    "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (".xlsx",)
)
CSV = FileType("csv", "text/csv", (".csv",))
TXT = FileType("txt", "text/plain", (".txt",))
PNG = FileType("png", "image/png", (".png",))
JPEG = FileType("jpeg", "image/jpeg", (".jpg", ".jpeg"))

ALLOWED_TYPES = (PDF, DOCX, XLSX, CSV, TXT, PNG, JPEG)


class RejectedFileError(Exception):
    """The file must not be accepted. `code` is a short machine reason (safe to audit)."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def sanitize_filename(raw: str | None) -> str:
    """A safe display name: no path, no control characters, bounded length."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        return "document"
    if len(name) > MAX_FILENAME:
        stem, dot, ext = name.rpartition(".")
        name = (
            (stem[: MAX_FILENAME - len(ext) - 1] + dot + ext)
            if dot and len(ext) < 10
            else name[:MAX_FILENAME]
        )
    return name


def _extension(name: str) -> str:
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _check_zip(file: BinaryIO, expect: FileType) -> None:
    try:
        with zipfile.ZipFile(file) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise RejectedFileError("zip_too_many_entries", "The file has too many parts.")
            total = 0
            names = set()
            for info in infos:
                names.add(info.filename)
                if info.filename.startswith("/") or ".." in info.filename.split("/"):
                    raise RejectedFileError("zip_unsafe_path", "The file contains an unsafe path.")
                total += info.file_size
                if info.compress_size and info.file_size / info.compress_size > MAX_ZIP_RATIO:
                    raise RejectedFileError("zip_bomb", "The file expands to an unsafe size.")
            if total > MAX_ZIP_UNCOMPRESSED:
                raise RejectedFileError("zip_bomb", "The file expands to an unsafe size.")
            if "[Content_Types].xml" not in names:
                raise RejectedFileError("not_office", "The file is not a valid Office document.")
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise RejectedFileError("macros", "Files containing macros are not accepted.")
            marker = "word/" if expect is DOCX else "xl/"
            if not any(n.startswith(marker) for n in names):
                raise RejectedFileError("not_office", "The file is not a valid Office document.")
    except zipfile.BadZipFile:
        raise RejectedFileError("not_office", "The file is not a valid Office document.") from None


def _is_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte character cut by the end of the sample is fine; anything else is not.
        if exc.start < len(head) - 4:
            return False
    return True


def detect_and_check(file: BinaryIO, filename: str, size: int) -> FileType:
    """Identify the file from its bytes, make sure the name agrees, and run type-specific checks."""
    if size <= 0:
        raise RejectedFileError("empty", "The file is empty.")
    file.seek(0)
    head = file.read(8192)
    ext = _extension(filename)

    detected: FileType | None = None
    if head.startswith(b"%PDF-"):
        detected = PDF
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = PNG
    elif head.startswith(b"\xff\xd8\xff"):
        detected = JPEG
    elif head.startswith(b"PK\x03\x04"):
        detected = DOCX if ext == ".docx" else XLSX if ext == ".xlsx" else None
    elif ext in CSV.extensions + TXT.extensions and _is_text(head):
        detected = CSV if ext == ".csv" else TXT

    if detected is None:
        raise RejectedFileError(
            "unsupported_type",
            "This file type is not accepted. Allowed: PDF, Word (docx), Excel (xlsx), CSV, "
            "text, PNG and JPEG.",
            status=415,
        )
    if ext not in detected.extensions:
        raise RejectedFileError(
            "extension_mismatch", "The file name does not match what the file contains.", status=415
        )
    if detected in (DOCX, XLSX):
        file.seek(0)
        _check_zip(file, detected)
    if detected is PDF:
        file.seek(0)
        if _PDF_ACTIVE.search(file.read(_PDF_SCAN_BYTES)):
            raise RejectedFileError(
                "pdf_active_content", "PDFs with scripts or embedded files are not accepted."
            )
    file.seek(0)
    return detected
