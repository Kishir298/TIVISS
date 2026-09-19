import json

import pytest

from tiviss.configuration import TIVISSConfig
from tiviss.identity import Ownership
from tiviss.memory.interface import MemoryRecord
from tiviss.memory.local import LocalMemory
from tiviss.state_io import (
    EXPORT_VERSION,
    StateImportError,
    export_state,
    import_state,
)


def _parts():
    config = TIVISSConfig.load(
        {
            "agent": {"name": "t", "owner_id": "kishir", "agent_id": "a-1"},
            "permissions": {"allow": ["conversation.generate"]},
        }
    )
    identity = config.build_identity()
    ownership = Ownership.create("kishir")
    memory = LocalMemory()
    memory.store(
        MemoryRecord(
            key="fact", content="likes tea", metadata={"session_token": "s3cr3t"}
        )
    )
    return config, identity, ownership, memory


def test_export_roundtrip():
    config, identity, ownership, memory = _parts()
    records = memory.search("").records
    doc = export_state(
        identity=identity,
        ownership=ownership,
        model={"provider_id": "mock", "model_id": "m"},
        permissions={"allow": ["conversation.generate"], "deny": []},
        memory_records=records,
        counters={"requests_handled": 3},
    )
    assert doc["tiviss_export"] is True
    assert doc["version"] == EXPORT_VERSION
    assert doc["integrity"]
    # Secret metadata dropped + recorded.
    assert doc["dropped_secrets"] == ["memory.fact.session_token"]
    assert doc["payload"]["memory_records"][0]["metadata"] == {}
    raw = json.dumps(doc)
    restored = import_state(json.loads(raw))
    assert restored.agent_id == "a-1"
    assert restored.identity.owner_id == "kishir"
    assert restored.ownership.owner_id == "kishir"
    assert len(restored.memory_records) == 1
    assert restored.counters == {"requests_handled": 3}


def test_export_drops_identity_meta_secrets():
    from tiviss.identity import AgentIdentity

    identity = AgentIdentity.create(
        name="t", version="1", owner_id="k", meta={"api_key": "K", "nick": "t"}
    )
    ownership = Ownership.create("k")
    doc = export_state(
        identity=identity,
        ownership=ownership,
        model={},
        permissions={},
        memory_records=[],
    )
    assert doc["payload"]["identity"]["meta"] == {"nick": "t"}
    assert "identity.meta.api_key" in doc["dropped_secrets"]
    assert import_state(doc).identity.meta == {"nick": "t"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("tiviss_export"),
        lambda d: d.update(version=999),
        lambda d: d["payload"].pop("identity"),
        lambda d: d.update(integrity="0" * 64),
        lambda d: d["payload"]["counters"].update({"x": "not-an-int"}),
    ],
)
def test_import_rejects_invalid(mutate):
    config, identity, ownership, memory = _parts()
    doc = export_state(
        identity=identity,
        ownership=ownership,
        model={},
        permissions={},
        memory_records=[],
    )
    mutate(doc)
    with pytest.raises(StateImportError):
        import_state(doc)


def test_import_rejects_non_mapping():
    with pytest.raises(StateImportError):
        import_state(["not", "a", "mapping"])
