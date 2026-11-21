"""Framing tests: roundtrip, limits, envelope validation, socket helpers."""

from __future__ import annotations

import socket

import pytest

from tiviss_security_protocol import (
    MAX_FRAME,
    FrameError,
    ProtocolError,
    decode_frame,
    encode_frame,
    envelope,
    read_frame,
    send_frame,
    validate_envelope,
)
from tiviss_security_protocol.version import PROTOCOL_VERSION


def test_roundtrip_simple():
    message = envelope("pdp.decide", {"subject": "alice", "action": "read"})
    frame = encode_frame(message)
    assert decode_frame(frame) == message


def test_roundtrip_nested_payload():
    payload = {"a": {"b": [1, 2, {"c": "d"}]}, "unicode": "héllo ✓"}
    message = envelope("test.nested", payload, msg_id="fixed-id")
    assert decode_frame(encode_frame(message)) == message


def test_oversized_frame_rejected():
    message = envelope("test.big", {"blob": "x" * (MAX_FRAME + 1)})
    with pytest.raises(FrameError, match="exceeds limit"):
        encode_frame(message)


def test_short_header_rejected():
    with pytest.raises(FrameError, match="shorter than"):
        decode_frame(b"\x00\x01")


def test_length_mismatch_rejected():
    frame = encode_frame(envelope("t", {}))
    with pytest.raises(FrameError, match="length mismatch"):
        decode_frame(frame[:-1])
    with pytest.raises(FrameError, match="length mismatch"):
        decode_frame(frame + b"junk")


def test_declared_length_over_cap_rejected():
    import struct

    header = struct.pack(">I", MAX_FRAME + 1)
    with pytest.raises(FrameError, match="exceeds limit"):
        decode_frame(header + b"x")


def test_invalid_json_body_rejected():
    import struct

    body = b"not-json"
    with pytest.raises(FrameError, match="not valid UTF-8 JSON"):
        decode_frame(struct.pack(">I", len(body)) + body)


def test_non_object_body_rejected():
    import struct

    body = b"[1,2,3]"
    with pytest.raises(FrameError, match="JSON object"):
        decode_frame(struct.pack(">I", len(body)) + body)


def test_envelope_requires_valid_type():
    with pytest.raises(FrameError, match="message type"):
        envelope("", {})
    with pytest.raises(FrameError, match="message type"):
        envelope("x" * 200, {})


def test_validate_envelope_rejects_wrong_version():
    message = envelope("pdp.decide", {})
    message["v"] = PROTOCOL_VERSION + 1
    with pytest.raises(FrameError, match="unsupported protocol version"):
        validate_envelope(message)


def test_validate_envelope_rejects_missing_fields():
    with pytest.raises(FrameError, match="envelope id"):
        validate_envelope({"v": PROTOCOL_VERSION, "type": "x", "payload": {}})
    with pytest.raises(FrameError, match="envelope type"):
        validate_envelope({"v": PROTOCOL_VERSION, "id": "1", "payload": {}})
    with pytest.raises(FrameError, match="payload"):
        validate_envelope(
            {"v": PROTOCOL_VERSION, "id": "1", "type": "x", "payload": []}
        )


def test_socket_roundtrip():
    left, right = socket.socketpair()
    try:
        message = envelope("pdp.health", {"ping": True})
        send_frame(left.sendall, message)
        received = read_frame(right.recv)
        assert received == message
        assert validate_envelope(received)[1] == "pdp.health"
    finally:
        left.close()
        right.close()


def test_read_frame_truncated_connection():
    left, right = socket.socketpair()
    try:
        left.sendall(b"\x00\x00\x00")
        left.close()
        with pytest.raises(FrameError, match="connection closed"):
            read_frame(right.recv)
    finally:
        right.close()


def test_errors_derive_from_protocol_error():
    assert issubclass(FrameError, ProtocolError)
