from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure.research_evidence_graph_view import (
    CLAIM_CEILING,
    NONCLAIM,
    PublicReceiptSource,
    ResearchEvidenceGraphView,
    ResearchEvidenceGraphViewError,
)
from hswm.infrastructure.standard_graph_view import StandardGraphViewDependencyError


SHAPES = (
    Path(__file__).parents[1]
    / "schemas/HSWM_RESEARCH_EVIDENCE_RDF_PROJECTION_SHACL_1_0.ttl"
)


def _source(source_id: str = "receipt-1") -> PublicReceiptSource:
    raw = json.dumps(
        {
            "schema_version": "hswm-g1-opaque-identifiability-public-redacted-projection/v1",
            "record_role": (
                "POST_EXECUTION_AGGREGATE_IDENTIFIABILITY_RESULT_NOT_G0_"
                "PROMOTION_OR_G1_EFFICACY"
            ),
            "study_uid": "sym:ExploratoryStudy:fixture",
            "terminal": "PILOT_COMPLETE_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE",
            "scientific_status": (
                "EXPLORATORY_G0_IDENTIFIABILITY_THRESHOLD_OBSERVED_G0_NOT_"
                "PASSED_G1_NOT_EVALUATED"
            ),
            "claim_boundary": {
                "claim_ceiling": "EXPLORATORY_G0_IDENTIFIABILITY_ONLY",
                "g0_gate_passed": False,
                "g1_gate_evaluated": False,
            },
            # Deliberately unprojected: it keeps separate fixture sources from
            # sharing a raw-byte digest without exercising generic flattening.
            "fixture_marker": source_id,
            "aggregate_result": {"count": 2},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return PublicReceiptSource(source_id, raw, sha256(raw).hexdigest(), len(raw))


def test_raw_bytes_are_bound_and_only_allowlisted_metadata_is_exported() -> None:
    source = _source()
    view = ResearchEvidenceGraphView.from_public_receipts(sources=(source,))
    assert view.descriptor["dataset"]["sha256"] == sha256(view.nquads).hexdigest()
    assert view.descriptor["sources"][0]["sha256"] == sha256(source.raw_bytes).hexdigest()
    assert b"aggregate" not in view.nquads
    assert b"POST_EXECUTION_AGGREGATE_IDENTIFIABILITY_RESULT" in view.nquads
    assert view.descriptor["nonclaim"] == NONCLAIM
    assert view.claim_ceiling == CLAIM_CEILING


def test_checked_in_g1_public_projection_is_an_exact_supported_source() -> None:
    raw = (
        Path(__file__).parents[1]
        / "results/raw/hswm_g1_opaque_identifiability_v2_2026-08-30/"
        "public_redacted_projection.json"
    ).read_bytes()
    view = ResearchEvidenceGraphView.from_public_receipts(
        sources=(
            PublicReceiptSource(
                "g1-opaque-v2-public",
                raw,
                "afc7e1f56522f276376ef7f331962f737b4ff2eeda1dff10f6ebc3fa35232f65",
                12363,
            ),
        )
    )
    assert b"sym:ExploratoryStudy:hswm-g1-opaque-identifiability-v2-2026-08-30" in view.nquads
    assert b"model_runtime" not in view.nquads
    assert b"aggregate_result" not in view.nquads


def test_deterministic_blank_node_free_nquads_and_source_ordering() -> None:
    one = _source("one")
    two = _source("two")
    left = ResearchEvidenceGraphView.from_public_receipts(sources=(two, one))
    right = ResearchEvidenceGraphView.from_public_receipts(sources=(one, two))
    assert left.nquads == right.nquads
    assert b"_:" not in left.nquads


def test_source_and_sensitive_payload_fail_closed() -> None:
    fixture = _source()
    with pytest.raises(ResearchEvidenceGraphViewError, match="source_id"):
        PublicReceiptSource("bad id", fixture.raw_bytes, fixture.sha256, fixture.byte_length)
    with pytest.raises(ResearchEvidenceGraphViewError, match="forbidden payload"):
        raw = b'{"schema_version":"v1","prompt":"secret"}'
        PublicReceiptSource("private", raw, sha256(raw).hexdigest(), len(raw))
    raw = _source().raw_bytes
    with pytest.raises(ResearchEvidenceGraphViewError, match="SHA-256 differs"):
        PublicReceiptSource("mutated", raw + b" ", sha256(raw).hexdigest(), len(raw) + 1)
    with pytest.raises(ResearchEvidenceGraphViewError, match="byte length differs"):
        PublicReceiptSource("short", raw, sha256(raw).hexdigest(), len(raw) - 1)
    with pytest.raises(ResearchEvidenceGraphViewError, match="unique"):
        ResearchEvidenceGraphView.from_public_receipts(sources=(_source(), _source()))
    same = _source("same-one")
    with pytest.raises(ResearchEvidenceGraphViewError, match="SHA-256 values must be unique"):
        ResearchEvidenceGraphView.from_public_receipts(
            sources=(
                same,
                PublicReceiptSource(
                    "same-two", same.raw_bytes, same.sha256, same.byte_length
                ),
            )
        )
    with pytest.raises(ResearchEvidenceGraphViewError, match="one or more"):
        ResearchEvidenceGraphView.from_public_receipts(sources=())


@pytest.mark.parametrize("field", ("g0_gate_passed", "g1_gate_evaluated"))
def test_contradictory_gate_promotion_is_rejected(field: str) -> None:
    value = json.loads(_source().raw_bytes)
    value["claim_boundary"][field] = True
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ResearchEvidenceGraphViewError, match="cannot promote"):
        PublicReceiptSource("promoted", raw, sha256(raw).hexdigest(), len(raw))


@pytest.mark.parametrize("constant", (b"NaN", b"Infinity", b"-Infinity"))
def test_strict_json_rejects_duplicate_keys_and_nonfinite_constants(constant: bytes) -> None:
    raw = b'{"schema_version":"x","schema_version":"x"}'
    with pytest.raises(ResearchEvidenceGraphViewError, match="duplicate JSON key"):
        PublicReceiptSource("duplicate", raw, sha256(raw).hexdigest(), len(raw))
    raw = b'{"schema_version":' + constant + b"}"
    with pytest.raises(ResearchEvidenceGraphViewError, match="non-finite JSON constant"):
        PublicReceiptSource("nonfinite", raw, sha256(raw).hexdigest(), len(raw))


def test_strict_json_rejects_non_utf8_and_excessive_depth() -> None:
    utf16 = '{}'.encode("utf-16")
    with pytest.raises(ResearchEvidenceGraphViewError, match="strict UTF-8"):
        PublicReceiptSource("utf16", utf16, sha256(utf16).hexdigest(), len(utf16))
    deep = ('{"x":' * 66 + "null" + "}" * 66).encode()
    with pytest.raises(ResearchEvidenceGraphViewError, match="depth limit"):
        PublicReceiptSource("deep", deep, sha256(deep).hexdigest(), len(deep))


def test_direct_construction_and_descriptor_mutation_fail_closed() -> None:
    source = _source()
    with pytest.raises(ResearchEvidenceGraphViewError, match="must be built"):
        ResearchEvidenceGraphView(object(), b"x", {}, ())
    view = ResearchEvidenceGraphView.from_public_receipts(sources=(source,))
    with pytest.raises(TypeError):
        view.descriptor["dataset"]["sha256"] = "0" * 64
    with pytest.raises(TypeError):
        view.descriptor["sources"][0]["sha256"] = "0" * 64


def test_query_refuses_nonlocal_and_nonread_forms_before_optional_dependencies() -> None:
    view = ResearchEvidenceGraphView.from_public_receipts(sources=(_source(),))
    for query in (
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
        "INSERT DATA { <x> <y> <z> }",
        "SELECT * FROM <https://remote.example/data> WHERE { ?s ?p ?o }",
        "ASK { SERVICE <https://remote.example/sparql> { ?s ?p ?o } }",
    ):
        with pytest.raises(ResearchEvidenceGraphViewError):
            view.query(query)


def test_local_select_ask_shacl_and_constrained_prov_when_graph_dependencies_exist() -> None:
    view = ResearchEvidenceGraphView.from_public_receipts(sources=(_source(),))
    try:
        assert view.query("ASK { GRAPH ?graph { ?s ?p ?o } }") is True
        rows = view.query(
            "SELECT ?status WHERE { GRAPH ?graph { ?s "
            "<https://hswm.invalid/research-evidence-rdf/v1/terminal> ?status } }"
        )
        assert rows == (
            {
                "status": {
                    "kind": "literal",
                    "value": (
                        "PILOT_COMPLETE_IDENTIFIABILITY_OBSERVED_NO_"
                        "EFFICACY_INFERENCE"
                    ),
                }
            },
        )
        assert (
            view.query(
                "ASK { GRAPH ?graph { ?s "
                "<https://hswm.invalid/research-evidence-rdf/v1/g0GatePassed> "
                "false } }"
            )
            is True
        )
        bool_rows = view.query(
            "SELECT ?flag WHERE { GRAPH ?graph { ?s "
            "<https://hswm.invalid/research-evidence-rdf/v1/g0GatePassed> "
            "?flag } }"
        )
        assert bool_rows == (
            {
                "flag": {
                    "kind": "literal",
                    "value": "false",
                    "datatype": "http://www.w3.org/2001/XMLSchema#boolean",
                }
            },
        )
        assert view.validate_shacl(shapes=SHAPES.read_bytes())["conforms"] is True
    except StandardGraphViewDependencyError:
        pytest.skip("optional graph dependencies are not installed")
    envelope = json.loads(view.prov_o_envelope())
    emitted_keys = {key for item in envelope["@graph"] for key in item}
    assert emitted_keys.isdisjoint({"re:outcome", "re:credit", "re:permit"})
    projection = next(
        item
        for item in envelope["@graph"]
        if item["@id"]
        == (
            "urn:hswm:research-evidence-projection:"
            f"{view.descriptor['projectionIdentitySha256']}"
        )
    )
    assert projection["prov:wasGeneratedBy"] == {"@id": projection["@id"] + ":derivation"}
    assert projection["re:datasetSha256"] == view.descriptor["dataset"]["sha256"]
    assert b"<http://www.w3.org/ns/prov#Entity>" in view.nquads
