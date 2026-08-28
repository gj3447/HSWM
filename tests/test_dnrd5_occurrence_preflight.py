from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from _research.dnrd5 import independent_randomization, occurrence_preflight as preflight, randomization
from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256


def _sha(letter: str) -> str:
    return letter * 64


def _git(letter: str) -> str:
    return letter * 40


def _descriptor(letter: str) -> dict[str, object]:
    return {"media_type": "application/vnd.hswm.dnrd5.fixture+json", "sha256": _sha(letter), "byte_length": 17}


def _source(letter: str) -> dict[str, str]:
    return {"commit": _git(letter), "tree": _git("f" if letter != "f" else "e"), "ci_receipt_sha256": _sha(letter)}


def _source_a() -> dict[str, object]:
    q0 = {"protocol_sha256": _sha("4"), "source": _source("5"), "start_marker_sha256": _sha("6")}
    return {
        "schema_version": preflight.SOURCE_A_SCHEMA,
        "historical_r2": {"commit": preflight.HISTORICAL_R2_COMMIT, "file_sha256": preflight.HISTORICAL_R2_SHA256},
        "exactness_amendment_sha256": preflight.EXACTNESS_AMENDMENT_SHA256,
        "q0": q0,
        "q_closure": {"evidence_root_sha256": _sha("7"), "closure_sha256": _sha("8"), "q0_sha256": canonical_sha256(q0), "terminal": "REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY"},
        "qualification_decisions": {"exactness": "SUPPORTED_NOT_PROVED", "lcb": "SUPPORTED_NOT_PROVED"},
        "source": _source("9"),
        "verifier": {"source": _source("a"), "build_output_sha256": _sha("b"), "import_graph_sha256": _sha("c"), "corpus_sha256": _sha("d"), "actual_byte_schema_sha256": _sha("e")},
        "source_b_preregistration_contract": _descriptor("b"),
        "beacon_receipt_contract": _descriptor("c"),
        "beacon_selection_contract": _descriptor("d"),
        "study_binding_sha256": _sha("f"),
        "block_universe": {"first": "DNRD5-BLOCK-0001", "last": "DNRD5-BLOCK-0300", "count": 300, "ordered_ids_sha256": canonical_sha256(list(randomization.expected_block_ids())), "calls_per_block": 9, "total_calls": 2700, "arms": list(randomization.ARMS)},
        "canonical_json": {"contract_version": "hswm-canonical-json/v1", "corpus_sha256": _sha("0")},
        "plan_descriptor_contract": {"media_type": preflight.PLAN_MEDIA_TYPE, "producer_schema": randomization.SCHEMA_VERSION, "independent_schema": independent_randomization.SCHEMA_VERSION, "encoding": preflight.PLAN_ENCODING, "blob_transport": preflight.PLAN_BLOB_TRANSPORT, "max_blob_bytes": preflight.PLAN_MAX_BLOB_BYTES, "cross_language_status": preflight.PLAN_CROSS_LANGUAGE_STATUS},
        "root_identity_contract": {"schema_version": preflight.ROOT_SCHEMA, "media_type": preflight.ROOT_MEDIA_TYPE, "byte_length": preflight.ROOT_IDENTITY_BYTE_LENGTH},
        "expected_occurrence_descriptors": {"build": _descriptor("1"), "runtime": _descriptor("2"), "no_prior_dispatch": _descriptor("4")},
        "retained_assumptions": list(preflight.FROZEN_RETAINED_ASSUMPTIONS),
        "terminal": preflight.SOURCE_A_SUCCESS,
        "nonclaim": preflight.NONCLAIM,
    }


def _premarker(source_a: dict[str, object]) -> tuple[dict[str, object], bytes, bytes]:
    source_a_sha = canonical_sha256(source_a)
    source_b = {"source": _source("6"), "source_a_binding_sha256": source_a_sha, "preregistration_sha256": _sha("7"), "preregistration_contract": deepcopy(source_a["source_b_preregistration_contract"])}
    future = _sha("8")
    binding = source_a["study_binding_sha256"]
    producer = randomization.canonical_json_bytes(randomization.derive_study_plan(future_randomness_hex=future, study_binding_sha256=binding))
    independent = independent_randomization.canonical_json_bytes(independent_randomization.derive_study_plan(future_randomness_hex=future, study_binding_sha256=binding))
    actual = deepcopy(source_a["expected_occurrence_descriptors"])
    root = preflight._future_root_descriptor(source_a_sha, canonical_sha256(source_b), _sha("9"), future, binding)
    actual["root"] = root
    value = {
        "schema_version": preflight.PREMARKER_SCHEMA,
        "source_a_binding_sha256": source_a_sha,
        "source_b": source_b,
        "beacon": {"receipt_sha256": _sha("9"), "future_randomness_hex": future, "study_binding_sha256": binding, "source_b_sha256": canonical_sha256(source_b), "receipt_contract": deepcopy(source_a["beacon_receipt_contract"]), "selection_contract": deepcopy(source_a["beacon_selection_contract"]), "caller_claimed_selected_after_source_b": True},
        "actual_occurrence_descriptors": actual,
        "producer_plan": {"media_type": preflight.PLAN_MEDIA_TYPE, "sha256": sha256(producer).hexdigest(), "byte_length": len(producer)},
        "independent_plan": {"media_type": preflight.PLAN_MEDIA_TYPE, "sha256": sha256(independent).hexdigest(), "byte_length": len(independent)},
        "terminal": preflight.PREMARKER_SUCCESS,
        "nonclaim": preflight.NONCLAIM,
    }
    return value, producer, independent


def test_valid_source_a_and_premarker_are_non_dispatching() -> None:
    source_a = _source_a()
    a_result = preflight.validate_source_a_instrument_binding(canonical_bytes(source_a))
    assert a_result["terminal"] == preflight.SOURCE_A_STRUCTURAL
    assert a_result["dispatch_authorized"] is False and a_result["dispatch_budget"] == 0
    block, producer, independent = _premarker(source_a)
    result = preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), producer, independent)
    assert result["terminal"] == preflight.PREMARKER_STRUCTURAL
    assert result["dispatch_authorized"] is False and result["dispatch_budget"] == 0
    assert result["nonclaim"] == preflight.NONCLAIM


def test_source_a_canonical_byte_drift_and_extra_field_refuse() -> None:
    source_a = _source_a()
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="canonical-json"):
        preflight.validate_source_a_instrument_binding(b" " + canonical_bytes(source_a))
    source_a["extra"] = True
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="key set"):
        preflight.validate_source_a_instrument_binding(canonical_bytes(source_a))


@pytest.mark.parametrize("mutate, match", [
    (lambda a, b: b.__setitem__("source_a_binding_sha256", _sha("0")), "source_a byte binding"),
    (lambda a, b: b["source_b"].__setitem__("source_a_binding_sha256", _sha("0")), "Source-B does not bind"),
    (lambda a, b: b["beacon"].__setitem__("source_b_sha256", _sha("0")), "chronology descriptor"),
    (lambda a, b: b["actual_occurrence_descriptors"]["runtime"].__setitem__("sha256", _sha("0")), "Source-A-bound"),
])
def test_bindings_chronology_and_descriptor_drift_refuse(mutate, match: str) -> None:
    source_a = _source_a(); block, producer, independent = _premarker(source_a); mutate(source_a, block)
    with pytest.raises(preflight.OccurrencePreflightRefusal, match=match):
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), producer, independent)


def test_plan_mismatch_and_extra_premarker_field_refuse() -> None:
    source_a = _source_a(); block, producer, independent = _premarker(source_a)
    block["producer_plan"]["sha256"] = _sha("0")
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="plan bytes"):
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), producer, independent)


def test_pinned_identity_q_assumption_and_legacy_contract_mutations_refuse() -> None:
    design = Path(__file__).parents[1] / "docs/research/HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md"
    amendment = Path(__file__).parents[1] / "docs/research/HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md"
    assert sha256(design.read_bytes()).hexdigest() == preflight.HISTORICAL_R2_SHA256
    assert sha256(amendment.read_bytes()).hexdigest() == preflight.EXACTNESS_AMENDMENT_SHA256
    assert preflight._future_root_descriptor(_sha("0"), _sha("0"), _sha("0"), _sha("0"), _sha("0"))["byte_length"] == preflight.ROOT_IDENTITY_BYTE_LENGTH
    for mutate, match in (
        (lambda value: value["historical_r2"].__setitem__("commit", _git("0")), "historical R2"),
        (lambda value: value.__setitem__("exactness_amendment_sha256", _sha("0")), "exactness amendment"),
        (lambda value: value["q_closure"].__setitem__("q0_sha256", _sha("0")), "Q0 binding"),
        (lambda value: value.__setitem__("retained_assumptions", value["retained_assumptions"][:-1]), "frozen assumption"),
        (lambda value: value.__setitem__("retained_assumptions", list(reversed(value["retained_assumptions"]))), "frozen assumption"),
        (lambda value: value["plan_descriptor_contract"].__setitem__("encoding", "hswm-canonical-json/v1"), "plan descriptor"),
    ):
        source_a = _source_a(); mutate(source_a)
        with pytest.raises(preflight.OccurrencePreflightRefusal, match=match):
            preflight.validate_source_a_instrument_binding(canonical_bytes(source_a))


def test_root_full_descriptor_phase_extras_and_raw_blob_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    source_a = _source_a(); block, producer, independent = _premarker(source_a)
    for mutate, match in (
        (lambda value: value["actual_occurrence_descriptors"]["root"].__setitem__("media_type", "application/json"), "future-derived"),
        (lambda value: value["actual_occurrence_descriptors"]["root"].__setitem__("byte_length", 0), "future-derived"),
        (lambda value: value["source_b"].__setitem__("preregistration_sha256", _sha("0")), "chronology descriptor"),
        (lambda value: value["beacon"].__setitem__("future_randomness_hex", _sha("0")), "future-derived"),
        (lambda value: value.__setitem__("occurrence_marker", True), "key set"),
        (lambda value: value.__setitem__("dynamic_request_manifest", {}), "key set"),
    ):
        candidate = deepcopy(block); mutate(candidate)
        with pytest.raises(preflight.OccurrencePreflightRefusal, match=match):
            preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(candidate), producer, independent)
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="must be bytes"):
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), "not-bytes", independent)  # type: ignore[arg-type]
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="exceeds frozen maximum"):
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), b"x" * (preflight.PLAN_MAX_BLOB_BYTES + 1), independent)
    def boom(**_: object) -> dict[str, object]:
        raise RuntimeError("unexpected derivation failure")
    monkeypatch.setattr(randomization, "derive_study_plan", boom)
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="plan refused") as refused:
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), producer, independent)
    assert refused.value.terminal == preflight.PREMARKER_REFUSAL
    assert refused.value.dispatch_authorized is False and refused.value.dispatch_budget == 0
    assert refused.value.source_freeze_eligible is False

    source_a["extra"] = True
    with pytest.raises(preflight.OccurrencePreflightRefusal) as source_a_refused:
        preflight.validate_source_a_instrument_binding(canonical_bytes(source_a))
    assert source_a_refused.value.terminal == preflight.SOURCE_A_REFUSAL
    assert source_a_refused.value.dispatch_authorized is False
    assert source_a_refused.value.dispatch_budget == 0
    assert source_a_refused.value.source_freeze_eligible is False


def test_source_b_and_beacon_selection_remain_bound_after_self_consistent_mutation() -> None:
    source_a = _source_a(); block, producer, independent = _premarker(source_a)
    block["source_b"]["preregistration_sha256"] = _sha("0")
    block["beacon"]["source_b_sha256"] = canonical_sha256(block["source_b"])
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="future-derived"):
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), producer, independent)

    block, producer, independent = _premarker(source_a)
    block["beacon"]["selection_contract"]["sha256"] = _sha("0")
    with pytest.raises(preflight.OccurrencePreflightRefusal, match="selection contract"):
        preflight.validate_occurrence_premarker(canonical_bytes(source_a), canonical_bytes(block), producer, independent)
