import json
import socket
import struct
import threading
from contextlib import suppress

import pytest

from tiviss.integrations.core_tcp import (
    PROTOCOL_VERSION,
    CoreTcpClient,
    DeviceClientError,
    decode_frame,
    encode_frame,
)

# Mirrors CORE-HOST core/communication/protocol.py:validate_registration_payload
# (lines 106-147) and core/version.py:SUPPORTED_VERSIONS. Kept local so the
# TIVISS tests do not import from another repository at runtime.
_SUPPORTED_PROTOCOL_VERSIONS = {"0.2.0", "0.2.1", "0.3.0", "0.4.0", "0.5.0"}


def _host_validate_registration_payload(payload):
    failed = "DEVICE_REGISTRATION_FAILED"
    if not isinstance(payload, dict):
        return failed, "Invalid registration payload structure."
    device_id = payload.get("device_id")
    if device_id is None:
        return failed, "Missing device_id."
    if isinstance(device_id, str) and device_id == "":
        return failed, "Empty device_id."
    if not isinstance(device_id, str):
        return failed, "Invalid device_id."
    device_name = payload.get("device_name")
    if device_name is None:
        return failed, "Missing device_name."
    if not isinstance(device_name, str) or device_name == "":
        return failed, "Empty device_name."
    if payload.get("device_type") is None:
        return failed, "Missing device_type."
    device_type = payload["device_type"]
    if not isinstance(device_type, str) or not device_type.strip():
        return failed, "Empty device_type."
    if payload.get("platform") is None:
        return failed, "Missing platform."
    platform = payload["platform"]
    if not isinstance(platform, str) or not platform.strip():
        return failed, "Empty platform."
    if "capabilities" not in payload:
        return failed, "Missing capabilities."
    if not isinstance(payload.get("capabilities"), list):
        return failed, "Malformed capabilities: must be a list."
    if payload.get("protocol_version") is None:
        return failed, "Missing protocol_version."
    if payload.get("protocol_version") not in _SUPPORTED_PROTOCOL_VERSIONS:
        return failed, "Unsupported protocol version."
    if "join_name" in payload and payload.get("join_name") is not None:
        join_name = payload.get("join_name")
        if not isinstance(join_name, str) or not join_name.strip():
            return failed, "Invalid join_name."
        if len(join_name.strip()) > 64:
            return failed, "Invalid join_name."
    return None, None


def _read_frame(sock):
    header = sock.recv(4)
    if len(header) < 4:
        raise ConnectionError("peer closed")
    (length,) = struct.unpack("!I", header)
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            raise ConnectionError("peer closed")
        body += chunk
    return json.loads(body.decode("utf-8"))


def _write_frame(sock, message):
    data = json.dumps(message).encode("utf-8")
    sock.sendall(struct.pack("!I", len(data)) + data)


def test_frame_roundtrip():
    message = {"message_type": "PING", "payload": {"a": 1}}
    assert decode_frame(encode_frame(message)[:4], encode_frame(message)[4:]) == message


def test_frame_rejects_garbage():
    with pytest.raises(DeviceClientError):
        decode_frame(b"\x00\x00", b"")
    with pytest.raises(DeviceClientError):
        decode_frame(struct.pack("!I", 0), b"")
    with pytest.raises(DeviceClientError):
        decode_frame(struct.pack("!I", 3), b"no}")
    with pytest.raises(DeviceClientError):
        decode_frame(struct.pack("!I", 2), b"{}")


def test_encode_rejects_oversize():
    with pytest.raises(DeviceClientError):
        encode_frame(
            {"message_type": "X", "payload": {"blob": "y" * (11 * 1024 * 1024)}}
        )


def test_constructor_validation():
    with pytest.raises(DeviceClientError):
        CoreTcpClient(host="h", port=1, device_id="  ", credential="c")
    with pytest.raises(DeviceClientError):
        CoreTcpClient(host="h", port=1, device_id="d", credential="")
    with pytest.raises(DeviceClientError):
        CoreTcpClient(host="h", port=1, device_id="d", credential="c", timeout_s=0)


def _peer_script(sock, script):
    """Run scripted (request_type -> response dict) peer on a thread."""
    def run():
        try:
            while True:
                try:
                    incoming = _read_frame(sock)
                except (ConnectionError, OSError, ValueError):
                    return
                response = script(incoming)
                if response is None:
                    return
                _write_frame(sock, response)
        finally:
            with suppress(OSError):
                sock.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _handshake_response():
    return {
        "message_id": "m1",
        "source": "core",
        "destination": "d",
        "message_type": "CORE_HANDSHAKE_RESPONSE",
        "timestamp": "t",
        "request_id": None,
        "payload": {
            "authenticated": True,
            "connection_id": "c-1",
            "session_token": "s-1",
        },
        "identity_id": "d",
    }


def test_handshake_and_register_over_socketpair():
    client_end, peer_end = socket.socketpair()
    client = CoreTcpClient(host="h", port=1, device_id="d", credential="c")
    client._sock = client_end

    def script(incoming):
        if incoming["message_type"] == "CORE_HANDSHAKE":
            assert incoming["payload"]["credential"] == "c"
            return _handshake_response()
        if incoming["message_type"] == "DEVICE_REGISTER":
            assert incoming["payload"]["_session_token"] == "s-1"
            return {
                "message_id": "m2",
                "source": "core",
                "destination": "d",
                "message_type": "DEVICE_REGISTER_RESPONSE",
                "timestamp": "t",
                "request_id": incoming.get("request_id"),
                "payload": {"registered": True},
                "identity_id": "d",
            }
        return None

    _peer_script(peer_end, script)
    # Bypass connect(): drive the post-socket flow manually.
    client._sock = client_end
    # Simulate post-handshake state then register.
    client._session_token = "s-1"
    client._connection_id = "c-1"
    response = client.register(capabilities=["chat"])
    assert response["message_type"] == "DEVICE_REGISTER_RESPONSE"
    assert client.registered is True
    client.close()
    assert client.connected is False


def test_register_payload_passes_host_validation_with_device_identity():
    client_end, peer_end = socket.socketpair()
    client = CoreTcpClient(host="h", port=1, device_id="d", credential="c")
    client._sock = client_end
    client._session_token = "s-1"
    captured = {}

    def script(incoming):
        assert incoming["message_type"] == "DEVICE_REGISTER"
        captured["payload"] = incoming["payload"]
        return {
            "message_id": "m2",
            "source": "core",
            "destination": "d",
            "message_type": "DEVICE_REGISTER_RESPONSE",
            "timestamp": "t",
            "request_id": incoming.get("request_id"),
            "payload": {"registered": True},
            "identity_id": "d",
        }

    _peer_script(peer_end, script)
    client.register(capabilities=["chat"])
    payload = captured["payload"]
    assert payload["device_type"] == "tiviss"
    assert isinstance(payload["platform"], str) and payload["platform"].strip()
    assert payload["platform"] == client.platform
    assert _host_validate_registration_payload(payload) == (None, None)
    assert payload["protocol_version"] == PROTOCOL_VERSION
    client.close()


def test_register_device_identity_sanitizes_platform_and_rejects_blanks():
    client = CoreTcpClient(
        host="h",
        port=1,
        device_id="d",
        credential="c",
        device_type="tiviss-edge",
        platform="Darwin ARM64",
    )
    assert client.device_type == "tiviss-edge"
    assert client.platform == "darwin-arm64"
    with pytest.raises(DeviceClientError):
        CoreTcpClient(
            host="h", port=1, device_id="d", credential="c", device_type=" "
        )
    with pytest.raises(DeviceClientError):
        CoreTcpClient(
            host="h", port=1, device_id="d", credential="c", platform="!!!"
        )


def test_request_id_mismatch_drops_connection():
    client_end, peer_end = socket.socketpair()
    client = CoreTcpClient(host="h", port=1, device_id="d", credential="c")
    client._sock = client_end
    client._session_token = "s-1"
    client._registered = True

    def script(incoming):
        reply = dict(_handshake_response())
        reply.update(
            {
                "message_type": "DEVICE_INFO_RESPONSE",
                "request_id": "someone-elses-id",
                "payload": {},
            }
        )
        return reply

    _peer_script(peer_end, script)
    with pytest.raises(DeviceClientError, match="correlation mismatch"):
        client.request("core", "DEVICE_INFO", {"device_id": "d"})
    assert client.connected is False


def test_host_error_raises():
    client_end, peer_end = socket.socketpair()
    client = CoreTcpClient(host="h", port=1, device_id="d", credential="c")
    client._sock = client_end
    client._session_token = "s-1"
    client._registered = True

    def script(incoming):
        return {
            "message_id": "m9",
            "source": "core",
            "destination": "d",
            "message_type": "DEVICE_ERROR",
            "timestamp": "t",
            "request_id": incoming.get("request_id"),
            "payload": {"error": "DEVICE_NOT_FOUND", "message": "nope"},
            "identity_id": "d",
        }

    _peer_script(peer_end, script)
    with pytest.raises(DeviceClientError, match="DEVICE_NOT_FOUND"):
        client.request("core", "DEVICE_INFO", {})
    client.close()


def test_auth_rejected_clears_state(monkeypatch):
    client_end, peer_end = socket.socketpair()
    monkeypatch.setattr(
        "tiviss.integrations.core_tcp.socket.create_connection",
        lambda *args, **kwargs: client_end,
    )

    def script(incoming):
        reply = _handshake_response()
        reply["payload"] = {"authenticated": False}
        _write_frame(peer_end, reply)

    thread = threading.Thread(
        target=lambda: script(_read_frame(peer_end)), daemon=True
    )
    thread.start()
    client = CoreTcpClient(
        host="h", port=1, device_id="d", credential="bad", use_tls=False
    )
    with pytest.raises(DeviceClientError, match="authentication rejected"):
        client.connect()
    assert client.connected is False
    assert client.registered is False
