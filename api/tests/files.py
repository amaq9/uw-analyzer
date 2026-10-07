"""Builders for test files. The EICAR antivirus test string is assembled at run time so this source
file does not itself trip antivirus software on a developer machine."""

import io
import zipfile

# The standard, harmless EICAR test string that every antivirus engine reports as a virus.
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-" + "TEST-FILE!$H+H*").encode()

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def office_zip(kind: str = "docx", extra: dict[str, bytes] | None = None) -> bytes:
    folder = "word" if kind == "docx" else "xl"
    parts = {
        "[Content_Types].xml": b"<Types/>",
        f"{folder}/document.xml": b"<doc>hello</doc>",
    }
    parts.update(extra or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def zip_bomb() -> bytes:
    """Tiny on disk, enormous when expanded (the ratio check must refuse it)."""
    return office_zip("docx", {"word/big.bin": b"\x00" * (8 * 1024 * 1024)})
