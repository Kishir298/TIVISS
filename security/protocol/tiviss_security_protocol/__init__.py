"""T.I.V.I.S.S. security protocol — framing, capability tokens, PDP schema.

Stdlib-only (``json``, ``struct``, ``hmac``, ``hashlib``, ``base64``,
``secrets``, ``socket`` helpers).  Distributions:

- ``tiviss-security-protocol`` (this package) — the wire contract, shared by
  host, daemon and client.
- ``tiviss-security-ipc`` / ``tiviss-security-host`` — UDS transport and the
  local PDP daemon (planned).
"""

from __future__ import annotations

from .errors import FrameError, ProtocolError, SchemaError, TokenError
from .framing import (
    MAX_FRAME,
    decode_frame,
    encode_frame,
    envelope,
    read_frame,
    send_frame,
    validate_envelope,
)
from .pdp import (
    TYPE_DECIDE,
    TYPE_HEALTH,
    TYPE_VERSION,
    Decision,
    DecisionRequest,
    DecisionResponse,
    deny_response,
)
from .tokens import DEFAULT_TTL_SECONDS, TokenClaims, generate_secret, mint, verify
from .version import PROTOCOL_NAME, PROTOCOL_VERSION

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "MAX_FRAME",
    "ProtocolError",
    "FrameError",
    "TokenError",
    "SchemaError",
    "encode_frame",
    "decode_frame",
    "envelope",
    "validate_envelope",
    "read_frame",
    "send_frame",
    "TokenClaims",
    "generate_secret",
    "mint",
    "verify",
    "DEFAULT_TTL_SECONDS",
    "Decision",
    "DecisionRequest",
    "DecisionResponse",
    "deny_response",
    "TYPE_DECIDE",
    "TYPE_HEALTH",
    "TYPE_VERSION",
]
