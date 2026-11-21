"""HMAC-SHA256 capability tokens (stdlib-only).

Token format::

    base64url(utf8(json(claims))) + "." + base64url(hmac_sha256(secret, signing_input))

Verification is fail-closed: any malformed, tampered, wrong-secret, or
expired token raises :class:`TokenError`.  Comparison uses
:func:`hmac.compare_digest` (constant time).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import TokenError

DEFAULT_TTL_SECONDS = 300
SECRET_BYTES = 32
_ALLOWED_CLAIMS = frozenset({"sub", "act", "res", "iat", "exp", "jti", "nonce"})


def generate_secret() -> bytes:
    """Return a fresh 256-bit secret (for key generation, not storage)."""
    return secrets.token_bytes(SECRET_BYTES)


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except (ValueError, TypeError) as exc:
        raise TokenError(f"invalid base64url segment: {exc}") from exc


@dataclass(frozen=True)
class TokenClaims:
    """Verified capability-token claims."""

    sub: str
    act: str
    res: str
    iat: int
    exp: int
    jti: str
    nonce: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TokenClaims:
        if not isinstance(data, Mapping):
            raise TokenError("claims must be a JSON object")
        unknown = set(data) - _ALLOWED_CLAIMS
        if unknown:
            raise TokenError(f"unknown claims: {sorted(unknown)}")
        for key in ("sub", "act", "res", "jti"):
            if not isinstance(data.get(key), str) or not data[key]:
                raise TokenError(f"claim {key!r} must be a non-empty string")
        for key in ("iat", "exp"):
            value = data.get(key)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TokenError(f"claim {key!r} must be an integer timestamp")
        nonce = data.get("nonce")
        if nonce is not None and (not isinstance(nonce, str) or not nonce):
            raise TokenError("claim 'nonce' must be a non-empty string when present")
        if data["exp"] <= data["iat"]:
            raise TokenError("claim 'exp' must be greater than 'iat'")
        return cls(
            sub=data["sub"],
            act=data["act"],
            res=data["res"],
            iat=data["iat"],
            exp=data["exp"],
            jti=data["jti"],
            nonce=nonce,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "sub": self.sub,
            "act": self.act,
            "res": self.res,
            "iat": self.iat,
            "exp": self.exp,
            "jti": self.jti,
        }
        if self.nonce is not None:
            out["nonce"] = self.nonce
        return out

    def is_expired(self, now: int | None = None, leeway: int = 0) -> bool:
        current = int(time.time()) if now is None else now
        return current >= self.exp + leeway


def mint(
    *,
    sub: str,
    act: str,
    res: str,
    secret: bytes,
    ttl: int = DEFAULT_TTL_SECONDS,
    nonce: str | None = None,
    now: int | None = None,
    jti: str | None = None,
) -> str:
    """Mint a signed capability token.

    ``sub``/``act``/``res`` are the subject, action and resource the
    capability is scoped to.  The token is bearer material: whoever holds it
    (and the shared secret on the verifier side) can exercise the capability
    until ``exp``.
    """
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < SECRET_BYTES:
        raise TokenError(f"secret must be at least {SECRET_BYTES} bytes")
    for key, value in (("sub", sub), ("act", act), ("res", res)):
        if not isinstance(value, str) or not value:
            raise TokenError(f"{key} must be a non-empty string")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
        raise TokenError("ttl must be a positive integer")
    if nonce is not None and (not isinstance(nonce, str) or not nonce):
        raise TokenError("nonce must be a non-empty string when provided")
    if jti is not None and (not isinstance(jti, str) or not jti):
        raise TokenError("jti must be a non-empty string when provided")
    current = int(time.time()) if now is None else now
    claims = TokenClaims(
        sub=sub,
        act=act,
        res=res,
        iat=current,
        exp=current + ttl,
        jti=jti or str(uuid.uuid4()),
        nonce=nonce,
    )
    signing_input = _b64u_encode(
        json.dumps(claims.to_dict(), separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )
    signature = hmac.new(
        bytes(secret), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_b64u_encode(signature)}"


def verify(
    token: str, secret: bytes, *, now: int | None = None, leeway: int = 0
) -> TokenClaims:
    """Verify ``token`` and return its claims.

    Raises :class:`TokenError` for any failure — malformed structure, bad
    signature, wrong secret, expired, or invalid claim types.  Callers must
    treat the exception as a denial.
    """
    if not isinstance(token, str) or not token:
        raise TokenError("token must be a non-empty string")
    if not isinstance(secret, (bytes, bytearray)) or len(secret) < SECRET_BYTES:
        raise TokenError(f"secret must be at least {SECRET_BYTES} bytes")
    parts = token.split(".")
    if len(parts) != 2:
        raise TokenError("token must have exactly two segments")
    signing_input, signature_b64 = parts
    if not signing_input or not signature_b64:
        raise TokenError("token segments must be non-empty")
    expected = hmac.new(
        bytes(secret), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    actual = _b64u_decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise TokenError("token signature mismatch")
    try:
        claims_dict = json.loads(_b64u_decode(signing_input).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TokenError(f"token claims are not valid UTF-8 JSON: {exc}") from exc
    claims = TokenClaims.from_dict(claims_dict)
    current = int(time.time()) if now is None else now
    if claims.is_expired(now=current, leeway=leeway):
        raise TokenError("token expired")
    if claims.iat - leeway > current:
        raise TokenError("token issued in the future")
    return claims


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "SECRET_BYTES",
    "TokenClaims",
    "generate_secret",
    "mint",
    "verify",
]
