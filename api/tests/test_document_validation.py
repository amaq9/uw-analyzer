import io

import pytest

from app.documents.validation import (
    CSV,
    DOCX,
    JPEG,
    PDF,
    PNG,
    TXT,
    XLSX,
    RejectedFileError,
    detect_and_check,
    sanitize_filename,
)
from tests.files import JPEG_BYTES, PDF_BYTES, PNG_BYTES, office_zip, zip_bomb


def check(data: bytes, name: str) -> object:
    return detect_and_check(io.BytesIO(data), name, len(data))


@pytest.mark.parametrize(
    ("data", "name", "expected"),
    [
        (PDF_BYTES, "statement.pdf", PDF),
        (PDF_BYTES, "STATEMENT.PDF", PDF),
        (PNG_BYTES, "scan.png", PNG),
        (JPEG_BYTES, "scan.jpg", JPEG),
        (JPEG_BYTES, "scan.jpeg", JPEG),
        (office_zip("docx"), "report.docx", DOCX),
        (office_zip("xlsx"), "figures.xlsx", XLSX),
        (b"a,b\n1,2\n", "figures.csv", CSV),
        ("notes caf\u00e9".encode(), "notes.txt", TXT),
    ],
)
def test_allowed_files_are_accepted(data: bytes, name: str, expected: object) -> None:
    assert check(data, name) is expected


def reason(data: bytes, name: str) -> str:
    with pytest.raises(RejectedFileError) as excinfo:
        check(data, name)
    return excinfo.value.code


def test_the_bytes_decide_not_the_name() -> None:
    assert reason(PDF_BYTES, "statement.png") == "extension_mismatch"
    assert reason(PNG_BYTES, "statement.pdf") == "extension_mismatch"
    assert reason(b"MZ\x90\x00 pretend program", "statement.pdf") == "unsupported_type"
    assert reason(b"MZ\x90\x00 pretend program", "tool.exe") == "unsupported_type"


@pytest.mark.parametrize(
    "name", ["run.exe", "page.html", "script.js", "archive.zip", "x.docm", "x"]
)
def test_types_off_the_allow_list_are_refused(name: str) -> None:
    assert reason(b"<html>hi</html>", name) == "unsupported_type"


def test_zip_with_a_non_office_name_is_refused() -> None:
    assert reason(office_zip("docx"), "archive.zip") == "unsupported_type"


def test_empty_file_is_refused() -> None:
    with pytest.raises(RejectedFileError) as excinfo:
        detect_and_check(io.BytesIO(b""), "a.pdf", 0)
    assert excinfo.value.code == "empty"


def test_binary_data_posing_as_text_is_refused() -> None:
    assert reason(b"abc\x00def", "notes.txt") == "unsupported_type"
    assert reason(b"\xff\xfe\xfd\xfc" * 50, "notes.csv") == "unsupported_type"


def test_macro_enabled_office_files_are_refused() -> None:
    macro = office_zip("docx", {"word/vbaProject.bin": b"macro"})
    assert reason(macro, "report.docx") == "macros"


def test_zip_bombs_and_unsafe_paths_are_refused() -> None:
    assert reason(zip_bomb(), "report.docx") == "zip_bomb"
    unsafe = office_zip("docx", {"../evil.txt": b"x"})
    assert reason(unsafe, "report.docx") == "zip_unsafe_path"


def test_office_file_must_really_be_office() -> None:
    assert reason(office_zip("xlsx"), "report.docx") == "not_office"  # xl/ parts, named docx
    assert reason(b"PK\x03\x04 not really a zip", "report.docx") == "not_office"


def test_pdfs_with_active_content_are_refused() -> None:
    for active in (b"/JavaScript", b"/JS (app.alert(1))", b"/Launch", b"/EmbeddedFile"):
        assert (
            reason(PDF_BYTES + b"\n<< " + active + b" >>", "statement.pdf") == "pdf_active_content"
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("statement.pdf", "statement.pdf"),
        ("C:\\Users\\bob\\statement.pdf", "statement.pdf"),
        ("../../etc/passwd", "passwd"),
        ("a\x00b\r\n.pdf", "ab.pdf"),
        ('we<ird>:"name|?.pdf', "weirdname.pdf"),
        ("  spaced   out  .pdf ", "spaced out .pdf"),
        ("", "document"),
        (None, "document"),
        ("...", "document"),
    ],
)
def test_filenames_are_made_safe(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_long_filenames_keep_their_extension() -> None:
    name = sanitize_filename("x" * 400 + ".pdf")
    assert len(name) <= 150 and name.endswith(".pdf")
