"""PDP decision schema — request/response contract for the policy daemon.

Default posture is **deny**: a request that fails schema validation must be
answered with :func:`deny_response` (or simply not answered), never with an
allow.  :class:`Decision` is a ``str`` enum so responses serialize directly
to JSON.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import SchemaError

TYPE_DECIDE = "pdp.decide"
TYPE_HEALTH = "pdp.health"
TYPE_VERSION = "pdp.version"


class Decision(str, Enum):
    """PDP outcome. ``str(Decision.ALLOW) == "allow"`` on every supported Python."""

    ALLOW = "allow"
    DENY = "deny"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    def __format__(self, format_spec: str) -> str:  # pragma: no cover - trivial
        return str.__format__(str(self.value), format_spec)


def _require_str(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise SchemaError(f"{key} must be a non-empty string")
    return value


@dataclass(frozen=True)
class DecisionRequest:
    """A single question: may ``subject`` perform ``action`` on ``resource``?"""

    subject: str
    action: str
    resource: str
    context: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DecisionRequest:
        if not isinstance(data, Mapping):
            raise SchemaError("decision request must be a JSON object")
        subject = _require_str(data, "subject")
        action = _require_str(data, "action")
        resource = _require_str(data, "resource")
        context = data.get("context", {})
        if not isinstance(context, dict):
            raise SchemaError("context must be a JSON object")
        request_id = data.get("request_id")
        if request_id is None:
            request_id = str(uuid.uuid4())
        if not isinstance(request_id, str) or not request_id:
            raise SchemaError("request_id must be a non-empty string")
        return cls(
            subject=subject,
            action=action,
            resource=resource,
            context=dict(context),
            request_id=request_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "action": self.action,
            "resource": self.resource,
            "context": dict(self.context),
            "request_id": self.request_id,
        }


@dataclass(frozen=True)
class DecisionResponse:
    """PDP answer. ``obligations`` are caller-imposed conditions (e.g. audit)."""

    decision: Decision
    request_id: str = ""
    reason: str = ""
    obligations: tuple[str, ...] = ()
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DecisionResponse:
        if not isinstance(data, Mapping):
            raise SchemaError("decision response must be a JSON object")
        raw_decision = data.get("decision")
        try:
            decision = Decision(raw_decision)
        except (ValueError, TypeError) as exc:
            raise SchemaError(
                f"decision must be 'allow' or 'deny', got {raw_decision!r}"
            ) from exc
        request_id = data.get("request_id", "")
        if not isinstance(request_id, str):
            raise SchemaError("request_id must be a string")
        reason = data.get("reason", "")
        if not isinstance(reason, str):
            raise SchemaError("reason must be a string")
        obligations_raw = data.get("obligations", [])
        if not isinstance(obligations_raw, list) or not all(
            isinstance(item, str) for item in obligations_raw
        ):
            raise SchemaError("obligations must be a list of strings")
        decision_id = data.get("decision_id")
        if decision_id is None:
            decision_id = str(uuid.uuid4())
        if not isinstance(decision_id, str) or not decision_id:
            raise SchemaError("decision_id must be a non-empty string")
        return cls(
            decision=decision,
            request_id=request_id,
            reason=reason,
            obligations=tuple(obligations_raw),
            decision_id=decision_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": str(self.decision),
            "request_id": self.request_id,
            "reason": self.reason,
            "obligations": list(self.obligations),
            "decision_id": self.decision_id,
        }


def deny_response(request: DecisionRequest, reason: str) -> DecisionResponse:
    """Fail-closed helper: a DENY bound to ``request``."""
    return DecisionResponse(
        decision=Decision.DENY,
        request_id=request.request_id,
        reason=reason or "denied",
    )


__all__ = [
    "TYPE_DECIDE",
    "TYPE_HEALTH",
    "TYPE_VERSION",
    "Decision",
    "DecisionRequest",
    "DecisionResponse",
    "deny_response",
]
