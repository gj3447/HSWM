import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / "research" / "HSWM_SHEAF_ONTOLOGY.v1.json"


def load_ontology() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def test_sheaf_ontology_inventory_and_uids_are_stable() -> None:
    data = load_ontology()
    assert data["schema_version"] == "hswm-sheaf-ontology/v1"
    assert len(data["concepts"]) == 28
    assert len(data["sources"]) == 12
    assert len(data["hswm_mappings"]) == 8
    assert len(data["concept_relations"]) == 32

    uids = [
        data["bundle_uid"],
        *[row["uid"] for row in data["concepts"]],
        *[row["uid"] for row in data["sources"]],
        *[row["uid"] for row in data["hswm_mappings"]],
    ]
    assert len(uids) == len(set(uids))


def test_sheaf_ontology_relationship_endpoints_exist() -> None:
    data = load_ontology()
    concept_uids = {row["uid"] for row in data["concepts"]}
    source_uids = {row["uid"] for row in data["sources"]}

    for relation in data["concept_relations"]:
        assert relation["from_uid"] in concept_uids
        assert relation["to_uid"] in concept_uids
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", relation["type"])
    for link in data["source_concept_links"]:
        assert link["source_uid"] in source_uids
        assert set(link["concept_uids"]) <= concept_uids
    for mapping in data["hswm_mappings"]:
        assert mapping["sheaf_concept_uid"] in concept_uids


def test_sheaf_sources_preserve_publication_authority_boundaries() -> None:
    data = load_ontology()
    statuses = {row["publication_status"] for row in data["sources"]}
    assert "PEER_REVIEWED_PRIMARY" in statuses
    assert "PHD_THESIS_PRIMARY" in statuses
    assert "PREPRINT_PRIMARY" in statuses
    assert "RECENT_PREPRINT_EXPLORATORY" in statuses
    assert sum(row["publication_status"] == "RECENT_PREPRINT_EXPLORATORY" for row in data["sources"]) == 2
    assert all(row["url"].startswith("https://") for row in data["sources"])


def test_hswm_mappings_remain_noncanonical_and_caveated() -> None:
    data = load_ontology()
    assert data["status"] == "SECONDARY_AI_RESEARCH_MAP"
    assert "No HSWM efficacy claim is made" in data["authority_boundary"]
    assert all(row["caveat"] for row in data["hswm_mappings"])
    assert "Sheaf consistency is not factual truth." in data["nonclaims"]
    assert "A global section is not forced consensus." in data["nonclaims"]


def test_kg_schema_binding_covers_unregistered_semantic_relations() -> None:
    data = load_ontology()
    binding = data["kg_schema_binding"]
    aliases = binding["relationship_type_aliases"]
    expected_aliases = {
        "HAS_LOCAL_DATA",
        "TRANSPORTS_BETWEEN",
        "ASSIGNS",
        "IS_SECTION_OVER_ALL",
        "COMPUTABLE_PRESENTATION_OF",
        "INDEXED_BY",
        "DUAL_DIRECTION_TO",
        "LIES_IN_KERNEL_OF",
    }
    assert set(aliases) == expected_aliases
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]*", target) for target in aliases.values())
