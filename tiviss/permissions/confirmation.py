"""Loopback approval broker client for dangerous T.I.V.I.S.S. tool calls.

RISARMS-ui launches local agents with ``RISARMS_APPROVAL_URL``,
``RISARMS_APPROVAL_TOKEN`` and ``RISARMS_APPROVAL_JOB`` in the environment.
Dangerous tool permissions are confirmed through that loopback broker; any
transport or response failure is treated as a denial.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.request import Request, urlopen

from .permissions import Permission

BROKER_TIMEOUT_S = 125
ALLOWED_DECISIONS = frozenset({"allow_once", "allow_session"})
DANGEROUS_PERMISSION_PREFIXES: tuple[str, ...] = (
    "tools.coding",
    "tools.web",
    "tools.voice",
    "tools.core",
    "tools.rescs",
    "handover",
    "core",
    "rescs",
)

_MAX_COMMAND_CHARS = 4000
_MAX_STRING_CHARS = 500
_MAX_CONTAINER_ITEMS = 50
_MAX_DEPTH = 5
_REDACTED = "<redacted>"
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "session",
)

class Approver(Protocol):
    """Callable that asks the broker whether one permission may proceed."""

    def __call__(
        self,
        permission: Permission | str,
        tool_id: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> bool: ...


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def broker_configured() -> bool:
    """True when the RISARMS-ui loopback broker environment is present."""
    return bool(_env("RISARMS_APPROVAL_URL") and _env("RISARMS_APPROVAL_TOKEN"))


def _normalized_prefix(prefix: str) -> str:
    prefix = prefix.strip()
    if prefix.endswith(".*"):
        prefix = prefix[:-2]
    return prefix.rstrip(".")


def _permission_name(permission: Permission | str) -> str:
    if isinstance(permission, Permission):
        return permission.name
    return str(permission)


def is_dangerous(permission: Permission | str) -> bool:
    """Return True when ``permission`` needs broker confirmation."""
    name = _permission_name(permission)
    for raw_prefix in DANGEROUS_PERMISSION_PREFIXES:
        prefix = _normalized_prefix(raw_prefix)
        if name == prefix or name.startswith(f"{prefix}."):
            return True
    return False


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _sensitive_key(key: Any) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _sanitize(value: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate(value, _MAX_STRING_CHARS)
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, Mapping):
        items = list(value.items())[:_MAX_CONTAINER_ITEMS]
        return {
            _truncate(str(key), 100): (
                _REDACTED if _sensitive_key(key) else _sanitize(item, depth + 1)
            )
            for key, item in items
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _sanitize(item, depth + 1)
            for item in list(value)[:_MAX_CONTAINER_ITEMS]
        ]
    try:
        rendered = str(value)
    except Exception:
        rendered = f"<{type(value).__name__}>"
    return _truncate(rendered, _MAX_STRING_CHARS)


def format_command(tool_id: str, params: Mapping[str, Any] | None = None) -> str:
    """Build a bounded, secret-free description of the requested tool call."""
    sanitized = _sanitize(params or {})
    try:
        rendered = json.dumps(
            sanitized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError):
        rendered = "{}"
    return _truncate(f"{_truncate(str(tool_id), 200)} {rendered}", _MAX_COMMAND_CHARS)


def broker_approver() -> Approver | None:
    """Return a loopback approver, or None when no broker is configured."""
    url = _env("RISARMS_APPROVAL_URL")
    token = _env("RISARMS_APPROVAL_TOKEN")
    if not url or not token:
        return None

    def approve(
        permission: Permission | str,
        tool_id: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> bool:
        action = _permission_name(permission)
        if tool_id is None:
            command = _truncate(action, _MAX_COMMAND_CHARS)
        else:
            command = format_command(tool_id, params)
        try:
            body = json.dumps(
                {
                    "service": "tiviss",
                    "action": action,
                    "command": command,
                    "workspace": os.getcwd(),
                    "details": {"job": _env("RISARMS_APPROVAL_JOB")},
                }
            ).encode("utf-8")
            request = Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-RISARMS-Approval-Token": token,
                },
            )
            with urlopen(request, timeout=BROKER_TIMEOUT_S) as response:
                result = json.loads(response.read(8192))
        except Exception:
            return False
        if not isinstance(result, Mapping):
            return False
        decision = result.get("decision")
        return isinstance(decision, str) and decision in ALLOWED_DECISIONS

    return approve


def build_broker_confirmation() -> Approver | None:
    """Alias matching the confirmation naming used by other RISARMS agents."""
    return broker_approver()
