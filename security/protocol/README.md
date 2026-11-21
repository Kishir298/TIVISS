# tiviss-security-protocol

The wire contract for the T.I.V.I.S.S.-owned security protocol
(**stdlib-only**, Python ≥ 3.10, version `0.1.0`, protocol version `1`).

Part of the [TIVISS-HOST](../../README.md) repository; distribution name
`tiviss-security-protocol`. The client repository (`TIVISS-CLIENT`) pins this
package's version rather than redefining the contract.

## What it defines

| Module | Contract |
|---|---|
| `framing` | 4-byte big-endian length prefix + UTF-8 JSON envelope `{"v","id","type","payload"}`; 1 MiB hard cap; `read_frame`/`send_frame` socket helpers; unknown protocol versions fail closed |
| `tokens` | HMAC-SHA256 capability tokens `b64url(claims).b64url(sig)`; claims `sub/act/res/iat/exp/jti[/nonce]`; constant-time verify; expired/tampered/wrong-secret → `TokenError` (deny) |
| `pdp` | `DecisionRequest` / `DecisionResponse` schema; `Decision.allow|deny`; `deny_response()` fail-closed helper; wire types `pdp.decide`, `pdp.health`, `pdp.version` |

Every error derives from `ProtocolError` (`FrameError`, `TokenError`,
`SchemaError`) so callers fail closed with one `except`.

## Install / test

```bash
pip install -e TIVISS-HOST/security/protocol     # from the RISARMS workspace root
cd TIVISS-HOST/security/protocol && python -m pytest -q
```

## Status

**IMPLEMENTED** (Wave A of the security build). The local PDP daemon
(`tiviss-security-host`), UDS transport (`tiviss-security-ipc`) and the
client embedding are later waves — see `RISARMS-DOCS/` for the plan.
