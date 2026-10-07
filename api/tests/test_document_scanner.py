"""The scanner client against a fake clamd server (no Docker needed): every reply and failure."""

import io
import socket
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from app.documents.scanner import ClamAVScanner, ScannerUnavailableError


@contextmanager
def fake_clamd(reply: bytes | None, *, hang: bool = False) -> Iterator[tuple[int, list[bytes]]]:
    """A one-shot fake clamd. Records the bytes it received so the protocol can be checked."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    received: list[bytes] = []

    def serve() -> None:
        conn, _ = server.accept()
        with conn:
            data = b""
            while not data.endswith(struct.pack("!I", 0)):
                part = conn.recv(65536)
                if not part:
                    break
                data += part
            received.append(data)
            if hang:
                threading.Event().wait(2)
            elif reply is not None:
                conn.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield server.getsockname()[1], received
    finally:
        server.close()
        thread.join(timeout=3)


def scan(port: int, data: bytes = b"hello", timeout: float = 5.0) -> object:
    return ClamAVScanner("127.0.0.1", port, timeout=timeout).scan(io.BytesIO(data))


def test_clean_file() -> None:
    with fake_clamd(b"stream: OK\0") as (port, received):
        result = scan(port, b"hello world")
    assert result.clean is True  # type: ignore[attr-defined]
    # protocol: command, then length-prefixed chunk(s), then a zero-length terminator
    assert received[0].startswith(b"zINSTREAM\0")
    assert struct.pack("!I", 11) + b"hello world" in received[0]
    assert received[0].endswith(struct.pack("!I", 0))


def test_infected_file_reports_the_signature() -> None:
    with fake_clamd(b"stream: Eicar-Test-Signature FOUND\0") as (port, _):
        result = scan(port)
    assert result.clean is False  # type: ignore[attr-defined]
    assert result.signature == "Eicar-Test-Signature"  # type: ignore[attr-defined]


def test_large_files_are_sent_in_chunks() -> None:
    data = b"x" * (200 * 1024)
    with fake_clamd(b"stream: OK\0") as (port, received):
        scan(port, data)
    assert len(received[0]) > len(data)  # several chunk headers added


@pytest.mark.parametrize(
    "reply",
    [
        b"INSTREAM size limit exceeded. ERROR\0",
        b"stream: some unexpected text\0",
        b"",
        b"stream: OK FOUND ERROR\0",
    ],
)
def test_anything_unclear_fails_closed(reply: bytes) -> None:
    with fake_clamd(reply) as (port, _), pytest.raises(ScannerUnavailableError):
        scan(port)


def test_connection_refused_fails_closed() -> None:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.close()  # nothing listens here any more
    with pytest.raises(ScannerUnavailableError):
        scan(port)


def test_a_scanner_that_hangs_times_out_and_fails_closed() -> None:
    with fake_clamd(None, hang=True) as (port, _), pytest.raises(ScannerUnavailableError):
        scan(port, timeout=0.5)


def test_scanner_rewinds_the_file_for_the_next_step() -> None:
    buffer = io.BytesIO(b"hello")
    with fake_clamd(b"stream: OK\0") as (port, _):
        ClamAVScanner("127.0.0.1", port).scan(buffer)
    assert buffer.tell() == 0
