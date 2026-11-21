"""Protocol-level errors.

Every failure in the protocol package derives from :class:`ProtocolError` so
callers can fail closed with a single ``except ProtocolError``.
"""

from __future__ import annotations


class ProtocolError(Exception):
    """Base error for the TIVISS security protocol."""


class FrameError(ProtocolError):
    """Malformed, oversized, or truncated frame on the wire."""


class TokenError(ProtocolError):
    """Capability token is malformed, tampered with, expired, or untrusted."""


class SchemaError(ProtocolError):
    """Request/response payload violates the protocol schema."""


__all__ = ["ProtocolError", "FrameError", "TokenError", "SchemaError"]
