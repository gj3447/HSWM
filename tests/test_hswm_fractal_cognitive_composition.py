from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.upsert_human_universal_body_ontology import validate_data


ROOT = Path(__file__).resolve().parents[1]
CANON = (
    ROOT
    / "docs"
    / "canon"
    / "USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md"
)
SOURCE = (
    ROOT
    / "docs"
    / "canon"
    / "sources"
    / "USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.txt"
)
CONSTITUTION = ROOT / "docs" / "canon" / "HSWM_CONSTITUTION_2026-08-20.md"
ONTOLOGY = (
    ROOT
    / "ontology"
    / "identity"
    / "human_universal_body"
    / "HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json"
)
SOURCE_SHA256 = "c453034f1d13c2bd7498a2e6b488a3bf07af74a3a7ee0f4d1ba7d4c74b2e685e"

CORE_UID = "sym:Concept:hswm-fractal-cognitive-composition"
SOURCE_UID = (
    "sym:CanonicalSource:user-primary-hswm-fractal-cognitive-composition-2026-08-28"
)
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ontology() -> dict[str, object]:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


def test_fractal_cognitive_composition_pins_user_source_and_authority() -> None:
    assert _sha256(SOURCE) == SOURCE_SHA256

    canon = CANON.read_text(encoding="utf-8")
    constitution = CONSTITUTION.read_text(encoding="utf-8")
    for required in (
        "USER_PRIMARY target identity",
        "fractal cognitive composition",
        "동일한 점화식",
        "HSWM-of-HSWMs",
        "scale-relative 거대한 인지능력체",
        "과학적 상태:** `UNJUDGED`",
        "Hausdorff dimension",
        "KG에 기록됐다는 사실이 HSWM cognition·learning·효능을 만들지 않는다",
        SOURCE_SHA256,
    ):
        assert required in canon

    assert CANON.name in constitution
    assert "왜 프랙탈인가 — 인지적 합성 closure" in constitution
    assert "H/W/A/F/Π" not in canon


def test_fractal_ontology_has_core_eight_laws_and_one_owner_per_new_atom() -> None:
    data = _ontology()
    validate_data(data, ROOT)
    nodes = {row["uid"]: row for row in data["nodes"]}

    assert nodes[SOURCE_UID]["properties"]["source_sha256"] == SOURCE_SHA256
    assert nodes[CORE_UID]["properties"]["authority_class"] == "USER_PRIMARY"
    assert LAW_UIDS <= nodes.keys()

    scoped_uids = {
        uid
        for uid in nodes
        if "fractal" in uid or uid == "sym:Concept:hswm-same-ignition-composition-contract"
    }
    assert len(scoped_uids) == 13
    for uid in scoped_uids:
        owner = nodes[uid]["properties"].get("responsibility_owner")
        assert isinstance(owner, str) and owner

    law_nodes = [nodes[uid]["properties"] for uid in LAW_UIDS]
    assert all(row["authority_class"] == "MIXED_EXPLICIT" for row in law_nodes)
    assert all(row["epistemic_state"] == "UNASSESSED" for row in law_nodes)
    assert all(row.get("acceptance_logic") for row in law_nodes)


def test_fractal_ontology_preserves_source_relations_and_prior_theory_boundary() -> None:
    data = _ontology()
    relations = {
        (row["from_uid"], row["type"], row["to_uid"]): row
        for row in data["relations"]
    }
    assert (SOURCE_UID, "USER_PRIMARY_SOURCE_FOR", CORE_UID) in relations
    for law_uid in LAW_UIDS:
        relation = relations[(SOURCE_UID, "USER_PRIMARY_SOURCE_FOR", law_uid)]
        assert relation["authority_class"] == "USER_PRIMARY"
        assert relation["scope"] == "USER_UTTERANCE_2026_08_28"
        assert (CORE_UID, "REQUIRES", law_uid) in relations

    theory_uid = (
        "sym:AbstractNode:hswm-fractal-cognitive-composition-prior-theory-map-2026-08-28"
    )
    theory = next(row["properties"] for row in data["nodes"] if row["uid"] == theory_uid)
    assert theory["authority_class"] == "SECONDARY_AI"
    assert theory["epistemic_state"] == "PRELIMINARY"
    assert len(theory["source_urls"]) >= 10
    assert "not HSWM identity authority" in theory["claim_boundary"]
