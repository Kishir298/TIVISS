"""Loopback approval broker integration tests for tool execution."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

import pytest

import tiviss.permissions.confirmation as confirmation
from tiviss.permissions import DefaultDenyPolicy, Permission, PermissionContext
from tiviss.tools import Tool, ToolRegistry, ToolResult, ToolStatus


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self, _limit: int) -> bytes:
        return self.payload


class RecordingTool(Tool):
    def __init__(self, tool_id: str, permissions: tuple[str, ...]) -> None:
        self._tool_id = tool_id
        self._permissions = [Permission.of(name) for name in permissions]
        self.calls: list[dict[str, Any]] = []

    @property
    def tool_id(self) -> str:
        return self._tool_id

    @property
    def name(self) -> str:
        return self._tool_id

    @property
    def description(self) -> str:
        return "Recording tool for approval tests."

    @property
    def permission(self) -> Permission:
        return self._permissions[0]

    def required_permissions(self) -> list[Permission]:
        return list(self._permissions)

    def validate_input(self, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(params)

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        self.calls.append(dict(params))
        return ToolResult(
            tool_id=self._tool_id,
            status=ToolStatus.OK,
            output="executed",
        )


@pytest.fixture(autouse=True)
def _clear_broker_env(monkeypatch):
    for name in (
        "RISARMS_APPROVAL_URL",
        "RISARMS_APPROVAL_TOKEN",
        "RISARMS_APPROVAL_JOB",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def broker_env(monkeypatch):
    monkeypatch.setenv("RISARMS_APPROVAL_URL", "http://127.0.0.1:9999/approve")
    monkeypatch.setenv("RISARMS_APPROVAL_TOKEN", "token-tiviss")
    monkeypatch.setenv("RISARMS_APPROVAL_JOB", "job-9")


def _registry(tool: Tool, *, allow: tuple[str, ...] = ("tools.*",)) -> ToolRegistry:
    policy = DefaultDenyPolicy(allow={Permission.of(name) for name in allow})
    registry = ToolRegistry(policy=policy)
    registry.register(tool)
    return registry


def _ctx() -> PermissionContext:
    return PermissionContext(source="owner")


def test_missing_broker_keeps_policy_behavior(monkeypatch):
    requests = []

    def forbidden(*args, **kwargs):
        requests.append((args, kwargs))
        raise AssertionError("broker must not be called without environment")

    monkeypatch.setattr(confirmation, "urlopen", forbidden)

    tool = RecordingTool("web_fetch", ("tools.web",))
    result = _registry(tool).execute(
        tool.tool_id, _ctx(), {"url": "https://example.test"}
    )
    assert result.status is ToolStatus.OK
    assert tool.calls == [{"url": "https://example.test"}]
    assert requests == []

    denied_tool = RecordingTool("danger", ("tools.coding",))
    denied_registry = ToolRegistry()
    denied_registry.register(denied_tool)
    denied = denied_registry.execute(denied_tool.tool_id, _ctx(), {})
    assert denied.status is ToolStatus.DENIED
    assert denied_tool.calls == []


@pytest.mark.parametrize("decision", ["allow_once", "allow_session"])
def test_broker_allow_proceeds(decision, broker_env, monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request, timeout))
        return FakeResponse({"decision": decision})

    monkeypatch.setattr(confirmation, "urlopen", fake_urlopen)

    tool = RecordingTool("ascs_integration", ("tools.coding",))
    result = _registry(tool).execute(
        tool.tool_id,
        _ctx(),
        {"task": "refactor", "api_key": "sk-super-secret", "nested": {"password": "x"}},
    )

    assert result.status is ToolStatus.OK
    assert tool.calls == [
        {
            "task": "refactor",
            "api_key": "sk-super-secret",
            "nested": {"password": "x"},
        }
    ]

    request, timeout = seen[0]
    assert timeout == 125
    assert request.get_header("X-risarms-approval-token") == "token-tiviss"
    payload = json.loads(request.data)
    assert payload["service"] == "tiviss"
    assert payload["action"] == "tools.coding"
    assert payload["command"].startswith("ascs_integration ")
    assert "refactor" in payload["command"]
    assert "sk-super-secret" not in payload["command"]
    assert '"password":"<redacted>"' in payload["command"]
    assert payload["workspace"] == os.getcwd()
    assert payload["details"] == {"job": "job-9"}


def test_broker_deny_fails_closed(broker_env, monkeypatch):
    def deny(_request, _timeout):
        return FakeResponse({"decision": "deny"})

    monkeypatch.setattr(confirmation, "urlopen", deny)

    tool = RecordingTool("voice_speak", ("tools.voice",))
    result = _registry(tool).execute(tool.tool_id, _ctx(), {"text": "hello"})

    assert result.status is ToolStatus.DENIED
    assert result.metadata["approval"] == "broker"
    assert "denied" in (result.error or "").lower()
    assert tool.calls == []


def test_broker_network_error_fails_closed(broker_env, monkeypatch):
    def offline(_request, _timeout):
        raise OSError("broker offline")

    monkeypatch.setattr(confirmation, "urlopen", offline)

    tool = RecordingTool("web_search", ("tools.web",))
    result = _registry(tool).execute(tool.tool_id, _ctx(), {"query": "x"})

    assert result.status is ToolStatus.DENIED
    assert tool.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        json.dumps({"decision": "allow_forever"}).encode(),
        json.dumps({"decision": ["allow_once"]}).encode(),
    ],
)
def test_broker_malformed_or_unknown_response_fails_closed(
    payload, broker_env, monkeypatch
):
    def malformed(_request, _timeout):
        return FakeResponse(payload)

    monkeypatch.setattr(confirmation, "urlopen", malformed)

    tool = RecordingTool("core_send", ("tools.core",))
    result = _registry(tool).execute(tool.tool_id, _ctx(), {})

    assert result.status is ToolStatus.DENIED
    assert tool.calls == []


@pytest.mark.parametrize(
    "permissions",
    [
        ("tools.calculator",),
        ("tools.safe",),
        ("tools.calculator", "tools.safe"),
    ],
)
def test_harmless_tools_do_not_call_broker(permissions, broker_env, monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse({"decision": "allow_once"})

    monkeypatch.setattr(confirmation, "urlopen", fake_urlopen)

    tool = RecordingTool("calculate", permissions)
    result = _registry(tool).execute(tool.tool_id, _ctx(), {"operation": "1+1"})

    assert result.status is ToolStatus.OK
    assert tool.calls == [{"operation": "1+1"}]
    assert requests == []


def test_every_dangerous_permission_must_pass_broker(broker_env, monkeypatch):
    decisions = iter(["allow_once", "deny"])
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request, timeout))
        return FakeResponse({"decision": next(decisions)})

    monkeypatch.setattr(confirmation, "urlopen", fake_urlopen)

    tool = RecordingTool("combo", ("tools.web", "tools.coding"))
    result = _registry(tool).execute(tool.tool_id, _ctx(), {})

    assert result.status is ToolStatus.DENIED
    assert tool.calls == []
    assert len(seen) == 2
    actions = [json.loads(request.data)["action"] for request, _ in seen]
    assert actions == ["tools.web", "tools.coding"]


def test_later_required_permission_denied_before_execution():
    tool = RecordingTool("combo", ("tools.safe", "tools.web"))
    registry = _registry(tool, allow=("tools.safe",))
    result = registry.execute(tool.tool_id, _ctx(), {})

    assert result.status is ToolStatus.DENIED
    assert result.metadata["permission"] == "tools.web"
    assert tool.calls == []
