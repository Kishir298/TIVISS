import pytest

from tiviss.configuration import ConfigValidationError, TIVISSConfig
from tiviss.identity import AgentIdentity
from tiviss.memory import LocalMemory
from tiviss.models import MockProvider
from tiviss.permissions import DefaultDenyPolicy


def test_defaults_are_valid():
    config = TIVISSConfig.defaults()
    assert config.validate() == []


def test_default_values():
    config = TIVISSConfig.defaults()
    assert config.agent.name == "tiviss"
    assert config.agent.version
    assert config.model.provider_id == "mock"
    assert config.model.model_id == "tiviss-mock-1"
    assert config.memory.backend == "local"
    assert config.core.enabled is False
    assert config.rescs.enabled is False
    assert config.permissions.allow == []


def test_load_from_mapping():
    config = TIVISSConfig.load(
        {
            "agent": {"name": "tiv", "owner_id": "kishir", "agent_id": "tiv-1"},
            "model": {"model_id": "local-model"},
            "permissions": {"allow": ["conversation.generate"]},
            "core": {"enabled": True},
        }
    )
    assert config.agent.agent_id == "tiv-1"
    assert config.model.model_id == "local-model"
    assert config.permissions.allow == ["conversation.generate"]
    assert config.core.enabled is True


def test_load_invalid_provider_rejected():
    with pytest.raises(ConfigValidationError):
        TIVISSConfig.load({"model": {"provider_id": "openai", "model_id": "x"}})


def test_load_invalid_backend_rejected():
    with pytest.raises(ConfigValidationError):
        TIVISSConfig.load({"memory": {"backend": "tape"}})


def test_load_invalid_permission_rejected():
    with pytest.raises(ConfigValidationError):
        TIVISSConfig.load({"permissions": {"allow": ["not a valid permission!!"]}})


def test_load_env_overrides():
    env = {
        "TIVISS_AGENT_NAME": "env-agent",
        "TIVISS_AGENT_ID": "env-id",
        "TIVISS_OWNER_ID": "env-owner",
        "TIVISS_MODEL_ID": "env-model",
        "TIVISS_PERMISSION_ALLOW": "conversation.generate, memory.store",
        "TIVISS_CORE_ENABLED": "1",
        "TIVISS_RESCS_ENABLED": "true",
    }
    config = TIVISSConfig.load_env(env)
    assert config.agent.name == "env-agent"
    assert config.agent.agent_id == "env-id"
    assert config.agent.owner_id == "env-owner"
    assert config.model.model_id == "env-model"
    assert config.permissions.allow == ["conversation.generate", "memory.store"]
    assert config.core.enabled is True
    assert config.rescs.enabled is True


def test_load_env_without_overrides_uses_defaults(monkeypatch):
    monkeypatch.delenv("TIVISS_AGENT_NAME", raising=False)
    config = TIVISSConfig.load_env({})
    assert config.agent.name == "tiviss"


def test_build_identity():
    config = TIVISSConfig.load({"agent": {"name": "tiv", "owner_id": "kishir", "agent_id": "tiv-1"}})
    identity = config.build_identity()
    assert isinstance(identity, AgentIdentity)
    assert identity.agent_id == "tiv-1"
    assert identity.owner_id == "kishir"


def test_build_provider():
    config = TIVISSConfig.defaults()
    provider = config.build_provider()
    assert isinstance(provider, MockProvider)
    assert provider.model_id == "tiviss-mock-1"


def test_build_policy():
    config = TIVISSConfig.load({"permissions": {"allow": ["memory.store"]}})
    policy = config.build_policy()
    assert isinstance(policy, DefaultDenyPolicy)
    ctx_policy = policy
    from tiviss.permissions import Permission, PermissionContext

    assert ctx_policy.check(PermissionContext(source="owner"), Permission.of("memory.store")) is True
    assert ctx_policy.check(PermissionContext(source="owner"), Permission.of("tools.run")) is False


def test_build_memory(tmp_path):
    config = TIVISSConfig.load({"memory": {"backend": "local", "storage_path": str(tmp_path / "m.json")}})
    memory = config.build_memory()
    assert isinstance(memory, LocalMemory)


def test_secrets_not_in_config_surfaces():
    config = TIVISSConfig.defaults()
    serialized = config.to_dict()
    assert "secret" not in str(serialized).lower()
    assert "token" not in str(serialized).lower()
    assert "password" not in str(serialized).lower()