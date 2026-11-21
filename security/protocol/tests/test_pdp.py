"""PDP schema tests: roundtrip, validation, default-deny helpers."""

from __future__ import annotations

import pytest

from tiviss_security_protocol import (
    TYPE_DECIDE,
    Decision,
    DecisionRequest,
    DecisionResponse,
    ProtocolError,
    SchemaError,
    deny_response,
)


def test_request_roundtrip():
    request = DecisionRequest(
        subject="alice",
        action="read",
        resource="rescs://docs/a",
        context={"ip": "127.0.0.1"},
        request_id="req-1",
    )
    again = DecisionRequest.from_dict(request.to_dict())
    assert again == request
    assert request.to_dict()["context"] == {"ip": "127.0.0.1"}


def test_request_from_dict_generates_request_id():
    request = DecisionRequest.from_dict(
        {"subject": "s", "action": "a", "resource": "r"}
    )
    assert request.request_id
    assert request.context == {}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"subject": "", "action": "a", "resource": "r"},
        {"subject": "s", "action": "", "resource": "r"},
        {"subject": "s", "action": "a", "resource": ""},
        {"subject": 5, "action": "a", "resource": "r"},
        {"subject": "s", "action": "a", "resource": "r", "context": "not-a-dict"},
        {"subject": "s", "action": "a", "resource": "r", "request_id": 42},
    ],
)
def test_request_validation_fails_closed(payload):
    with pytest.raises(SchemaError):
        DecisionRequest.from_dict(payload)


def test_response_roundtrip():
    response = DecisionResponse(
        decision=Decision.ALLOW,
        request_id="req-1",
        reason="policy-7",
        obligations=("audit", "log"),
        decision_id="dec-1",
    )
    assert response.allowed is True
    again = DecisionResponse.from_dict(response.to_dict())
    assert again == response
    assert again.obligations == ("audit", "log")


def test_deny_response_is_fail_closed():
    request = DecisionRequest(subject="s", action="a", resource="r", request_id="req-9")
    response = deny_response(request, "no matching policy")
    assert response.decision is Decision.DENY
    assert response.allowed is False
    assert response.request_id == "req-9"
    assert response.reason == "no matching policy"


def test_decision_is_json_string():
    import json

    assert json.dumps({"d": str(Decision.ALLOW)}) == '{"d": "allow"}'
    assert json.dumps({"d": str(Decision.DENY)}) == '{"d": "deny"}'
    assert Decision("allow") is Decision.ALLOW
    assert Decision("deny") is Decision.DENY


@pytest.mark.parametrize(
    "payload",
    [
        {"decision": "maybe"},
        {"decision": True},
        {"decision": None},
        {"decision": "allow", "obligations": "audit"},
        {"decision": "allow", "obligations": [1]},
        {"decision": "allow", "request_id": 7},
        {"decision": "allow", "reason": None},
        {"decision": "allow", "decision_id": ""},
    ],
)
def test_response_validation_fails_closed(payload):
    with pytest.raises(SchemaError):
        DecisionResponse.from_dict(payload)


def test_response_defaults():
    response = DecisionResponse.from_dict({"decision": "deny"})
    assert response.allowed is False
    assert response.obligations == ()
    assert response.decision_id
    assert response.request_id == ""


def test_wire_type_constant():
    assert TYPE_DECIDE == "pdp.decide"


def test_errors_are_protocol_errors():
    assert issubclass(SchemaError, ProtocolError)
    assert issubclass(DecisionRequest.from_dict.__class__, object)  # sanity
    with pytest.raises(ProtocolError):
        DecisionRequest.from_dict({"subject": "", "action": "", "resource": ""})
