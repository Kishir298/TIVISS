"""Length-prefixed JSON framing for the TIVISS security protocol.

Wire format::

    +----------------+--------------------------+
    | 4-byte BE len  | UTF-8 JSON envelope      |
    +----------------+--------------------------+

The envelope is a JSON object::

    {"v": 1, "id": "<uuid>", "type": "<message type>", "payload": {...}}

Frames larger than :data:`MAX_FRAME` are rejected (fail closed).  Socket
helpers :func:`read_frame` / :func:`send_frame` operate on any object with
``recv``/``sendall`` (real sockets, or test doubles).
"""

from __future__ import annotations

import json
import struct
import uuid
from collections.abc import Mapping
from typing import Any

from .errors import FrameError
from .version import PROTOCOL_VERSION

HEADER = struct.Struct(">I")
MAX_FRAME = 1 << 20  # 1 MiB — hard cap on a single frame
MAX_TYPE_LEN = 128
_RECV_CHUNK = 4096


def encode_frame(message: Mapping[str, Any]) -> bytes:
    """Serialize ``message`` into a length-prefixed frame."""
    if not isinstance(message, Mapping):
        raise FrameError("frame payload must be a JSON object")
    try:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FrameError(f"frame payload is not JSON-serializable: {exc}") from exc
    if len(payload) > MAX_FRAME:
        raise FrameError(f"frame of {len(payload)} bytes exceeds limit of {MAX_FRAME}")
    return HEADER.pack(len(payload)) + payload


def decode_frame(data: bytes) -> dict[str, Any]:
    """Parse a complete frame (header + payload) into its envelope dict."""
    if len(data) < HEADER.size:
        raise FrameError("frame shorter than length header")
    (length,) = HEADER.unpack_from(data)
    if length > MAX_FRAME:
        raise FrameError(f"declared frame length {length} exceeds limit of {MAX_FRAME}")
    if len(data) != HEADER.size + length:
        raise FrameError(
            f"frame length mismatch: header says {length}, "
            f"body is {len(data) - HEADER.size} bytes"
        )
    body = data[HEADER.size :]
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrameError(f"frame body is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise FrameError("frame body must be a JSON object")
    return message


def envelope(
    msg_type: str,
    payload: Mapping[str, Any] | None = None,
    *,
    msg_id: str | None = None,
) -> dict[str, Any]:
    """Build a protocol envelope around ``payload``."""
    if not isinstance(msg_type, str) or not msg_type or len(msg_type) > MAX_TYPE_LEN:
        raise FrameError(
            f"message type must be a non-empty string of at most {MAX_TYPE_LEN} chars"
        )
    if payload is not None and not isinstance(payload, Mapping):
        raise FrameError("envelope payload must be a JSON object")
    return {
        "v": PROTOCOL_VERSION,
        "id": msg_id or str(uuid.uuid4()),
        "type": msg_type,
        "payload": dict(payload or {}),
    }


def validate_envelope(message: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Validate an envelope; return ``(id, type, payload)``.

    Rejects unknown protocol versions so a future incompatible peer fails
    closed instead of being misinterpreted.
    """
    if not isinstance(message, Mapping):
        raise FrameError("envelope must be a JSON object")
    version = message.get("v")
    if version != PROTOCOL_VERSION:
        raise FrameError(
            f"unsupported protocol version: {version!r} (expected {PROTOCOL_VERSION})"
        )
    msg_id = message.get("id")
    msg_type = message.get("type")
    payload = message.get("payload")
    if not isinstance(msg_id, str) or not msg_id:
        raise FrameError("envelope id must be a non-empty string")
    if not isinstance(msg_type, str) or not msg_type or len(msg_type) > MAX_TYPE_LEN:
        raise FrameError("envelope type must be a non-empty string")
    if not isinstance(payload, dict):
        raise FrameError("envelope payload must be a JSON object")
    return msg_id, msg_type, payload


def _recv_exactly(recv, size: int) -> bytes:
    """Read exactly ``size`` bytes from ``recv`` (fail closed on EOF)."""
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = recv(min(remaining, _RECV_CHUNK))
        if not chunk:
            raise FrameError("connection closed mid-frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(recv) -> dict[str, Any]:
    """Read one frame from a socket-like ``recv(maxlen)`` callable."""
    header = _recv_exactly(recv, HEADER.size)
    (length,) = HEADER.unpack(header)
    if length > MAX_FRAME:
        raise FrameError(f"declared frame length {length} exceeds limit of {MAX_FRAME}")
    body = _recv_exactly(recv, length)
    message = decode_frame(header + body)
    return message


def send_frame(sendall, message: Mapping[str, Any]) -> int:
    """Write one frame via a socket-like ``sendall(bytes)``; return byte count."""
    frame = encode_frame(message)
    sendall(frame)
    return len(frame)


__all__ = [
    "HEADER",
    "MAX_FRAME",
    "encode_frame",
    "decode_frame",
    "envelope",
    "validate_envelope",
    "read_frame",
    "send_frame",
]
