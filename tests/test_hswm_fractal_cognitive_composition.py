from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.upsert_human_universal_body_fractal_projection import BUNDLE_UID, FRACTAL_UID, NONCLAIM, validate_data


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json"
CORE_V1 = ROOT / "ontology/identity/hswm_core/HSWM_CORE_RESPONSIBILITY_ONTOLOGY.v1.json"
CORE_TS = ROOT / "src/hswm/effect-runtime/src/hswm-core-ontology.ts"
PROJECTION = ROOT / "ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_FRACTAL_PROJECTION.v1.json"
V1_SHA256 = "4b7bd2574491c0c6f17f00226db53811311e993e6f995b6e3e076e8f1d457238"
CORE_V1_SHA256 = "4cba162f4b392ce3ede45365b45ccbf22640fdaa4a101184c4a206f12cc657b2"
CORE_CONTENT_SHA256 = "c5f11257cd6b17a6c3055dcad772ddcd41149a3779370565728e74ec7d4fc6f2"
SOURCE_SHA256 = "c453034f1d13c2bd7498a2e6b488a3bf07af74a3a7ee0f4d1ba7d4c74b2e685e"
CANON_SHA256 = "d7dc6d86dc6bbdaf0a3eb6735d634dd9f5b8045563c2b88ffceeabc9343bf7c0"
SOURCE_UID = "sym:CanonicalSource:user-primary-hswm-fractal-cognitive-composition-2026-08-28"
CANON_UID = "sym:AbstractNode:hswm-fractal-cognitive-composition-canon-2026-08-28"
THEORY_UID = "sym:AbstractNode:hswm-fractal-cognitive-composition-prior-theory-map-2026-08-28"
CONTRACT_UID = "sym:Concept:hswm-same-ignition-composition-contract"
LAW_UIDS = {
    "sym:Concept:hswm-fractal-law-local-causal-learning",
    "sym:Concept:hswm-fractal-law-composition-preservation",
    "sym:Concept:hswm-fractal-law-emergent-coalition",
    "sym:Concept:hswm-fractal-law-multiscale-credit",
    "sym:Concept:hswm-fractal-law-topology-morphogenesis",
    "sym:Concept:hswm-fractal-law-world-self-co-model",
    "sym:Concept:hswm-fractal-law-diachronic-continuity",
    "sym:Concept:hswm-fractal-law-hswm-of-hswms",
}


def _is_python_sdist() -> bool:
    """The Effect runtime is intentionally absent from the Python sdist."""
    return (ROOT / "PKG-INFO").is_file()


def _data() -> dict[str, object]:
    return json.loads(PROJECTION.read_text(encoding="utf-8"))


def _relations(data: dict[str, object]) -> set[tuple[str, str, str, str, str, str]]:
    return {
        (row["from_uid"], row["type"], row["to_uid"], row["authority_class"], row["scope"], row["status"])
        for row in data["relations"]
    }


def test_hash_bound_human_body_v1_is_exact_and_contains_no_fractal_overlay() -> None:
    assert hashlib.sha256(V1.read_bytes()).hexdigest() == V1_SHA256
    legacy = json.loads(V1.read_text(encoding="utf-8"))
    assert legacy["schema_version"] == "hswm-human-universal-body-ontology/v1"
    assert all("fractal-cognitive-composition-2026-08-28" not in row["uid"] for row in legacy["nodes"])


def test_fractal_projection_has_exactly_fourteen_new_nodes_and_anchor_endpoint_closure() -> None:
    data = _data()
    validate_data(data, ROOT)
    nodes = {row["uid"]: row for row in data["nodes"]}
    anchors = {row["uid"] for row in data["anchors"]}
    assert data["bundle_uid"] == BUNDLE_UID and data["nonclaim"] == NONCLAIM
    assert len(nodes) == 14 and BUNDLE_UID in nodes and FRACTAL_UID in nodes
    assert not (set(nodes) & anchors)
    assert all(row["properties"]["responsibility_owner"] for row in nodes.values())
    assert all(row["properties"]["authority_class"] for row in nodes.values())
    assert all(row["properties"]["projection_nonclaim"] for row in nodes.values())
    endpoints = set(nodes) | anchors
    assert all(row["from_uid"] in endpoints and row["to_uid"] in endpoints for row in data["relations"])


def test_fractal_projection_binds_user_source_and_never_claims_science() -> None:
    data = _data()
    assert data["source_sha256"] == SOURCE_SHA256
    assert hashlib.sha256((ROOT / data["source_path"]).read_bytes()).hexdigest() == SOURCE_SHA256
    source = next(row for row in data["nodes"] if row["uid"].startswith("sym:CanonicalSource:"))
    assert source["properties"]["authority_class"] == "USER_PRIMARY"
    assert "NOT_HSWM_COGNITION" in data["nonclaim"]


def test_retired_core_v1_bytes_and_anchor_are_restored_not_refreshed() -> None:
    assert hashlib.sha256(CORE_V1.read_bytes()).hexdigest() == CORE_V1_SHA256
    core = json.loads(CORE_V1.read_text(encoding="utf-8"))
    assert all(anchor["source_bundle_sha256"] == V1_SHA256 for anchor in core["external_anchors"])
    if _is_python_sdist():
        # The Python distribution transports the authoritative JSON ontology but
        # deliberately prunes the separate npm/Effect artifact.  Its absence is
        # a packaging boundary, not evidence that the historical anchor changed.
        assert not CORE_TS.exists()
    else:
        ts = CORE_TS.read_text(encoding="utf-8")
        assert CORE_CONTENT_SHA256 in ts
        assert V1_SHA256 in ts


def test_projection_is_uid_disjoint_and_preserves_complete_scientific_fields() -> None:
    data = _data()
    nodes = {row["uid"]: row for row in data["nodes"]}
    legacy = json.loads(V1.read_text(encoding="utf-8"))
    historical_uids = {row["uid"] for row in [*legacy["nodes"], *legacy["anchors"]]}
    anchors = {row["uid"] for row in data["anchors"]}
    assert len(nodes) == 14
    assert set(nodes).isdisjoint(anchors | historical_uids)
    assert {BUNDLE_UID, SOURCE_UID, CANON_UID, THEORY_UID, FRACTAL_UID, CONTRACT_UID, *LAW_UIDS} == set(nodes)
    for row in nodes.values():
        properties = row["properties"]
        assert all(isinstance(properties.get(key), str) and properties[key] for key in (
            "name", "authority_class", "canonical_scope", "ontology_kind", "ontology_plane",
            "epistemic_state", "responsibility_owner", "claim_boundary", "projection_nonclaim",
        ))
    for uid in LAW_UIDS:
        properties = nodes[uid]["properties"]
        assert (properties["authority_class"], properties["canonical_scope"], properties["epistemic_state"]) == (
            "MIXED_EXPLICIT", "USER_TARGET_WITH_AI_FORMALIZATION", "UNASSESSED"
        )
        assert properties.get("acceptance_logic") and properties.get("claim_boundary")
    assert nodes[CONTRACT_UID]["properties"].get("architectural_implications")
    theory = nodes[THEORY_UID]["properties"]
    assert theory["authority_class"] == "SECONDARY_AI"
    assert theory["epistemic_state"] == "PRELIMINARY"
    assert len(theory.get("source_urls", [])) >= 10 and theory.get("claim_boundary")


def test_projection_binds_both_artifacts_and_preserves_all_47_relation_semantics() -> None:
    data = _data()
    assert (data["historical_base_sha256"], data["source_sha256"], data["canon_sha256"]) == (
        V1_SHA256, SOURCE_SHA256, CANON_SHA256
    )
    assert hashlib.sha256((ROOT / data["historical_base_path"]).read_bytes()).hexdigest() == V1_SHA256
    assert hashlib.sha256((ROOT / data["source_path"]).read_bytes()).hexdigest() == SOURCE_SHA256
    assert hashlib.sha256((ROOT / data["canon_path"]).read_bytes()).hexdigest() == CANON_SHA256
    rows = _relations(data)
    assert len(rows) == 47
    endpoints = {row["uid"] for row in data["nodes"]} | {row["uid"] for row in data["anchors"]}
    anchors = {row["uid"] for row in data["anchors"]}
    assert all(left in endpoints and right in endpoints for left, _, right, *_ in rows)
    assert all(not (left in anchors and right in anchors) for left, _, right, *_ in rows)
    assert anchors <= {endpoint for row in rows for endpoint in (row[0], row[2])}
    user = ("USER_PRIMARY", "USER_UTTERANCE_2026_08_28", "ACTIVE")
    mixed = ("MIXED_EXPLICIT", "USER_LAW_AND_AI_FALSIFIER_2026_08_28", "ACTIVE")
    assert ("sym:Concept:hswm", "STRUCTURED_AS", FRACTAL_UID, *user) in rows
    assert ("sym:Concept:human-universal-body", "REQUIRES", FRACTAL_UID, *user) in rows
    assert (SOURCE_UID, "USER_PRIMARY_SOURCE_FOR", FRACTAL_UID, *user) in rows
    for uid in LAW_UIDS:
        assert (SOURCE_UID, "USER_PRIMARY_SOURCE_FOR", uid, *user) in rows
        assert (CANON_UID, "HAS_CONCEPT", uid, *mixed) in rows
        assert (FRACTAL_UID, "REQUIRES", uid, *user) in rows
    assert (CANON_UID, "HAS_SOURCE", SOURCE_UID, "SYSTEM_DERIVED", "CANONICAL_FORMALIZATION_2026_08_28", "ACTIVE") in rows
    assert (CANON_UID, "HAS_SOURCE", THEORY_UID, "SECONDARY_AI", "HSWM_RESEARCH_SYNTHESIS_2026_08_28", "PROPOSED") in rows
    assert (FRACTAL_UID, "REQUIRES", CONTRACT_UID, "SECONDARY_AI", "HSWM_ENGINEERING_FORMALIZATION_2026_08_28", "PROPOSED") in rows
    publication = ("SYSTEM_DERIVED", "ONTOLOGY_PUBLICATION_2026_08_28", "ACTIVE")
    proposed_mixed = ("MIXED_EXPLICIT", "USER_LAW_AND_AI_FALSIFIER_2026_08_28", "PROPOSED")
    expected = {
        (BUNDLE_UID, "HAS_SOURCE", SOURCE_UID, *publication),
        *( (BUNDLE_UID, "HAS_CONCEPT", uid, *publication) for uid in (CANON_UID, THEORY_UID, FRACTAL_UID) ),
        *( (SOURCE_UID, "USER_PRIMARY_SOURCE_FOR", uid, *user) for uid in (FRACTAL_UID, *LAW_UIDS) ),
        (CANON_UID, "HAS_SOURCE", SOURCE_UID, "SYSTEM_DERIVED", "CANONICAL_FORMALIZATION_2026_08_28", "ACTIVE"),
        (CANON_UID, "HAS_SOURCE", THEORY_UID, "SECONDARY_AI", "HSWM_RESEARCH_SYNTHESIS_2026_08_28", "PROPOSED"),
        (CANON_UID, "HAS_CONCEPT", FRACTAL_UID, "MIXED_EXPLICIT", "USER_DIRECTION_AND_AI_FORMALIZATION_2026_08_28", "ACTIVE"),
        (CANON_UID, "HAS_CONCEPT", CONTRACT_UID, "SECONDARY_AI", "HSWM_ENGINEERING_FORMALIZATION_2026_08_28", "PROPOSED"),
        *( (CANON_UID, "HAS_CONCEPT", uid, *mixed) for uid in LAW_UIDS ),
        ("sym:Concept:hswm", "STRUCTURED_AS", FRACTAL_UID, *user),
        (FRACTAL_UID, "PART_OF", "sym:Concept:hswm", *user),
        (FRACTAL_UID, "REFINES", "sym:Concept:human-universal-body-self-similar-composition", "MIXED_EXPLICIT", "USER_DIRECTION_AND_AI_FORMALIZATION_2026_08_28", "ACTIVE"),
        (FRACTAL_UID, "REQUIRES", CONTRACT_UID, "SECONDARY_AI", "HSWM_ENGINEERING_FORMALIZATION_2026_08_28", "PROPOSED"),
        *( (FRACTAL_UID, "REQUIRES", uid, *user) for uid in LAW_UIDS ),
        ("sym:Concept:human-universal-body", "REQUIRES", FRACTAL_UID, *user),
        (CONTRACT_UID, "REFINES", "sym:Concept:hswm-operational-composite-individuation", "SECONDARY_AI", "HSWM_ENGINEERING_FORMALIZATION_2026_08_28", "PROPOSED"),
        *( (uid, "REFINES", anchor, *proposed_mixed) for uid, anchor in {
            "sym:Concept:hswm-fractal-law-local-causal-learning": "sym:Concept:human-universal-body-outcome-bound-learning",
            "sym:Concept:hswm-fractal-law-composition-preservation": "sym:Concept:human-universal-body-self-similar-composition",
            "sym:Concept:hswm-fractal-law-emergent-coalition": "sym:Concept:hswm-sparse-bounded-recurrent-routing",
            "sym:Concept:hswm-fractal-law-multiscale-credit": "sym:Concept:hswm-semantic-causal-weight-separation",
            "sym:Concept:hswm-fractal-law-topology-morphogenesis": "sym:Concept:hswm-topology-morphogenesis",
            "sym:Concept:hswm-fractal-law-world-self-co-model": "sym:Concept:human-universal-body-global-self-model",
            "sym:Concept:hswm-fractal-law-diachronic-continuity": "sym:Concept:human-universal-body-persistent-shared-state",
        }.items() ),
        ("sym:Concept:hswm-fractal-law-hswm-of-hswms", "SUBSTRATE_FOR", "sym:Concept:human-universal-body", *proposed_mixed),
    }
    assert rows == expected


@pytest.mark.parametrize("mutate", (
    lambda data: data.__setitem__("historical_base_sha256", "0" * 64),
    lambda data: data["nodes"][0]["properties"].pop("responsibility_owner"),
    lambda data: data["nodes"].append(deepcopy(data["nodes"][0])),
    lambda data: data["relations"].append(deepcopy(data["relations"][0])),
    lambda data: data["relations"][0].__setitem__("to_uid", "missing:uid"),
    lambda data: data["relations"][0].update(
        from_uid=data["anchors"][0]["uid"], to_uid=data["anchors"][1]["uid"]
    ),
))
def test_projection_validator_refuses_provenance_owner_uid_and_relation_mutations(mutate) -> None:
    data = _data()
    mutate(data)
    with pytest.raises(ValueError):
        validate_data(data, ROOT)
