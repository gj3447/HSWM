from __future__ import annotations

from collections.abc import Mapping
import copy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

import pytest

from prom_search_hswm.hswm_function_network import F1_ARMS, TYPED_ARM, VECTOR_ARM
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V4,
    F1_R8_A3_SUCCESSOR_RUN_ID,
    PriorExposureRefusal,
    SCHEMA as PRIOR_SCHEMA,
    build_f1_r8_successor_exposure_set,
    merge_exposure_boundaries,
)
from prom_search_hswm.prom9_f1_r8_environment import R8_DEPENDENCY_NAMES
from prom_search_hswm.prom9_f1_r8_power import (
    CONFIRMATORY_POOL_OFFSETS,
    DEVELOPMENT_OFFSETS,
    GOLD_SOURCE_SCHEMA,
    POWER_EVIDENCE_SCHEMA,
    POWER_RECEIPT_SCHEMA,
    SELECTION_SCHEMA,
    SUCCESSOR_SELECTION_SCHEMA,
    PowerRefusal,
    _component_key,
    _load_judge_core,
    build_power_receipt,
    build_selection_receipts as _build_selection_receipts,
    derive_development_components,
    evaluator_selected_entries,
    replay_selection_receipt,
    _manifest_source_entity_ids,
    main,
    selected_entries,
    verify_gold_source_receipt,
    verify_selection_receipt,
)
from prom_search_hswm.prom9_f1_r8_source import (
    COMPONENT_SCHEMA,
    build_artifacts,
    source_entity_id,
)


SENTINEL = "PRIVATE_SENTINEL_ANSWER"
REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_RECEIPT_PATH = (
    REPO_ROOT / "receipts/hswm_f1_r8_v8_aborted_exposure.v2.json"
)
_JUDGE_RELATIVE_PATH = Path(
    "FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_lakatotree_judge.py"
)


def _resolve_symposium_root() -> Path:
    candidates = (
        REPO_ROOT.parents[1],
        REPO_ROOT.parent / "SYMPOSIUM",
        REPO_ROOT.parent / "symposium",
    )
    matches: dict[tuple[int, int], Path] = {}
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / ".git").exists() and (
            resolved / _JUDGE_RELATIVE_PATH
        ).is_file():
            info = resolved.stat()
            matches.setdefault((info.st_dev, info.st_ino), resolved)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one SYMPOSIUM checkout for {REPO_ROOT}; "
            f"found {sorted(str(path) for path in matches.values())}"
        )
    return next(iter(matches.values()))


SYMPOSIUM_ROOT = _resolve_symposium_root()
JUDGE_PATH = SYMPOSIUM_ROOT / _JUDGE_RELATIVE_PATH


def build_selection_receipts(**kwargs):
    kwargs.setdefault("forensic_legacy_replay", True)
    return _build_selection_receipts(**kwargs)


def _incident() -> dict[str, object]:
    return json.loads(INCIDENT_RECEIPT_PATH.read_text(encoding="utf-8"))


def _successor_wrapper(
    monkeypatch: pytest.MonkeyPatch, *, distinct_component: bool = False
) -> tuple[dict[str, object], str]:
    import prom_search_hswm.prom9_f1_prior_exposure as prior_exposure
    import prom_search_hswm.prom9_f1_r8_power as power

    historical = _incident()
    synthetic = copy.deepcopy(historical)
    synthetic_sha = "a" * 64
    synthetic["schema_version"] = ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V4
    synthetic["aborted_attempt_exposure_receipt_sha256"] = synthetic_sha
    synthetic["counts"] = {
        **synthetic["counts"],
        "attempt_calls": 27,
        "spool_complete_calls": 26,
    }
    synthetic["profile_evidence"] = {
        "canary_counter_receipt": {
            "historical_baseline": 1,
            "terminal_total": 27,
            "incident_delta": 26,
        }
    }
    target_component = _INCIDENT_COMPONENT_ID
    if distinct_component:
        row = _row(21, development=True)
        titles = row["context"]["title"]
        sentences = row["context"]["sentences"]
        sources = sorted(
            source_entity_id(str(title), sentence)
            for title, sentence in zip(titles, sentences, strict=True)
        )
        target_component = canonical_sha256(
            {
                "schema_version": COMPONENT_SCHEMA,
                "source_entity_ids": sources,
            }
        )
        metadata = {
            "item_id": str(row["id"]),
            "dataset_row_index": DEVELOPMENT_OFFSETS[0] + 21,
            "source_entity_ids": sources,
            "component_id": target_component,
        }
        for collection in ("call_observations", "item_run_observations"):
            observations = synthetic.get(collection)
            assert isinstance(observations, list)
            for observation in observations:
                assert isinstance(observation, dict)
                observation.update(metadata)
        aggregate = synthetic["aggregate"]
        assert isinstance(aggregate, dict)
        aggregate.update(
            {
                "prior_item_ids": [metadata["item_id"]],
                "prior_source_entity_ids": sources,
                "prior_component_ids": [target_component],
                "item_root_sha256": canonical_sha256([metadata["item_id"]]),
                "source_entity_root_sha256": canonical_sha256(sources),
                "component_root_sha256": canonical_sha256([target_component]),
            }
        )
    original_verify = prior_exposure.verify_aborted_attempt_exposure_receipt

    def verify_member(value: Mapping[str, object]) -> str:
        if value.get("aborted_attempt_exposure_receipt_sha256") == synthetic_sha:
            return synthetic_sha
        return original_verify(value)

    def verify_exact(value: Mapping[str, object]) -> str:
        if value.get("aborted_attempt_exposure_receipt_sha256") != synthetic_sha:
            raise PriorExposureRefusal("wrong synthetic a2 member")
        return synthetic_sha

    monkeypatch.setattr(
        prior_exposure, "verify_aborted_attempt_exposure_receipt", verify_member
    )
    monkeypatch.setattr(
        prior_exposure, "verify_f1_r8_successor_incident", verify_exact
    )
    monkeypatch.setattr(
        power, "verify_aborted_attempt_exposure_receipt", verify_member
    )
    return build_f1_r8_successor_exposure_set([historical, synthetic]), target_component


def _accepted_incident_call(incident: Mapping[str, object]) -> dict[str, object]:
    observations = incident.get("call_observations")
    accepted = [
        call
        for call in observations
        if isinstance(call, dict)
        and call.get("raw_attempt_state") == "ACCEPTED"
        and call.get("spool_snapshot_state") == "COMPLETE"
    ] if isinstance(observations, list) else []
    assert len(accepted) == 1
    return accepted[0]


_INCIDENT_AGGREGATE = _incident()["aggregate"]
assert isinstance(_INCIDENT_AGGREGATE, dict)
_INCIDENT_ITEM_ID = str(_INCIDENT_AGGREGATE["prior_item_ids"][0])
_INCIDENT_COMPONENT_ID = str(_INCIDENT_AGGREGATE["prior_component_ids"][0])
_INCIDENT_SOURCE_ENTITY_IDS = tuple(
    str(value) for value in _INCIDENT_AGGREGATE["prior_source_entity_ids"]
)
_INCIDENT_SELECTION_KEY = _component_key(
    _INCIDENT_COMPONENT_ID, "development_power"
)


@lru_cache(maxsize=None)
def _ordinary_development_title(label: str) -> str:
    """Give ordinary synthetic components ranks after the incident component."""

    for nonce in range(1000):
        title = f"{label}-nonce-{nonce}"
        sentences = [f"Sentence {title}."]
        entity_id = source_entity_id(title, sentences)
        component_id = canonical_sha256(
            {
                "schema_version": COMPONENT_SCHEMA,
                "source_entity_ids": [entity_id],
            }
        )
        if _component_key(component_id, "development_power") > (
            _INCIDENT_SELECTION_KEY
        ):
            return title
    raise AssertionError("could not synthesize a post-incident component rank")


@pytest.fixture(autouse=True)
def _synthetic_incident_source_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import prom_search_hswm.prom9_f1_prior_exposure as prior_exposure
    import prom_search_hswm.prom9_f1_r8_source as source

    original = source.source_entity_id
    mapped = {
        f"incident-source-{index}": entity_id
        for index, entity_id in enumerate(_INCIDENT_SOURCE_ENTITY_IDS)
    }

    def synthetic_source_entity_id(title: str, sentences) -> str:
        if title in mapped:
            return mapped[title]
        return original(title, sentences)

    monkeypatch.setattr(source, "source_entity_id", synthetic_source_entity_id)
    monkeypatch.setattr(
        prior_exposure, "source_entity_id", synthetic_source_entity_id
    )


def _prior() -> dict[str, object]:
    items = sorted(f"prior-item-{index:03d}" for index in range(104))
    entities = sorted(
        canonical_sha256({"prior-entity": index}) for index in range(104)
    )
    components = sorted(
        canonical_sha256({"prior-component": index}) for index in range(104)
    )
    unsigned = {
        "schema_version": PRIOR_SCHEMA,
        "aggregate": {
            "prior_item_ids": items,
            "prior_source_entity_ids": entities,
            "prior_component_ids": components,
            "item_root_sha256": canonical_sha256(items),
            "source_entity_root_sha256": canonical_sha256(entities),
            "component_root_sha256": canonical_sha256(components),
        },
        "complete": True,
    }
    return {**unsigned, "prior_exposure_receipt_sha256": canonical_sha256(unsigned)}


def _allow_resigned_incident_for_preimage_test(
    monkeypatch: pytest.MonkeyPatch,
    incident: dict[str, object],
) -> str:
    """Bypass only the fixed incident identity to exercise candidate replay."""

    import prom_search_hswm.prom9_f1_r8_power as power

    unsigned = dict(incident)
    unsigned.pop("aborted_attempt_exposure_receipt_sha256")
    incident_sha = canonical_sha256(unsigned)
    incident["aborted_attempt_exposure_receipt_sha256"] = incident_sha
    monkeypatch.setattr(
        power,
        "verify_aborted_attempt_exposure_receipt",
        lambda _value: incident_sha,
    )

    def preverified_merge(prior, supplied_incident):
        assert supplied_incident is incident
        prior_aggregate = prior["aggregate"]
        incident_aggregate = supplied_incident["aggregate"]

        def union(key: str) -> list[str]:
            return sorted(
                set(prior_aggregate[key]).union(incident_aggregate[key])
            )

        item_ids = union("prior_item_ids")
        source_ids = union("prior_source_entity_ids")
        component_ids = union("prior_component_ids")
        return {
            "prior_exposure_receipt_sha256": prior[
                "prior_exposure_receipt_sha256"
            ],
            "aborted_attempt_exposure_receipt_sha256": incident_sha,
            "item_ids": item_ids,
            "source_entity_ids": source_ids,
            "component_ids": component_ids,
            "item_root_sha256": canonical_sha256(item_ids),
            "source_entity_root_sha256": canonical_sha256(source_ids),
            "component_root_sha256": canonical_sha256(component_ids),
        }

    monkeypatch.setattr(power, "merge_exposure_boundaries", preverified_merge)
    import prom_search_hswm.prom9_f1_prior_exposure as prior_exposure

    monkeypatch.setattr(
        prior_exposure,
        "verify_aborted_attempt_exposure_receipt",
        lambda _value: incident_sha,
    )
    return incident_sha


def _prior_with_component_dimension(
    component: Mapping[str, object], dimension: str
) -> dict[str, object]:
    receipt = _prior()
    aggregate = receipt["aggregate"]
    assert isinstance(aggregate, dict)
    key_by_dimension = {
        "item_ids": "prior_item_ids",
        "source_entity_ids": "prior_source_entity_ids",
        "component_ids": "prior_component_ids",
    }
    root_by_dimension = {
        "item_ids": "item_root_sha256",
        "source_entity_ids": "source_entity_root_sha256",
        "component_ids": "component_root_sha256",
    }
    aggregate_key = key_by_dimension[dimension]
    component_values = (
        [component["component_id"]]
        if dimension == "component_ids"
        else component[dimension]
    )
    values = sorted(
        set(str(value) for value in aggregate[aggregate_key]).union(
            str(value) for value in component_values
        )
    )
    aggregate[aggregate_key] = values
    aggregate[root_by_dimension[dimension]] = canonical_sha256(values)
    unsigned = dict(receipt)
    unsigned.pop("prior_exposure_receipt_sha256")
    receipt["prior_exposure_receipt_sha256"] = canonical_sha256(unsigned)
    return receipt


def _row(
    index: int, *, development: bool, answer: str | None = None
) -> dict[str, object]:
    if development and index == 20:
        item_id = _INCIDENT_ITEM_ID
        titles = [
            f"incident-source-{source_index}"
            for source_index in range(len(_INCIDENT_SOURCE_ENTITY_IDS))
        ]
    elif development and index < 20:
        item_id = f"dev-item-{index:04d}"
        titles = [
            _ordinary_development_title(
                f"development-pair-{index // 2:03d}"
            )
        ]
    elif development and 21 <= index < 47:
        item_id = f"dev-item-{index:04d}"
        titles = [
            _ordinary_development_title(
                f"development-pair-{10 + (index - 21) // 2:03d}"
            )
        ]
    elif development:
        item_id = f"dev-item-{index:04d}"
        titles = [
            _ordinary_development_title(f"development-{index:04d}")
        ]
    else:
        item_id = f"r8-item-{index:04d}"
        titles = [f"confirmatory-{index:04d}"]
    return {
        "id": item_id,
        "question": f"Question {index}?",
        "answer": answer if answer is not None else f"PRIVATE_{index}",
        "context": {
            "title": titles,
            "sentences": [[f"Sentence {title}."] for title in titles],
        },
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _pages(tmp_path: Path, *, answer: str | None = None):
    development: dict[int, Path] = {}
    for page_index, offset in enumerate(DEVELOPMENT_OFFSETS):
        rows = [
            _row(page_index * 100 + index, development=True, answer=answer)
            for index in range(100)
        ]
        path = tmp_path / f"dev-{offset}.json"
        path.write_text(json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8")
        path.chmod(0o600)
        development[offset] = path
    confirmatory: dict[int, Path] = {}
    for page_index, offset in enumerate(CONFIRMATORY_POOL_OFFSETS):
        rows = [
            _row(page_index * 100 + index, development=False, answer=answer)
            for index in range(100)
        ]
        path = tmp_path / f"r8-{offset}.json"
        path.write_text(json.dumps({"rows": [{"row": row} for row in rows]}), encoding="utf-8")
        path.chmod(0o600)
        confirmatory[offset] = path
    return development, confirmatory


def _envelope() -> dict[str, object]:
    return {
        "per_call_input_caps": {"1": 275, "2": 1691, "3": 2359},
        "per_call_output_caps": {"1": 768, "2": 1536, "3": 768},
    }


def test_public_selection_v3_and_private_gold_source_are_physically_separate(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    selection, gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert selection["schema_version"] == SELECTION_SCHEMA
    assert gold_source["schema_version"] == GOLD_SOURCE_SCHEMA
    assert verify_selection_receipt(selection) == selection["selection_receipt_sha256"]
    assert replay_selection_receipt(
        selection,
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
    ) == selection["selection_receipt_sha256"]
    assert verify_gold_source_receipt(gold_source, selection) == gold_source[
        "gold_source_receipt_sha256"
    ]
    assert SENTINEL not in canonical_json(selection)
    assert SENTINEL in canonical_json(gold_source)
    public_rows = selected_entries(selection, "development")
    full_rows = evaluator_selected_entries(selection, gold_source, "development")
    assert all(set(entry) == {"dataset_row_index", "row"} for entry in public_rows)
    assert all(set(entry["row"]) == {"id", "question", "context", "type"} for entry in public_rows)
    assert all("answer" in entry["row"] for entry in full_rows)
    assert len(selection["development"]["component_schedule"]) == 48
    assert len(selection["development"]["item_ids"]) == 55
    assert len(selection["confirmatory"]["item_ids"]) == 100


def test_answer_only_mutation_leaves_public_selection_byte_identical(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path, answer="FIRST_PRIVATE")
    first_selection, first_gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    for path in development.values():
        page = json.loads(path.read_text(encoding="utf-8"))
        for wrapped in page["rows"]:
            wrapped["row"]["answer"] = "MUTATED_PRIVATE"
        path.write_text(json.dumps(page), encoding="utf-8")
        path.chmod(0o600)
    second_selection, second_gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert first_selection == second_selection
    assert first_gold_source != second_gold_source
    assert first_gold_source["gold_source_receipt_sha256"] != second_gold_source[
        "gold_source_receipt_sha256"
    ]


def test_incident_component_is_excluded_and_replacement_is_selected(
    tmp_path: Path,
) -> None:
    import prom_search_hswm.prom9_f1_r8_power as power

    development, confirmatory = _pages(tmp_path)
    incident = _incident()
    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=incident,
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    projections: list[dict[str, object]] = []
    for page in selection["source_pages"]:
        if page["purpose"] == "development":
            _receipt, rows, _entries = power._page_input_redacted(
                page["redacted_rows"], page["offset"]
            )
            projections.extend(rows)
    projected_items = [dict(row) for row in projections]
    components = power._assign_components(projected_items)
    ordered = sorted(
        components,
        key=lambda component: _component_key(
            str(component["component_id"]), "development_power"
        ),
    )
    incident_aggregate = incident["aggregate"]
    accepted_call = _accepted_incident_call(incident)
    assert [
        item["dataset_row_index"]
        for item in projected_items
        if item["item_id"] == accepted_call["item_id"]
        and item["component_id"] == accepted_call["component_id"]
        and item["source_entity_ids"] == accepted_call["source_entity_ids"]
    ] == [accepted_call["dataset_row_index"]]
    assert ordered[0] == {
        "component_id": incident_aggregate["prior_component_ids"][0],
        "item_ids": incident_aggregate["prior_item_ids"],
        "source_entity_ids": incident_aggregate["prior_source_entity_ids"],
    }
    selected_components = {
        str(component["component_id"])
        for component in selection["development"]["component_schedule"]
    }
    expected_components = {
        str(component["component_id"]) for component in ordered[1:49]
    }
    assert selected_components == expected_components
    assert str(ordered[48]["component_id"]) in selected_components
    assert not selected_components & set(
        incident_aggregate["prior_component_ids"]
    )
    assert not set(selection["development"]["item_ids"]) & set(
        incident_aggregate["prior_item_ids"]
    )
    assert not set(selection["development"]["source_entity_ids"]) & set(
        incident_aggregate["prior_source_entity_ids"]
    )
    assert selection["aborted_attempt_exposure_receipt_sha256"] == incident[
        "aborted_attempt_exposure_receipt_sha256"
    ]
    assert len(selection["development"]["component_schedule"]) == 48
    assert len(selection["development"]["item_ids"]) == 55
    assert len(selection["confirmatory"]["item_ids"]) == 100


def test_missing_tampered_and_resigned_incident_are_refused(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path)
    with pytest.raises(TypeError, match="aborted_attempt_exposure_receipt"):
        build_selection_receipts(
            prior_receipt=_prior(),
            development_pages=development,
            confirmatory_pages=confirmatory,
        )

    tampered = _incident()
    tampered["termination"]["exit_code"] = 134
    with pytest.raises(PriorExposureRefusal, match="self-hash"):
        build_selection_receipts(
            prior_receipt=_prior(),
            aborted_attempt_exposure_receipt=tampered,
            development_pages=development,
            confirmatory_pages=confirmatory,
        )

    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    resigned = _incident()
    resigned["run_identity"]["run_id"] = "re-signed-wrong-attempt"
    unsigned = dict(resigned)
    unsigned.pop("aborted_attempt_exposure_receipt_sha256")
    resigned["aborted_attempt_exposure_receipt_sha256"] = canonical_sha256(
        unsigned
    )
    with pytest.raises(PriorExposureRefusal, match="call observation drifted"):
        replay_selection_receipt(
            selection,
            prior_receipt=_prior(),
            aborted_attempt_exposure_receipt=resigned,
        )


def test_default_selection_api_refuses_singular_incident(
    tmp_path: Path,
) -> None:
    development, confirmatory = _pages(tmp_path)
    with pytest.raises(PriorExposureRefusal, match="successor exposure-set"):
        _build_selection_receipts(
            prior_receipt=_prior(),
            aborted_attempt_exposure_receipt=_incident(),
            development_pages=development,
            confirmatory_pages=confirmatory,
        )


def test_successor_exposure_wrapper_reaches_selection_preimage_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper, second_component = _successor_wrapper(
        monkeypatch, distinct_component=True
    )
    development, confirmatory = _pages(tmp_path)
    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=wrapper,
        development_pages=development,
        confirmatory_pages=confirmatory,
        forensic_legacy_replay=False,
    )
    assert selection["aborted_attempt_exposure_receipt_sha256"] == wrapper[
        "aborted_attempt_exposure_receipt_sha256"
    ]
    assert selection["schema_version"] == SUCCESSOR_SELECTION_SCHEMA
    selected_components = {
        row["component_id"] for row in selection["development"]["component_schedule"]
    }
    assert second_component != _INCIDENT_COMPONENT_ID
    assert _INCIDENT_COMPONENT_ID not in selected_components
    assert second_component not in selected_components
    assert len(selection["development"]["item_ids"]) == sum(
        int(row["cluster_size"])
        for row in selection["development"]["component_schedule"]
    )
    assert replay_selection_receipt(
        selection,
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=wrapper,
    ) == selection["selection_receipt_sha256"]


def test_incident_must_reproduce_one_candidate_component_even_if_preverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    development, confirmatory = _pages(tmp_path)
    prior = _prior()
    wrong = _incident()
    wrong_item = "re-signed-but-not-in-candidate-pages"
    _accepted_incident_call(wrong)["item_id"] = wrong_item
    wrong["aggregate"]["prior_item_ids"] = [wrong_item]
    wrong["aggregate"]["item_root_sha256"] = canonical_sha256([wrong_item])
    _allow_resigned_incident_for_preimage_test(monkeypatch, wrong)
    with pytest.raises(PowerRefusal, match="cumulative aggregate"):
        build_selection_receipts(
            prior_receipt=prior,
            aborted_attempt_exposure_receipt=wrong,
            development_pages=development,
            confirmatory_pages=confirmatory,
        )


def test_resigned_incident_row_index_must_match_candidate_preimage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    development, confirmatory = _pages(tmp_path)
    wrong = _incident()
    accepted_call = _accepted_incident_call(wrong)
    assert accepted_call["dataset_row_index"] == 124
    accepted_call["dataset_row_index"] = 125
    _allow_resigned_incident_for_preimage_test(monkeypatch, wrong)

    with pytest.raises(PowerRefusal, match="item metadata conflicts"):
        build_selection_receipts(
            prior_receipt=_prior(),
            aborted_attempt_exposure_receipt=wrong,
            development_pages=development,
            confirmatory_pages=confirmatory,
        )


@pytest.mark.parametrize(
    ("cohort", "dimension"),
    [
        (cohort, dimension)
        for cohort in ("development", "confirmatory")
        for dimension in ("item_ids", "source_entity_ids", "component_ids")
    ],
)
def test_all_identity_dimensions_filter_development_and_confirmatory_components(
    tmp_path: Path,
    cohort: str,
    dimension: str,
) -> None:
    development, confirmatory = _pages(tmp_path)
    baseline, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    target = baseline[cohort]["component_schedule"][0]
    reselection, _replacement_gold_source = build_selection_receipts(
        prior_receipt=_prior_with_component_dimension(target, dimension),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    replacement_components = {
        str(component["component_id"])
        for component in reselection[cohort]["component_schedule"]
    }
    assert target["component_id"] not in replacement_components
    assert not set(target["item_ids"]) & set(reselection[cohort]["item_ids"])
    assert not set(target["source_entity_ids"]) & set(
        reselection[cohort]["source_entity_ids"]
    )
    expected_count = 48 if cohort == "development" else 100
    assert len(reselection[cohort]["component_schedule"]) == expected_count


def test_select_cli_requires_public_incident_and_separate_gold_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    successor, _second_component = _successor_wrapper(monkeypatch)
    prior_path = tmp_path / "prior.json"
    prior_path.write_text(json.dumps(_prior()), encoding="utf-8")
    prior_path.chmod(0o600)
    incident_path = tmp_path / "incident.json"
    incident_path.write_text(json.dumps(successor), encoding="utf-8")
    incident_path.chmod(0o600)
    public_path = tmp_path / "selection.json"
    gold_source_path = tmp_path / "gold-source.json"
    command = [
        "select",
        "--prior-exposure-receipt", str(prior_path),
        "--aborted-attempt-exposure-receipt", str(incident_path),
    ]
    for offset, path in development.items():
        command.extend(["--development-page", f"{offset}:{path}"])
    for offset, path in confirmatory.items():
        command.extend(["--confirmatory-page", f"{offset}:{path}"])
    command.extend(
        ["--output", str(public_path), "--gold-source-output", str(gold_source_path)]
    )
    missing_incident = list(command)
    incident_option = missing_incident.index(
        "--aborted-attempt-exposure-receipt"
    )
    del missing_incident[incident_option : incident_option + 2]
    with pytest.raises(SystemExit):
        main(missing_incident)
    assert "--aborted-attempt-exposure-receipt" in capsys.readouterr().err

    assert os.stat(incident_path).st_mode & 0o077 == 0
    assert main(command) == 0
    captured = capsys.readouterr()
    assert SENTINEL not in captured.out + captured.err
    assert SENTINEL not in public_path.read_text(encoding="utf-8")
    assert SENTINEL in gold_source_path.read_text(encoding="utf-8")
    assert os.stat(public_path).st_mode & 0o777 == 0o600
    assert os.stat(gold_source_path).st_mode & 0o777 == 0o600


def test_rehashed_block_swap_is_refused_by_public_selector_replay(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    tampered = copy.deepcopy(selection)
    schedule = tampered["development"]["component_schedule"]
    schedule[0]["seed_block"], schedule[5]["seed_block"] = (
        schedule[5]["seed_block"], schedule[0]["seed_block"]
    )
    unsigned = dict(tampered)
    unsigned.pop("selection_receipt_sha256")
    tampered["selection_receipt_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(PowerRefusal, match="block assignment"):
        replay_selection_receipt(
            tampered,
            prior_receipt=_prior(),
            aborted_attempt_exposure_receipt=_incident(),
        )


def test_terminal_components_use_evaluator_only_gold_after_the_run(tmp_path: Path) -> None:
    development, confirmatory = _pages(tmp_path)
    selection, gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=_incident(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    public_rows = selected_entries(selection, "development")
    full_rows = evaluator_selected_entries(selection, gold_source, "development")
    artifacts = build_artifacts(
        public_rows,
        full_rows,
        public_selection_receipt_sha256=selection["selection_receipt_sha256"],
        gold_source_receipt_sha256=gold_source["gold_source_receipt_sha256"],
        dataset="dataset",
        config="default",
        split="validation",
        run_id="f1-2wiki-r8-development-test",
        mode="development",
        model="model",
        model_revision="revision",
        token_envelope=_envelope(),
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256=None,
    )
    accepted = {
        row["item_id"]: row["accepted_answers"][0]
        for row in artifacts["gold"]["items"]
    }
    item_runs = []
    for index, item in enumerate(artifacts["manifest"]["items"]):
        for arm in F1_ARMS:
            correct = arm == TYPED_ARM or (arm == VECTOR_ARM and index % 3 == 0)
            item_runs.append(
                {
                    "item_id": item["item_id"],
                    "arm_id": arm,
                    "answer": {
                        "answer": accepted[item["item_id"]] if correct else "incorrect",
                        "abstain": False,
                    },
                }
            )
    components = derive_development_components(
        manifest=artifacts["manifest"],
        suite={
            "mode": "development",
            "run_id": artifacts["manifest"]["run_id"],
            "item_runs": item_runs,
        },
        gold=artifacts["gold"],
        selection_receipt=selection,
    )
    assert len(components) == 48
    assert {component["seed_block"] for component in components} == set(range(12))
    assert any(component["contrasts"][VECTOR_ARM] < 1.0 for component in components)


def test_power_builder_success_rederives_full_embedded_development_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import prom_search_hswm.prom9_f1_r8_power as power
    import prom_search_hswm.prom9_f1_r8_runner as runner
    import prom_search_hswm.prom_f1_function_network as function_network

    development, confirmatory = _pages(tmp_path)
    prior = _prior()
    incident, _second_component = _successor_wrapper(monkeypatch)
    selection, gold_source = build_selection_receipts(
        prior_receipt=prior,
        aborted_attempt_exposure_receipt=incident,
        development_pages=development,
        confirmatory_pages=confirmatory,
        forensic_legacy_replay=False,
    )
    public_rows = selected_entries(selection, "development")
    full_rows = evaluator_selected_entries(selection, gold_source, "development")
    artifacts = build_artifacts(
        public_rows,
        full_rows,
        public_selection_receipt_sha256=selection["selection_receipt_sha256"],
        gold_source_receipt_sha256=gold_source["gold_source_receipt_sha256"],
        dataset="dataset",
        config="default",
        split="validation",
        run_id=F1_R8_A3_SUCCESSOR_RUN_ID,
        mode="development",
        model="measured-model",
        model_revision="f" * 40,
        token_envelope=_envelope(),
        sealed_at="2026-07-29T00:00:00Z",
        preregistration_artifact_sha256=None,
    )
    manifest = artifacts["manifest"]
    gold = artifacts["gold"]
    source = artifacts["source_receipt"]
    evaluator = artifacts["evaluator_receipt"]
    accepted = {
        row["item_id"]: row["accepted_answers"][0] for row in gold["items"]
    }
    item_runs = [
        {
            "item_id": item["item_id"],
            "arm_id": arm,
            "answer": {
                "answer": accepted[item["item_id"]]
                if arm == TYPED_ARM
                else "incorrect",
                "abstain": False,
            },
        }
        for item in manifest["items"]
        for arm in F1_ARMS
    ]

    judge_path = JUDGE_PATH
    judge_file_sha = hashlib.sha256(judge_path.read_bytes()).hexdigest()
    judge_semantic_sha = str(_load_judge_core(judge_path).judge_core_sha256(judge_path))
    environment_sha = "a" * 64
    dependency_sha = "b" * 64
    compatibility_root = "c" * 64
    bundle_sha = "d" * 64
    genesis_unsigned = {"schema_version": "test-genesis/v1"}
    genesis = {
        **genesis_unsigned,
        "genesis_sha256": canonical_sha256(genesis_unsigned),
    }
    deployment_sha = "e" * 64
    dependency_files = {
        name: {"sha256": canonical_sha256({"dependency": name})}
        for name in R8_DEPENDENCY_NAMES
    }
    dependency_files["judge_core"] = {"sha256": judge_file_sha}
    exposure_union = merge_exposure_boundaries(prior, incident)
    environment = {
        "labels": {
            "spool_endpoint": "https://spool.invalid",
            "model_upstream_endpoint": (
                "https://inference.invalid/v1/chat/completions"
            ),
            "model_deployment_receipt_sha256": deployment_sha,
            "model": manifest["model"],
            "model_revision": manifest["model_revision"],
            "run_id": manifest["run_id"],
            "hswm_commit": "1" * 40,
            "symposium_commit": "2" * 40,
        }
    }
    dependencies = {"files": dependency_files}
    environment_bundle = {
        "environment_receipt": environment,
        "dependency_receipt": dependencies,
        "bundle_sha256": bundle_sha,
    }
    lock_unsigned = {
        "run_id": F1_R8_A3_SUCCESSOR_RUN_ID,
        "manifest_sha256": canonical_sha256(manifest),
        "selection_receipt_sha256": selection["selection_receipt_sha256"],
        "prior_exposure_receipt_sha256": prior[
            "prior_exposure_receipt_sha256"
        ],
        "aborted_attempt_exposure_receipt_sha256": incident[
            "aborted_attempt_exposure_receipt_sha256"
        ],
        "public_source_receipt_sha256": source["source_receipt_sha256"],
        "gold_source_receipt_sha256": gold_source[
            "gold_source_receipt_sha256"
        ],
        "gold_sha256": canonical_sha256(gold),
        "evaluator_receipt_sha256": evaluator["receipt_sha256"],
        "db_genesis_receipt_sha256": genesis["genesis_sha256"],
        "environment_receipt_sha256": environment_sha,
        "dependency_receipt_sha256": dependency_sha,
        "environment_dependency_compatibility_root_sha256": compatibility_root,
        "environment_dependency_bundle_sha256": bundle_sha,
        "judge_core_sha256": judge_semantic_sha,
        "judge_core_file_sha256": judge_file_sha,
        "hswm_commit": "1" * 40,
        "model": manifest["model"],
        "model_revision": manifest["model_revision"],
        "upstream_endpoint": environment["labels"]["model_upstream_endpoint"],
        "deployment_receipt_sha256": deployment_sha,
        "deployment_id": f"hswm:model_deployment:v2:{deployment_sha}",
        "served_model": manifest["model"],
        "forbidden_prior_item_ids": exposure_union["item_ids"],
        "forbidden_prior_source_entity_ids": exposure_union[
            "source_entity_ids"
        ],
        "forbidden_prior_component_ids": exposure_union["component_ids"],
        "execution_policy": {"endpoint": "https://spool.invalid", "max_workers": 1},
    }
    execution_lock = {
        **lock_unsigned,
        "lock_sha256": canonical_sha256(lock_unsigned),
    }
    suite = {
        "mode": "development",
        "run_id": manifest["run_id"],
        "manifest_sha256": canonical_sha256(manifest),
        "measurement_lock_sha256": execution_lock["lock_sha256"],
        "item_runs": item_runs,
        "token_parity": {"all_within_tolerance": True},
        "transport_audit": {
            "call_count": len(item_runs) * 3,
            "item_run_count": len(item_runs),
            "status_counts": {"ACCEPTED": len(item_runs) * 3},
        },
        "max_workers": 1,
        "gold_opened": False,
        "scientific_verdict_emitted": False,
        "upstream_endpoint": lock_unsigned["upstream_endpoint"],
        "deployment_receipt_sha256": deployment_sha,
        "deployment_id": lock_unsigned["deployment_id"],
        "served_model": manifest["model"],
        "model_revision": manifest["model_revision"],
    }

    monkeypatch.setattr(
        runner,
        "verify_suite_v3_without_gold",
        lambda _suite: canonical_sha256({"terminal-suite": True}),
    )
    monkeypatch.setattr(function_network, "_verify_token_blocks", lambda *_args: None)
    monkeypatch.setattr(power, "verify_preimage_bundle", lambda *_args, **_kwargs: compatibility_root)
    monkeypatch.setattr(power, "verify_environment_receipt", lambda *_args, **_kwargs: environment_sha)
    monkeypatch.setattr(power, "verify_dependency_receipt", lambda *_args, **_kwargs: dependency_sha)

    receipt = build_power_receipt(
        manifest=manifest,
        execution_lock=execution_lock,
        public_source_receipt=source,
        selection_receipt=selection,
        gold_source_receipt=gold_source,
        prior_exposure_receipt=prior,
        aborted_attempt_exposure_receipt=incident,
        suite=suite,
        evaluator_receipt=evaluator,
        gold=gold,
        db_genesis_receipt=genesis,
        environment_dependency_bundle=environment_bundle,
        judge_core_path=judge_path,
    )
    expected_components = derive_development_components(
        manifest=manifest,
        suite=suite,
        gold=gold,
        selection_receipt=selection,
    )
    assert receipt["analysis_input"]["development_components"] == expected_components
    assert receipt["schema_version"] == POWER_RECEIPT_SCHEMA
    assert receipt["development_evidence"]["schema_version"] == POWER_EVIDENCE_SCHEMA
    assert receipt["development_evidence"][
        "aborted_attempt_exposure_receipt"
    ] == incident
    assert set(receipt["development_evidence"]["artifact_receipts"]) == {
        "selection_receipt_sha256",
        "prior_exposure_receipt_sha256",
        "aborted_attempt_exposure_receipt_sha256",
        "execution_lock_sha256",
        "public_source_receipt_sha256",
        "gold_source_receipt_sha256",
        "suite_receipt_sha256",
        "evaluator_receipt_sha256",
        "db_genesis_receipt_sha256",
        "gold_sha256",
        "environment_receipt_sha256",
        "dependency_receipt_sha256",
        "environment_dependency_compatibility_root_sha256",
        "environment_dependency_bundle_sha256",
    }


def test_manifest_source_entities_follow_source_receipt_set_semantics() -> None:
    entity = "e" * 64
    assert _manifest_source_entity_ids(
        {
            "candidates": [
                {"source_entity_id": entity},
                {"source_entity_id": entity},
            ]
        }
    ) == [entity]
