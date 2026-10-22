"""Bounded Nanonis TCP framing and strict, declarative payload codecs.

Vendored 2026-10-23 from D:/STM/tools/nanonis_diagnostics/protocol.py,
diagnostics 1.2.0; protocol baseline TCPProtocol_Mimea_V5e.pdf R14573.
"""
from __future__ import annotations

import math
import socket
import struct
import time

HEADER = struct.Struct(">32sIHH")
RESPONSE_HEADER = struct.Struct(">32siI")
MAX_BODY = 32 * 1024 * 1024
MAX_ELEMENTS = 4_194_304


class ProtocolError(ValueError):
    pass


class Cancelled(Exception):
    pass


class InstrumentError(Exception):
    def __init__(self, status, description):
        super().__init__(f"Nanonis status={status}: {description}")
        self.status, self.description = status, description


def count_checked(value):
    if not isinstance(value, int) or not 0 <= value <= MAX_ELEMENTS:
        raise ProtocolError(f"Invalid element count: {value!r}")
    return value


def encode(types, values):
    if not isinstance(values, list) or len(values) != len(types):
        raise ValueError(f"Expected JSON array of {len(types)} arguments")
    parts = []
    for kind, value in zip(types, values):
        if kind in ("+*c", "*+c"):
            if isinstance(value, str):
                raw = value.encode("utf-8")
                parts.append(struct.pack(">i", len(raw)) + raw)
            elif isinstance(value, list) and all(isinstance(s, str) for s in value):
                raw = b"".join(struct.pack(">i", len(s.encode("utf-8"))) + s.encode("utf-8") for s in value)
                parts.append(struct.pack(">ii", len(raw), len(value)) + raw)
            else:
                raise ValueError("String or string array required")
        elif "*" in kind or kind.startswith("2"):
            if not isinstance(value, list):
                raise ValueError(f"{kind} requires an array")
            if kind.startswith("2"):
                cols = len(value[0]) if value else 0
                if not all(isinstance(row, list) and len(row) == cols for row in value):
                    raise ValueError("Ragged matrix")
                parts.append(struct.pack(">ii", len(value), cols))
                value = [v for row in value for v in row]
            elif "+" in kind:
                parts.append(struct.pack(">i", len(value)))
            count_checked(len(value))
            if any(isinstance(v, float) and not math.isfinite(v) for v in value):
                raise ValueError("Non-finite request value")
            parts.append(struct.pack(">" + str(len(value)) + kind[-1], *value))
        else:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Non-finite request value")
            parts.append(struct.pack(">" + kind, value))
    body = b"".join(parts)
    if len(body) > MAX_BODY:
        raise ValueError("Request exceeds 32 MiB")
    return body


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ProtocolError(f"Truncated payload at {self.pos}: need {size}, have {len(self.data)-self.pos}")
        block = self.data[self.pos:self.pos + size]
        self.pos += size
        return block

    def scalar(self, kind):
        return struct.unpack(">" + kind, self.take(struct.calcsize(">" + kind)))[0]

    def string(self, length=None):
        length = self.scalar("i") if length is None else length
        try:
            return self.take(count_checked(length)).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("Invalid UTF-8 string in response") from exc

    def array(self, kind, count):
        count = count_checked(count)
        if kind == "c":
            return [self.string() for _ in range(count)]
        return list(struct.unpack(">" + str(count) + kind, self.take(count * struct.calcsize(">" + kind))))

    def error(self):
        status = self.scalar("I")
        description = self.string()
        if self.pos != len(self.data):
            raise ProtocolError(f"Unexpected trailing bytes: {len(self.data)-self.pos}")
        if status:
            raise InstrumentError(status, description)
        return description


def decode(types, data):
    r, values = Reader(data), []
    # Some unavailable modules return only the error trailer.
    if len(data) >= 8:
        code, size = struct.unpack_from(">Ii", data)
        if code == 1 and size == len(data) - 8:
            Reader(data).error()
    for kind in types:
        if kind == "+*c":
            value = r.string()
        elif kind == "*-c":
            value = r.string(values[-1])
        elif kind == "*+c":
            begin = r.pos
            value = r.array("c", values[-1])
            if len(values) >= 2 and isinstance(values[-2], int) and r.pos - begin != values[-2]:
                raise ProtocolError(f"String-array byte size mismatch: declared {values[-2]}, read {r.pos-begin}")
        elif kind.startswith("2"):
            rows, cols = count_checked(values[-2]), count_checked(values[-1])
            value = {"shape": [rows, cols], "values": r.array(kind[-1], rows * cols)}
        elif kind.startswith("**"):
            value = r.array(kind[-1], values[0])
        elif kind.startswith("*") or kind.startswith("+*"):
            value = r.array(kind[-1], values[-1])
        else:
            value = r.scalar(kind)
        values.append(value)
    warning = r.error()
    return values, warning


def documented_error(data):
    """Recover an explicit device error only, never infer success from a tail."""
    marker = b"Error in command:"
    pos = data.find(marker)
    if pos >= 8:
        code, size = struct.unpack_from(">Ii", data, pos - 8)
        if code == 1 and size == len(data) - pos:
            raise InstrumentError(code, data[pos:].decode("utf-8", errors="replace"))


def summarize(value):
    if isinstance(value, dict):
        return {k: summarize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) <= 24:
            return [summarize(v) for v in value]
        result = {"count": len(value), "preview": [summarize(v) for v in value[:12]]}
        if all(isinstance(v, (int, float)) for v in value):
            valid = [v for v in value if math.isfinite(v)]
            result.update(finite_count=len(valid), finite_fraction=len(valid) / len(value),
                          min=min(valid) if valid else None, max=max(valid) if valid else None)
        return result
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


class Connection:
    def __init__(self, host, port, timeout=2.0, cancel=None):
        self.host, self.port, self.timeout, self.cancel = host, port, timeout, cancel
        self.sock = None
        self.request_header, self.response_header = None, None

    def __enter__(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return self

    def __exit__(self, *_):
        if self.sock:
            self.sock.close()
            # The Nanonis single-client listener needs time to re-arm after EOF.
            time.sleep(0.05)

    def check(self):
        if self.cancel is not None and self.cancel.is_set():
            raise Cancelled("Test cancelled")

    def recv(self, size, deadline):
        blocks, remaining = [], size
        while remaining:
            self.check()
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("Response deadline exceeded")
            self.sock.settimeout(min(0.2, left))
            try:
                block = self.sock.recv(min(remaining, 65536))
            except socket.timeout:
                continue
            if not block:
                raise ConnectionError(f"Connection closed with {remaining} bytes missing")
            remaining -= len(block)
            blocks.append(block)
        return b"".join(blocks)

    def exchange(self, command, body=b""):
        self.check()
        self.request_header, self.response_header = None, None
        name = command.encode("ascii")
        if len(name) > 32 or not name or len(body) > MAX_BODY:
            raise ValueError("Invalid request")
        start = time.perf_counter()
        deadline = time.monotonic() + self.timeout
        self.sock.settimeout(self.timeout)
        self.request_header = HEADER.pack(name, len(body), 1, 0)
        self.sock.sendall(self.request_header + body)
        self.response_header = self.recv(RESPONSE_HEADER.size, deadline)
        returned, size, reserved = RESPONSE_HEADER.unpack(self.response_header)
        if returned.rstrip(b"\0") != name:
            raise ProtocolError("Response command does not match request")
        if not 8 <= size <= MAX_BODY:
            raise ProtocolError(f"Invalid response length {size}")
        if reserved:
            raise ProtocolError(f"Nonzero reserved response header: {reserved}")
        data = self.recv(size, deadline)
        return data, (time.perf_counter() - start) * 1000
