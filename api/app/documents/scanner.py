"""Virus scanning through ClamAV's clamd INSTREAM protocol. Fails closed: if the scanner cannot give
a clear answer, the file is not accepted."""

import socket
import struct
from dataclasses import dataclass
from typing import BinaryIO, Protocol

CHUNK = 64 * 1024


class ScannerUnavailableError(Exception):
    """The scanner could not be reached or gave no clear answer. Nothing may be stored."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str | None = None


class Scanner(Protocol):
    def scan(self, file: BinaryIO) -> ScanResult: ...


class ClamAVScanner:
    def __init__(self, host: str, port: int = 3310, timeout: float = 30.0) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

    def scan(self, file: BinaryIO) -> ScanResult:
        file.seek(0)
        try:
            with socket.create_connection((self._host, self._port), timeout=self._timeout) as conn:
                conn.settimeout(self._timeout)
                conn.sendall(b"zINSTREAM\0")
                while chunk := file.read(CHUNK):
                    conn.sendall(struct.pack("!I", len(chunk)) + chunk)
                conn.sendall(struct.pack("!I", 0))
                reply = self._read_reply(conn)
        except OSError as exc:  # refused, reset, timed out
            raise ScannerUnavailableError(type(exc).__name__) from None
        finally:
            file.seek(0)
        return self._interpret(reply)

    @staticmethod
    def _read_reply(conn: socket.socket) -> str:
        data = b""
        while not data.endswith(b"\0") and not data.endswith(b"\n"):
            part = conn.recv(4096)
            if not part:
                break
            data += part
            if len(data) > 4096:
                break
        return data.rstrip(b"\0\n").decode("utf-8", "replace")

    @staticmethod
    def _interpret(reply: str) -> ScanResult:
        if reply.endswith("OK") and "FOUND" not in reply and "ERROR" not in reply:
            return ScanResult(clean=True)
        if reply.endswith("FOUND"):
            # "stream: Eicar-Signature FOUND"
            signature = reply.split(":", 1)[-1].replace("FOUND", "").strip() or "unknown"
            return ScanResult(clean=False, signature=signature)
        raise ScannerUnavailableError("scanner_error")
