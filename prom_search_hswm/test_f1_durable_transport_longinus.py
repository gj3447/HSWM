from __future__ import annotations

import json
from pathlib import Path

import pytest

from prom_search_hswm.verify_f1_durable_transport_longinus import (
    BindingError,
    DEFAULT_MANIFEST,
    verify,
)


def test_checked_in_f1_transport_binding_is_exact() -> None:
    result = verify()
    assert result["status"] == "PASS"
    assert result["longinus_layers"] == 7
    assert result["kg_write_state"] == "NOT_AUTHORIZED_NOT_WRITTEN"


def test_f1_transport_binding_rejects_source_hash_drift(tmp_path: Path) -> None:
    value = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    value["bindings"][0]["sha256"] = "0" * 64
    changed = tmp_path / "binding.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BindingError, match="source bytes drifted"):
        verify(changed)


def test_f1_transport_binding_rejects_missing_artifact_role(tmp_path: Path) -> None:
    value = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    value["bindings"] = [
        binding for binding in value["bindings"] if binding["layer"] != "L6_RECEIPT"
    ]
    changed = tmp_path / "binding.json"
    changed.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BindingError, match="artifact-role coverage"):
        verify(changed)
