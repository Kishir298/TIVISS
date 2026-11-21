"""Capability-token tests: roundtrip, tamper, expiry, claim validation."""

from __future__ import annotations

import pytest

from tiviss_security_protocol import (
    DEFAULT_TTL_SECONDS,
    TokenClaims,
    TokenError,
    generate_secret,
    mint,
    verify,
)


@pytest.fixture
def secret() -> bytes:
    return generate_secret()


def test_mint_verify_roundtrip(secret):
    token = mint(
        sub="alice", act="read", res="rescs://docs/a", secret=secret, now=1_000_000
    )
    claims = verify(token, secret, now=1_000_000 + 10)
    assert claims.sub == "alice"
    assert claims.act == "read"
    assert claims.res == "rescs://docs/a"
    assert claims.iat == 1_000_000
    assert claims.exp == 1_000_000 + DEFAULT_TTL_SECONDS
    assert claims.jti
    assert claims.nonce is None


def test_roundtrip_with_nonce_and_custom_ttl(secret):
    token = mint(
        sub="bob",
        act="write",
        res="s3://bucket/k",
        secret=secret,
        ttl=60,
        nonce="n-1",
        now=500,
        jti="fixed-jti",
    )
    claims = verify(token, secret, now=510)
    assert claims.nonce == "n-1"
    assert claims.jti == "fixed-jti"
    assert claims.exp == 560


def test_tampered_signature_rejected(secret):
    token = mint(sub="a", act="r", res="x", secret=secret, now=1_000)
    body, sig = token.split(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(TokenError, match="signature mismatch"):
        verify(f"{body}.{flipped}", secret, now=1_010)


def test_tampered_claims_rejected(secret):
    import base64
    import json

    token = mint(sub="alice", act="read", res="x", secret=secret, now=1_000)
    body, sig = token.split(".")
    padding = "=" * (-len(body) % 4)
    claims = json.loads(base64.urlsafe_b64decode(body + padding))
    claims["sub"] = "mallory"
    forged_body = (
        base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    with pytest.raises(TokenError, match="signature mismatch"):
        verify(f"{forged_body}.{sig}", secret, now=1_010)


def test_wrong_secret_rejected(secret):
    token = mint(sub="a", act="r", res="x", secret=secret, now=1_000)
    with pytest.raises(TokenError, match="signature mismatch"):
        verify(token, generate_secret(), now=1_010)


def test_expired_token_rejected(secret):
    token = mint(sub="a", act="r", res="x", secret=secret, ttl=30, now=1_000)
    with pytest.raises(TokenError, match="expired"):
        verify(token, secret, now=1_030)
    # leeway extends validity
    claims = verify(token, secret, now=1_035, leeway=10)
    assert claims.sub == "a"


def test_future_iat_rejected(secret):
    token = mint(sub="a", act="r", res="x", secret=secret, now=10_000)
    with pytest.raises(TokenError, match="future"):
        verify(token, secret, now=9_000)


@pytest.mark.parametrize(
    "bad_token",
    [
        "",
        "no-dot",
        "a.b.c",
        "..",
        "not-base64!.sig",
        "e30.bm90LXJlYWw",  # valid b64 "e30" = "{}"? actually "{}" missing claims keys
    ],
)
def test_malformed_tokens_rejected(bad_token, secret):
    with pytest.raises(TokenError):
        verify(bad_token, secret, now=1_000)


def test_unknown_claim_rejected(secret):
    import base64
    import json

    claims = {
        "sub": "a",
        "act": "r",
        "res": "x",
        "iat": 1,
        "exp": 2,
        "jti": "j",
        "admin": True,
    }
    body = (
        base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )
    import hashlib
    import hmac

    sig = base64.urlsafe_b64encode(
        hmac.new(secret, body.encode(), hashlib.sha256).digest()
    ).rstrip(b"=")
    with pytest.raises(TokenError, match="unknown claims"):
        verify(f"{body}.{sig.decode()}", secret, now=1)


def test_short_secret_rejected():
    with pytest.raises(TokenError, match="secret"):
        mint(sub="a", act="r", res="x", secret=b"short", now=1)
    with pytest.raises(TokenError, match="secret"):
        verify("x.y", b"short", now=1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sub": "", "act": "r", "res": "x"},
        {"sub": "a", "act": "", "res": "x"},
        {"sub": "a", "act": "r", "res": ""},
        {"sub": 1, "act": "r", "res": "x"},
        {"sub": "a", "act": "r", "res": "x", "ttl": 0},
        {"sub": "a", "act": "r", "res": "x", "ttl": -5},
        {"sub": "a", "act": "r", "res": "x", "nonce": ""},
        {"sub": "a", "act": "r", "res": "x", "jti": ""},
    ],
)
def test_mint_validates_inputs(kwargs, secret):
    with pytest.raises(TokenError):
        mint(secret=secret, now=1, **kwargs)


def test_generate_secret_length_and_uniqueness():
    a, b = generate_secret(), generate_secret()
    assert len(a) == 32
    assert a != b


def test_claims_dict_roundtrip():
    claims = TokenClaims(sub="s", act="a", res="r", iat=1, exp=2, jti="j", nonce="n")
    again = TokenClaims.from_dict(claims.to_dict())
    assert again == claims
    assert claims.is_expired(now=2) is True
    assert claims.is_expired(now=1) is False
