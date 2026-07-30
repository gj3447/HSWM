from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from prom_search_hswm.verify_f1_aborted_exposure_v4_longinus import (
    BindingError,
    DEFAULT_MANIFEST,
    EXPECTED_ARTIFACT_COMMIT,
    EXPECTED_BINDING_ID,
    EXPECTED_PIN_COMMIT,
    EXPECTED_PIN_PARENT,
    EXPECTED_PIN_PATH,
    EXPECTED_PRODUCER_COMMIT,
    EXPECTED_PRODUCER_FILES,
    EXPECTED_PRODUCER_ROOT,
    EXPECTED_RECEIPT_RAW_SHA256,
    EXPECTED_RECEIPT_SELF_SHA256,
    PIN_AFTER,
    PIN_BEFORE,
    _changed_paths,
    _commit_blob,
    _git,
    verify,
)


def _changed_manifest(tmp_path: Path, mutate) -> Path:
    value = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    mutate(value)
    changed = tmp_path / "binding.json"
    changed.write_text(json.dumps(value), encoding="utf-8")
    return changed


def test_checked_in_v4_incident_and_pin_are_exact_git_blob_bound() -> None:
    assert verify() == {
        "status": "PASS",
        "binding_id": EXPECTED_BINDING_ID,
        "producer_commit": EXPECTED_PRODUCER_COMMIT,
        "artifact_commit": EXPECTED_ARTIFACT_COMMIT,
        "pin_commit": EXPECTED_PIN_COMMIT,
        "receipt_raw_sha256": EXPECTED_RECEIPT_RAW_SHA256,
        "receipt_self_sha256": EXPECTED_RECEIPT_SELF_SHA256,
        "incident_producer_files_checked": EXPECTED_PRODUCER_FILES,
        "producer_closure_root_sha256": EXPECTED_PRODUCER_ROOT,
        "longinus_layers": 7,
        "seven_layer_targets_checked": 5,
        "blob_authority": "GIT_COMMIT_ONLY",
        "kg_write_state": "NOT_AUTHORIZED_NOT_WRITTEN",
        "scientific_status": "UNJUDGED",
        "historical_v8_upstream_model_calls": 1,
        "a2_upstream_model_calls": 26,
        "cumulative_terminal_upstream_model_calls": 27,
        "prospective_a3_upstream_model_calls": 0,
        "canary_terminal_total": 27,
    }


def test_verifier_never_reads_producer_python_from_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def guarded(path: Path, *args, **kwargs):
        if path.suffix == ".py":
            raise AssertionError(f"worktree Python read: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    assert verify()["blob_authority"] == "GIT_COMMIT_ONLY"


def test_verifier_ignores_ambient_git_control_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"
    ):
        monkeypatch.setenv(name, str(tmp_path / name.casefold()))
    assert verify()["status"] == "PASS"


def test_pin_commit_is_exact_single_path_literal_replacement() -> None:
    assert _changed_paths(EXPECTED_PIN_PARENT, EXPECTED_PIN_COMMIT) == {
        EXPECTED_PIN_PATH
    }
    before = _commit_blob(EXPECTED_PIN_PARENT, EXPECTED_PIN_PATH)
    after = _commit_blob(EXPECTED_PIN_COMMIT, EXPECTED_PIN_PATH)
    assert before.count(PIN_BEFORE) == 1
    assert after == before.replace(PIN_BEFORE, PIN_AFTER, 1)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("path", "prom_search_hswm/foreign.py"),
        ("symbol", "FOREIGN_PIN"),
        ("line", 1),
        ("producer_value", "0" * 64),
        ("pinned_value", "0" * 64),
        ("pre_pin_blob_mode", "100755"),
        ("pre_pin_blob_oid", "0" * 40),
        ("pre_pin_size_bytes", 1),
        ("pre_pin_sha256", "0" * 64),
        ("pin_blob_mode", "100755"),
        ("pin_blob_oid", "0" * 40),
        ("pin_size_bytes", 1),
        ("pin_sha256", "0" * 64),
        ("replacement_policy", "OPEN_WORLD"),
    ],
)
def test_pin_binding_tamper_is_refused(
    tmp_path: Path, field: str, replacement: object
) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["pin_binding"].__setitem__(field, replacement),
    )
    with pytest.raises(BindingError, match="LABEL_ROT"):
        verify(changed)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("producer_commit", "0" * 40),
        ("producer_parent", "0" * 40),
        ("artifact_commit", "0" * 40),
        ("artifact_parent", "0" * 40),
        ("artifact_tree", "0" * 40),
        ("pin_commit", "0" * 40),
        ("pin_parent", "0" * 40),
        ("pin_tree", "0" * 40),
        ("binding_source_commit", "0" * 40),
    ],
)
def test_git_authority_label_tamper_is_refused(
    tmp_path: Path, field: str, replacement: object
) -> None:
    changed = _changed_manifest(
        tmp_path, lambda value: value["git"].__setitem__(field, replacement)
    )
    with pytest.raises(BindingError, match="LABEL_ROT"):
        verify(changed)


@pytest.mark.parametrize(
    ("mutation", "classification"),
    [
        ("count", "LABEL_ROT"),
        ("profile", "LABEL_ROT"),
        ("canary_count", "LABEL_ROT"),
        ("canary_command", "LABEL_ROT"),
        ("disposition", "LABEL_ROT"),
        ("prospective_calls", "LABEL_ROT"),
    ],
)
def test_profile_canary_count_or_disposition_tamper_is_refused(
    tmp_path: Path, mutation: str, classification: str
) -> None:
    def mutate(value: dict[str, object]) -> None:
        incident = value["incident_boundary"]
        if mutation == "count":
            incident["counts"]["attempt_calls"] = 28
        elif mutation == "profile":
            incident["incident_profile_sha256"] = "0" * 64
        elif mutation == "canary_count":
            incident["canary_counter"]["terminal_total"] = 28
        elif mutation == "canary_command":
            incident["canary_counter"]["job_command"]["sha256"] = "0" * 64
        elif mutation == "disposition":
            incident["successor_disposition"]["resume_authorized"] = True
        else:
            incident["prospective_a3_upstream_model_calls"] = 1

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match=classification):
        verify(changed)


@pytest.mark.parametrize("field", ["raw_sha256", "self_sha256", "blob_oid"])
def test_receipt_binding_tamper_is_refused(tmp_path: Path, field: str) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["receipt_binding"].__setitem__(
            field, "0" * (40 if field == "blob_oid" else 64)
        ),
    )
    with pytest.raises(BindingError, match="LABEL_ROT"):
        verify(changed)


@pytest.mark.parametrize("mutation", ["missing", "substitution", "duplicate"])
def test_producer_path_inventory_tamper_is_refused(
    tmp_path: Path, mutation: str
) -> None:
    def mutate(value: dict[str, object]) -> None:
        files = value["producer_authority"]["files"]
        if mutation == "missing":
            files.pop()
        elif mutation == "substitution":
            files[0]["relative_path"] = "prom_search_hswm/foreign.py"
        else:
            files[1]["relative_path"] = files[0]["relative_path"]

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="LABEL_ROT|ORPHANED"):
        verify(changed)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("size_bytes", 1),
        ("sha256", "0" * 64),
        ("blob_mode", "100755"),
        ("blob_oid", "0" * 40),
    ],
)
def test_producer_identity_or_byte_tamper_is_refused(
    tmp_path: Path, field: str, replacement: object
) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["producer_authority"]["files"][0][field] = replacement

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="LABEL_ROT|DIVERGENT"):
        verify(changed)


def test_producer_closure_root_tamper_is_refused(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["producer_authority"].__setitem__(
            "closure_root_sha256", "0" * 64
        ),
    )
    with pytest.raises(BindingError, match="LABEL_ROT"):
        verify(changed)


def test_reverse_pin_ancestry_is_classified_as_divergent() -> None:
    with pytest.raises(BindingError, match="DIVERGENT"):
        _git(
            [
                "merge-base",
                "--is-ancestor",
                EXPECTED_PIN_COMMIT,
                EXPECTED_ARTIFACT_COMMIT,
            ],
            label="reverse pin ancestry must fail",
            classification="DIVERGENT",
        )


@pytest.mark.parametrize(
    ("mutation", "classification"),
    [
        ("missing_target", "ORPHANED"),
        ("missing_binding", "ORPHANED"),
        ("contract", "LABEL_ROT"),
        ("kg_node", "LABEL_ROT"),
        ("symbol", "LABEL_ROT"),
        ("signature", "SIGNATURE_MISMATCHED"),
        ("file_line", "DIVERGENT"),
        ("line_range", "DIVERGENT"),
        ("sha256", "DIVERGENT"),
        ("crate_script", "LABEL_ROT"),
    ],
)
def test_seven_layer_binding_tamper_is_refused(
    tmp_path: Path, mutation: str, classification: str
) -> None:
    def mutate(value: dict[str, object]) -> None:
        if mutation == "missing_target":
            value["required_target_paths"].pop()
        elif mutation == "missing_binding":
            value["bindings"].pop()
        elif mutation == "contract":
            value["bindings"][0]["contract_binding"] = "FOREIGN"
        elif mutation == "kg_node":
            value["bindings"][0]["kg_node"] = "LOCAL_PROPOSED_FOREIGN"
        elif mutation == "symbol":
            value["bindings"][0]["code_symbol"]["name"] = "main"
        elif mutation == "signature":
            value["bindings"][0]["code_symbol"]["signature_sha256"] = "0" * 64
        elif mutation == "file_line":
            value["bindings"][0]["file_line"] = (
                "prom_search_hswm/prom9_f1_prior_exposure.py:1"
            )
        elif mutation == "line_range":
            value["bindings"][0]["line_range"] = "1-1"
        elif mutation == "sha256":
            value["bindings"][0]["sha256"] = "0" * 64
        else:
            value["bindings"][0]["crate_script"] = (
                "python -m pytest -q prom_search_hswm/test_foreign.py"
            )

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match=classification):
        verify(changed)
