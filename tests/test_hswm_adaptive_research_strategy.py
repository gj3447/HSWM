from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import build_hswm_adaptive_research_strategy_ontology as builder
from scripts import upsert_hswm_adaptive_research_strategy as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH


def _data() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def _relation_keys(data: dict) -> set[tuple[str, str, str]]:
    return {
        (row["from_uid"], row["type"], row["to_uid"])
        for row in data["relations"]
    }


def test_projection_is_deterministic_source_bound_and_valid() -> None:
    data = _data()

    publisher.validate_data(data, ROOT)

    assert data == builder.build_data()
    assert data["expected_counts"] == publisher.EXPECTED_COUNTS
    assert builder.canonical_sha(data) == publisher.EXPECTED_PROJECTION_SHA256
    assert sha256(ONTOLOGY_PATH.read_bytes()).hexdigest() == publisher.EXPECTED_FILE_SHA256
    assert data["status"] == (
        "TARGET_IDENTITY_FIXED_METHODS_ADAPTIVE_SCIENTIFICALLY_UNJUDGED"
    )


def test_exact_user_source_is_preserved_and_not_promoted_to_evidence() -> None:
    source = ROOT / builder.SOURCE_PATH
    source_digest = "3170c91d233f496185602754b7dd5a10ba2fa6b423e1bc43d77dc0ae996d75cd"
    assert sha256(source.read_bytes()).hexdigest() == source_digest

    data = _data()
    commitment = next(
        row for row in data["nodes"] if row["uid"] == builder.COMMITMENT_UID
    )
    assert commitment["properties"]["authority_class"] == "USER_PRIMARY"
    assert commitment["properties"]["source_sha256"] == source_digest
    assert "not evidence" in commitment["properties"]["claim_boundary"]
    assert all(row["type"] != "EVIDENCE_FOR" for row in data["relations"])


def test_target_and_fcl_provenance_do_not_extend_the_new_user_source() -> None:
    data = _data()
    bindings = {row["path"]: row["sha256"] for row in data["artifact_bindings"]}
    expected_bindings = {
        builder.CONSTITUTION_PATH.as_posix(): (
            "cf43bc034a64d8db54b3444b7eba9ea02c8c5d9e252e14f157637401c68c3373"
        ),
        builder.FRACTAL_USER_SOURCE_PATH.as_posix(): (
            "c453034f1d13c2bd7498a2e6b488a3bf07af74a3a7ee0f4d1ba7d4c74b2e685e"
        ),
        builder.FRACTAL_CANON_PATH.as_posix(): (
            "d7dc6d86dc6bbdaf0a3eb6735d634dd9f5b8045563c2b88ffceeabc9343bf7c0"
        ),
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_PATH.as_posix(): (
            "80acb365fa28ff06d4ad95fc0c928e9993c8825a7828310921fea91de5d32c81"
        ),
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY_PATH.as_posix(): (
            "81992abe14029ad78a50b9d3b83cf11658846f6dea9d9f2688e058778cdf3422"
        ),
    }
    assert {path: bindings[path] for path in expected_bindings} == expected_bindings

    relations = _relation_keys(data)
    assert (
        builder.COMMITMENT_UID,
        "PRESERVES",
        builder.TARGET_INVARIANTS["TI-1"]["uid"],
    ) in relations
    for invariant_id, invariant in builder.TARGET_INVARIANTS.items():
        for source_uid in invariant["source_uids"]:
            assert (invariant["uid"], "HAS_SOURCE", source_uid) in relations
        if invariant_id != "TI-1":
            assert (
                builder.COMMITMENT_UID,
                "PRESERVES",
                invariant["uid"],
            ) not in relations
    for source_uid in (
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_UID,
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY_UID,
    ):
        assert (builder.PROGRAM_UID, "HAS_SOURCE", source_uid) in relations


def test_external_fractal_sources_are_anchors_not_duplicate_local_nodes() -> None:
    data = _data()
    external = {
        builder.FRACTAL_USER_SOURCE_UID: (
            "USER_PRIMARY HSWM fractal cognitive composition 2026-08-28",
            {"AbstractNode", "SourceDocument", "CanonicalSource"},
        ),
        builder.FRACTAL_CANON_UID: (
            "HSWM fractal cognitive composition canon 2026-08-28",
            {"AbstractNode", "ResearchArtifact"},
        ),
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_UID: (
            "HSWM fractal cognitive-composition scientific connection synthesis",
            {"AbstractNode", "ResearchArtifact"},
        ),
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY_UID: (
            "HSWM fractal scientific connections ontology 2026-08-28",
            {"AbstractNode", "ResearchArtifact"},
        ),
    }
    assert not external.keys() & {row["uid"] for row in data["nodes"]}
    anchors = {row["uid"]: row for row in data["anchors"]}
    for uid, (name, labels) in external.items():
        assert anchors[uid]["name"] == name
        assert set(anchors[uid]["required_labels"]) == labels

    observed: dict[str, tuple[str, set[str]]] = {}
    local_uids = {row["uid"] for row in data["nodes"]}
    duplicate_local_uids: set[str] = set()
    for path in (ROOT / "ontology").rglob("*.json"):
        if path == ONTOLOGY_PATH:
            continue
        candidate = json.loads(path.read_text(encoding="utf-8"))
        for row in candidate.get("nodes", []):
            if row.get("uid") in local_uids:
                duplicate_local_uids.add(row["uid"])
            if row.get("uid") in external:
                observed[row["uid"]] = (
                    row["properties"]["name"],
                    set(row["labels"]),
                )
    assert observed == external
    assert not duplicate_local_uids


def test_program_preserves_all_fcl_targets_but_not_mechanisms() -> None:
    data = _data()
    relations = _relation_keys(data)
    for fcl_uid in builder.FCL_UIDS.values():
        assert (builder.PROGRAM_UID, "PRESERVES", fcl_uid) in relations

    mechanisms = [
        row
        for row in data["nodes"]
        if "AUXILIARY_HYPOTHESIS_FAMILY"
        in row["properties"]["semantic_roles"]
    ]
    assert len(mechanisms) == 9
    assert all(
        row["properties"]["canonical_scope"]
        == "REVISABLE_AUXILIARY_HYPOTHESIS_FAMILY"
        for row in mechanisms
    )
    assert all(
        row["properties"]["epistemic_state"] == "REPLACEABLE_UNJUDGED"
        for row in mechanisms
    )


def test_red_path_preserves_evidence_and_reenters_through_new_preregistration() -> None:
    data = _data()
    relations = _relation_keys(data)
    state = {
        name: f"sym:Concept:hswm-adaptive-disposition-{name.lower().replace('_', '-')}"
        for name in builder.DISPOSITION_STATES
    }
    assert (state["TESTING"], "NEXT", state["RED_WITHIN_SCOPE"]) in relations
    assert (
        state["RED_WITHIN_SCOPE"],
        "NEXT",
        state["RETIRED_WITH_EVIDENCE_PRESERVED"],
    ) in relations
    assert (
        state["RETIRED_WITH_EVIDENCE_PRESERVED"],
        "NEXT",
        state["REROUTE_PROPOSED"],
    ) in relations
    assert (
        state["REROUTE_PROPOSED"],
        "NEXT",
        state["PREREGISTERED"],
    ) in relations


def test_reroute_requires_falsification_lineage_and_claim_guards() -> None:
    data = _data()
    relations = _relation_keys(data)
    reroute_uid = builder.GUARDRAILS["RG-3"][0]
    for guard_id in ("RG-1", "RG-2", "RG-4", "RG-5", "RG-6"):
        assert (
            reroute_uid,
            "REQUIRES",
            builder.GUARDRAILS[guard_id][0],
        ) in relations


def test_validator_refuses_source_drift_and_efficacy_edge() -> None:
    data = _data()
    data["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact binding drifted"):
        publisher.validate_data(data, ROOT)

    data = _data()
    data["relations"][0]["type"] = "EVIDENCE_FOR"
    with pytest.raises(ValueError, match="projection content drifted"):
        publisher.validate_data(data, ROOT)

    data = _data()
    data["relations"] = [
        row
        for row in data["relations"]
        if not (
            row["from_uid"] == builder.TARGET_INVARIANTS["TI-4"]["uid"]
            and row["type"] == "HAS_SOURCE"
            and row["to_uid"] == builder.FRACTAL_CANON_UID
        )
    ]
    with pytest.raises(ValueError, match="projection content drifted"):
        publisher.validate_data(data, ROOT)


def test_validator_refuses_partial_target_preservation() -> None:
    data = _data()
    expected = (
        builder.PROGRAM_UID,
        "PRESERVES",
        builder.FCL_UIDS["FCL-8"],
    )
    replacement = copy.deepcopy(data["relations"][0])
    data["relations"] = [
        row
        for row in data["relations"]
        if (row["from_uid"], row["type"], row["to_uid"]) != expected
    ]
    data["relations"].append(replacement)
    with pytest.raises(ValueError, match="projection content drifted"):
        publisher.validate_data(data, ROOT)


def test_owned_bundle_migration_classifier_accepts_only_known_states() -> None:
    data = _data()

    assert (
        publisher.classify_owned_snapshot(publisher.PREDECESSOR_SNAPSHOT, data)
        == "EXACT_PREDECESSOR"
    )
    current = publisher._expected_snapshot(data)
    assert publisher.classify_owned_snapshot(current, data) == "EXACT_CURRENT"

    partial = dict(publisher.PREDECESSOR_SNAPSHOT)
    partial["nodes"] = int(partial["nodes"]) - 1
    with pytest.raises(RuntimeError, match="partial, mixed, or unknown"):
        publisher.classify_owned_snapshot(partial, data)

    unknown = dict(publisher.PREDECESSOR_SNAPSHOT)
    unknown["relation_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="partial, mixed, or unknown"):
        publisher.classify_owned_snapshot(unknown, data)


def test_predecessor_migration_refuses_new_uid_collision_before_any_write() -> None:
    data = _data()
    retained = [
        {
            "uid": row["uid"],
            "labels": row["labels"],
            "properties": {"predecessor": row["uid"]},
        }
        for row in data["nodes"]
        if row["uid"] not in publisher.MIGRATION_NEW_NODE_UIDS
    ]
    retained_by_uid = {row["uid"]: row for row in retained}
    queries: list[str] = []

    class Rows:
        def __init__(self, values: list[dict]) -> None:
            self.values = values

        def data(self) -> list[dict]:
            return self.values

    class CollisionTx:
        def run(self, query: str, **kwargs: object) -> Rows:
            queries.append(query)
            assert query.startswith("MATCH (n) WHERE n.uid IN $uids")
            uids = kwargs["uids"]
            assert isinstance(uids, list)
            if set(uids) == publisher.MIGRATION_NEW_NODE_UIDS:
                uid = next(iter(publisher.MIGRATION_NEW_NODE_UIDS))
                return Rows([{"uid": uid, "labels": ["External"], "properties": {}}])
            return Rows([copy.deepcopy(retained_by_uid[uid]) for uid in uids])

    with pytest.raises(RuntimeError, match="already exists externally"):
        publisher._migrate_exact_predecessor(
            CollisionTx(),
            data,
            retained,
            [],
        )

    assert queries
    assert all(query.startswith("MATCH ") for query in queries)


def test_predecessor_relation_delete_does_not_return_deleted_entity() -> None:
    source = (
        ROOT / "scripts/upsert_hswm_adaptive_research_strategy.py"
    ).read_text(encoding="utf-8")

    assert "DELETE r RETURN count(r)" not in source
    assert "DELETE r RETURN 1 AS deleted" in source
