"""T.I.V.I.S.S. configuration.

Configuration controls real agent behavior (identity, model, memory, and
permissions) with validation and sensible defaults. Secrets are never read
from source; settings can be supplied explicitly or via ``TIVISS_*``
environment variables. No secrets are hard-coded here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping

from .. import __version__ as _package_version


class ConfigValidationError(ValueError):
    """Raised when a configuration is invalid."""


@dataclass
class AgentSettings:
    name: str = "tiviss"
    version: str = _package_version
    agent_id: str | None = None
    owner_id: str = "unassigned"


@dataclass
class ModelSettings:
    provider_id: str = "mock"
    model_id: str = "tiviss-mock-1"
    prefix: str = "ack"


@dataclass
class MemorySettings:
    backend: str = "local"
    storage_path: str | None = None


@dataclass
class PermissionSettings:
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)


@dataclass
class RuntimeSettings:
    enabled: bool = True


@dataclass
class CoreSettings:
    enabled: bool = False
    endpoint: str | None = None


@dataclass
class RescsSettings:
    enabled: bool = False
    endpoint: str | None = None


@dataclass
class TIVISSConfig:
    """Validated, environment-overridable configuration."""

    agent: AgentSettings = field(default_factory=AgentSettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    permissions: PermissionSettings = field(default_factory=PermissionSettings)
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    core: CoreSettings = field(default_factory=CoreSettings)
    rescs: RescsSettings = field(default_factory=RescsSettings)

    @classmethod
    def defaults(cls) -> "TIVISSConfig":
        return cls()

    def validate(self) -> list[str]:
        """Return a list of configuration problems (empty when valid)."""
        errors: list[str] = []
        if not self.agent.name.strip():
            errors.append("agent.name must be a non-empty string")
        if not self.agent.version.strip():
            errors.append("agent.version must be a non-empty string")
        if not self.agent.owner_id.strip():
            errors.append("agent.owner_id must be a non-empty string")
        if self.agent.agent_id is not None and not self.agent.agent_id.strip():
            errors.append("agent.agent_id must be a non-empty string when provided")

        if self.model.provider_id not in {"mock", "local"}:
            errors.append(f"model.provider_id must be one of 'mock', 'local'; got {self.model.provider_id!r}")
        if not self.model.model_id.strip():
            errors.append("model.model_id must be a non-empty string")

        if self.memory.backend not in {"local", "rescs"}:
            errors.append(f"memory.backend must be one of 'local', 'rescs'; got {self.memory.backend!r}")

        for permission in [*self.permissions.allow, *self.permissions.deny]:
            if not self._valid_permission(permission):
                errors.append(f"permission is malformed: {permission!r}")

        if self.memory.storage_path:
            import pathlib

            parent = pathlib.Path(self.memory.storage_path).parent
            if not pathlib.Path(parent).exists():
                errors.append(f"memory.storage_path parent does not exist: {parent}")
        return errors

    @staticmethod
    def _valid_permission(name: str) -> bool:
        from ..permissions.permissions import Permission

        try:
            Permission.of(name)
        except ValueError:
            return False
        return True

    def assert_valid(self) -> None:
        errors = self.validate()
        if errors:
            raise ConfigValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent.__dict__,
            "model": self.model.__dict__,
            "memory": self.memory.__dict__,
            "permissions": {"allow": list(self.permissions.allow), "deny": list(self.permissions.deny)},
            "runtime": self.runtime.__dict__,
            "core": self.core.__dict__,
            "rescs": self.rescs.__dict__,
        }

    # --- building agents -------------------------------------------------

    def build_identity(self):
        from ..identity.identity import AgentIdentity

        return AgentIdentity.create(
            agent_id=self.agent.agent_id,
            name=self.agent.name,
            version=self.agent.version,
            owner_id=self.agent.owner_id,
        )

    def build_provider(self):
        from ..models.mock import MockProvider

        if self.model.provider_id == "mock":
            return MockProvider(model_id=self.model.model_id, prefix=self.model.prefix)
        raise ConfigValidationError(f"provider {self.model.provider_id!r} is not implemented yet")

    def build_policy(self):
        from ..permissions.permissions import Permission
        from ..permissions.policy import DefaultDenyPolicy

        return DefaultDenyPolicy(
            allow={Permission.of(p) for p in self.permissions.allow},
            deny={Permission.of(p) for p in self.permissions.deny},
        )

    def build_memory(self):
        if self.memory.backend == "local":
            from ..memory.local import LocalMemory

            return LocalMemory(storage_path=self.memory.storage_path)
        return None  # 'rescs' backend resolved via the RESCS adapter

    # --- loading ---------------------------------------------------------

    _ENV_MAP: ClassVar[dict[str, tuple[str, ...]]] = {
        "agent_id": ("TIVISS_AGENT_ID",),
        "name": ("TIVISS_AGENT_NAME",),
        "version": ("TIVISS_AGENT_VERSION",),
        "owner_id": ("TIVISS_OWNER_ID",),
        "model_id": ("TIVISS_MODEL_ID",),
        "prefix": ("TIVISS_MODEL_PREFIX",),
        "backend": ("TIVISS_MEMORY_BACKEND",),
        "storage_path": ("TIVISS_MEMORY_STORAGE_PATH",),
        "allow": ("TIVISS_PERMISSION_ALLOW",),
        "deny": ("TIVISS_PERMISSION_DENY",),
        "runtime_enabled": ("TIVISS_RUNTIME_ENABLED",),
        "core_enabled": ("TIVISS_CORE_ENABLED",),
        "rescs_enabled": ("TIVISS_RESCS_ENABLED",),
    }

    @classmethod
    def load(cls, data: Mapping[str, Any]) -> "TIVISSConfig":
        """Load from a mapping, then normalise and validate."""
        config = cls.defaults()
        agent = data.get("agent") or {}
        model = data.get("model") or {}
        memory = data.get("memory") or {}
        permissions = data.get("permissions") or {}
        runtime = data.get("runtime") or {}
        core = data.get("core") or {}
        rescs = data.get("rescs") or {}

        config.agent = AgentSettings(
            name=str(agent.get("name", config.agent.name)),
            version=str(agent.get("version", config.agent.version)),
            agent_id=str(agent["agent_id"]) if agent.get("agent_id") is not None else None,
            owner_id=str(agent.get("owner_id", config.agent.owner_id)),
        )
        config.model = ModelSettings(
            provider_id=str(model.get("provider_id", "mock")),
            model_id=str(model.get("model_id", config.model.model_id)),
            prefix=str(model.get("prefix", config.model.prefix)),
        )
        config.memory = MemorySettings(
            backend=str(memory.get("backend", config.memory.backend)),
            storage_path=str(memory["storage_path"]) if memory.get("storage_path") else None,
        )
        config.permissions = PermissionSettings(
            allow=[str(p) for p in (permissions.get("allow") or [])],
            deny=[str(p) for p in (permissions.get("deny") or [])],
        )
        config.runtime = RuntimeSettings(enabled=bool(runtime.get("enabled", config.runtime.enabled)))
        config.core = CoreSettings(enabled=bool(core.get("enabled", False)), endpoint=core.get("endpoint"))
        config.rescs = RescsSettings(enabled=bool(rescs.get("enabled", False)), endpoint=rescs.get("endpoint"))
        config.assert_valid()
        return config

    @classmethod
    def load_env(cls, environ: Mapping[str, str] | None = None) -> "TIVISSConfig":
        """Load configuration from ``TIVISS_*`` environment variables."""
        env = os.environ if environ is None else environ

        def _get(*names: str) -> str | None:
            for name in names:
                value = env.get(name)
                if value:
                    return value
            return None

        def _to_list(value: str | None) -> list[str]:
            return [item.strip() for item in value.split(",") if item.strip()] if value else []

        config = cls.defaults()
        if name := _get("TIVISS_AGENT_NAME"):
            config.agent.name = name
        if version := _get("TIVISS_AGENT_VERSION"):
            config.agent.version = version
        if agent_id := _get("TIVISS_AGENT_ID"):
            config.agent.agent_id = agent_id
        if owner := _get("TIVISS_OWNER_ID"):
            config.agent.owner_id = owner
        if model_id := _get("TIVISS_MODEL_ID"):
            config.model.model_id = model_id
        if prefix := _get("TIVISS_MODEL_PREFIX"):
            config.model.prefix = prefix
        if backend := _get("TIVISS_MEMORY_BACKEND"):
            config.memory.backend = backend
        if path := _get("TIVISS_MEMORY_STORAGE_PATH"):
            config.memory.storage_path = path
        if raw_allow := _get("TIVISS_PERMISSION_ALLOW"):
            config.permissions.allow = _to_list(raw_allow)
        if raw_deny := _get("TIVISS_PERMISSION_DENY"):
            config.permissions.deny = _to_list(raw_deny)
        if raw_runtime := _get("TIVISS_RUNTIME_ENABLED"):
            config.runtime.enabled = raw_runtime.strip().lower() in {"1", "true", "yes", "on"}
        if raw_core := _get("TIVISS_CORE_ENABLED"):
            config.core.enabled = raw_core.strip().lower() in {"1", "true", "yes", "on"}
        if raw_rescs := _get("TIVISS_RESCS_ENABLED"):
            config.rescs.enabled = raw_rescs.strip().lower() in {"1", "true", "yes", "on"}
        config.assert_valid()
        return config