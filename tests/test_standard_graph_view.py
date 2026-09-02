from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure.standard_graph_view import StandardGraphView, StandardGraphViewDependencyError, StandardGraphViewError


NQUADS = b'<https://example.test/s> <https://example.test/p> "value" <https://example.test/g> .\n'
BLANK_NODE_NQUADS = b'_:subject <https://example.test/p> <https://example.test/o> <https://example.test/g> .\n'
_HSWM = "https://hswm.invalid/canonical-atom-v2/rdf/v1/vocab/"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_XSD_NON_NEGATIVE_INTEGER = "http://www.w3.org/2001/XMLSchema#nonNegativeInteger"


def _valid_hswm_projection_nquads() -> bytes:
    dataset = "https://example.test/dataset"
    entity = "https://example.test/atom/entity"
    relation = "https://example.test/atom/relation"
    reference = "https://example.test/reference/0"
    state = "https://example.test/graph/state"
    schema = "https://example.test/graph/schema"
    provenance = "https://example.test/graph/provenance"
    evidence = "https://example.test/graph/evidence"
    literal = lambda value: f'"{value}"'
    typed = lambda value: f'"{value}"^^<{_XSD_NON_NEGATIVE_INTEGER}>'
    lines = [
        (dataset, _RDF_TYPE, f"<{_HSWM}Dataset>", state),
        (dataset, f"{_HSWM}stateSha256", literal("0" * 64), state),
        (dataset, f"{_HSWM}stateRevision", typed(1), state),
        (dataset, f"{_HSWM}schemaVersion", literal("schema:v2"), schema),
        (dataset, f"{_HSWM}schemaContentSha256", literal("1" * 64), evidence),
        (dataset, f"{_HSWM}journalLineageId", literal("journal:main"), evidence),
        (dataset, f"{_HSWM}tailSha256", literal("2" * 64), evidence),
        (dataset, f"{_HSWM}rdfProfile", literal("RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE"), evidence),
        (dataset, f"{_HSWM}mapping", literal("ROLE_PRESERVING_REIFIED_TYPED_REFERENCE"), evidence),
        (dataset, f"{_HSWM}writeBack", literal("FORBIDDEN"), evidence),
        (dataset, f"{_HSWM}nonclaim", literal("RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY"), evidence),
        (dataset, f"{_HSWM}compilerContractVersion", literal("hswm-canonical-atom-v2-rdf-projection/v1"), evidence),
        (dataset, f"{_HSWM}compilerContractSha256", literal("3" * 64), evidence),
    ]
    for atom, rdf_class, kind, form, mode, source in (
        (entity, "CanonicalAtomVersion", "kind:entity", "ENTITY", "BOOTSTRAP", None),
        (relation, "ReifiedRelationAtomVersion", "kind:relation", "RELATION", "DERIVATION", entity),
    ):
        lines.extend(
            [
                (atom, _RDF_TYPE, f"<{_HSWM}{rdf_class}>", state),
                (atom, f"{_HSWM}canonicalKey", literal(f"schema:v2|lineage:main|{kind}|0"), state),
                (atom, f"{_HSWM}kind", literal(kind), schema),
                (atom, f"{_HSWM}kindForm", literal(form), schema),
                (atom, f"{_HSWM}responsibilityOwner", literal("owner:graph"), schema),
                (atom, f"{_HSWM}contentMediaType", literal("application/json"), state),
                (atom, f"{_HSWM}contentByteLength", typed(2), state),
                (atom, f"{_HSWM}contentSha256", literal("4" * 64), evidence),
                (atom, f"{_HSWM}provenanceMode", literal(mode), provenance),
                (atom, f"{_HSWM}evidenceSha256", literal("5" * 64), evidence),
            ]
        )
        if source is not None:
            lines.append((atom, f"{_HSWM}provenanceSource", f"<{source}>", provenance))
    lines.extend(
        [
            (relation, f"{_HSWM}hasTypedReference", f"<{reference}>", state),
            (reference, _RDF_TYPE, f"<{_HSWM}TypedReference>", state),
            (reference, f"{_HSWM}sourceAtom", f"<{relation}>", state),
            (reference, f"{_HSWM}targetAtom", f"<{entity}>", state),
            (reference, f"{_HSWM}referenceType", literal("reference:member"), schema),
            (reference, f"{_HSWM}role", literal("role:member"), schema),
            (reference, f"{_HSWM}ordinal", typed(0), state),
        ]
    )
    return "".join(
        f"<{subject}> <{predicate}> {obj} <{graph}> .\n"
        for subject, predicate, obj, graph in lines
    ).encode()


def _manifest(payload: bytes = NQUADS) -> dict[str, object]:
    return {
        "_tag": "CanonicalAtomV2RdfProjectionManifest",
        "contractVersion": "hswm-canonical-atom-v2-rdf-projection/v1",
        "rdfProfile": "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE",
        "mapping": "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE",
        "dataset": {"mediaType": "application/n-quads", "byteLength": len(payload), "sha256": sha256(payload).hexdigest()},
        "writeBack": "FORBIDDEN",
        "nonclaim": "RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY",
        "invalidatedBy": ["SCHEMA_CONTENT_BINDING_CHANGED", "STATE_DIGEST_CHANGED", "TAIL_DESCRIPTOR_OR_BYTES_CHANGED", "COMPILER_PROFILE_CHANGED"],
        "rdfDatasetOmits": ["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN"],
    }


def test_source_artifact_and_projection_descriptor_are_both_required() -> None:
    with pytest.raises(StandardGraphViewError, match="SHA-256"):
        StandardGraphView.from_projection(projection_dataset_sha256="not-a-digest", projection_manifest=_manifest(), nquads=NQUADS)
    with pytest.raises(StandardGraphViewError, match="does not bind"):
        StandardGraphView.from_projection(projection_dataset_sha256=sha256(NQUADS).hexdigest(), projection_manifest=_manifest(b"other"), nquads=NQUADS)


def test_manifest_cannot_allow_writeback_or_omit_invalidation() -> None:
    manifest = _manifest()
    manifest["writeBack"] = "ALLOWED"
    with pytest.raises(StandardGraphViewError, match="forbid write-back"):
        StandardGraphView.from_projection(projection_dataset_sha256=sha256(NQUADS).hexdigest(), projection_manifest=manifest, nquads=NQUADS)


def test_blank_nodes_are_refused_by_the_declared_projection_profile() -> None:
    try:
        StandardGraphView.from_projection(
            projection_dataset_sha256=sha256(BLANK_NODE_NQUADS).hexdigest(),
            projection_manifest=_manifest(BLANK_NODE_NQUADS),
            nquads=BLANK_NODE_NQUADS,
        )
    except StandardGraphViewDependencyError:
        pytest.skip("RDFLib optional graph implementation is not installed")
    except StandardGraphViewError as error:
        assert "blank nodes are forbidden" in str(error)
    else:
        pytest.fail("blank-node N-Quads was accepted by the blank-node-free profile")
    manifest = _manifest()
    manifest["invalidatedBy"] = []
    with pytest.raises(StandardGraphViewError, match="invalidation"):
        StandardGraphView.from_projection(projection_dataset_sha256=sha256(NQUADS).hexdigest(), projection_manifest=manifest, nquads=NQUADS)


def test_missing_rdflib_is_explicit_not_a_silent_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from hswm.infrastructure import standard_graph_view

    actual = standard_graph_view.importlib.import_module
    def absent(name: str):
        if name == "rdflib":
            raise ModuleNotFoundError("no module", name="rdflib")
        return actual(name)
    monkeypatch.setattr(standard_graph_view.importlib, "import_module", absent)
    with pytest.raises(StandardGraphViewDependencyError, match="RDFLib"):
        StandardGraphView.from_projection(projection_dataset_sha256=sha256(NQUADS).hexdigest(), projection_manifest=_manifest(), nquads=NQUADS)


def test_read_only_query_contract_refuses_every_non_select_ask_form() -> None:
    # This lexical gate runs before RDFLib, so it is independently testable.
    for query in (
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
        "INSERT DATA { <x> <y> <z> }",
        "DESCRIBE <x>",
        "SELECT * FROM <https://remote.example/data> WHERE { ?s ?p ?o }",
        "ASK { SERVICE <https://remote.example/sparql> { ?s ?p ?o } }",
    ):
        with pytest.raises(StandardGraphViewError, match="only SELECT and ASK|remote datasets"):
            # A manually-created instance is safe here: the operation is rejected before dataset access.
            StandardGraphView(None, "0" * 64, {}, ()).query(query)


def test_full_api_when_optional_dependencies_are_available() -> None:
    try:
        view = StandardGraphView.from_projection(projection_dataset_sha256=sha256(NQUADS).hexdigest(), projection_manifest=_manifest(), nquads=NQUADS)
    except StandardGraphViewDependencyError:
        pytest.skip("RDFLib optional graph implementation is not installed")
    assert view.query("ASK { GRAPH ?g { ?s ?p ?o } }") is True
    assert view.query('ASK { ?s ?p "SERVICE FROM is data" }') is False
    assert view.query("SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }") == ({"s": {"kind": "iri", "value": "https://example.test/s"}},)
    assert json.loads(view.expanded_jsonld())
    assert json.loads(view.aliased_jsonld(context={"p": "https://example.test/p"}))["@context"]["p"] == "https://example.test/p"
    provenance = json.loads(view.prov_o_envelope())["@graph"]
    assert provenance[1]["prov:used"]["@id"].startswith("urn:sha256:")
    assert provenance[2]["hswm:writeBack"] == "FORBIDDEN"
    assert provenance[2]["prov:wasGeneratedBy"]["@id"].endswith(":derivation")


def test_mutating_a_disposable_rdflib_dataset_cannot_change_the_view() -> None:
    try:
        view = StandardGraphView.from_projection(
            projection_dataset_sha256=sha256(NQUADS).hexdigest(),
            projection_manifest=_manifest(),
            nquads=NQUADS,
        )
    except StandardGraphViewDependencyError:
        pytest.skip("RDFLib optional graph implementation is not installed")
    disposable = view._load_dataset()
    disposable.parse(
        data=(
            b'<https://attacker.test/s> <https://attacker.test/p> '
            b'<https://attacker.test/o> <https://attacker.test/g> .\n'
        ),
        format="nquads",
    )

    assert view.query(
        "ASK { GRAPH <https://attacker.test/g> { <https://attacker.test/s> ?p ?o } }"
    ) is False
    assert not hasattr(view, "_dataset")


def test_checked_in_shacl_profile_rejects_an_incomplete_dataset() -> None:
    incomplete = (
        b'<https://example.test/dataset> '
        b'<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> '
        b'<https://hswm.invalid/canonical-atom-v2/rdf/v1/vocab/Dataset> '
        b'<https://example.test/state> .\n'
    )
    view = StandardGraphView.from_projection(
        projection_dataset_sha256=sha256(incomplete).hexdigest(),
        projection_manifest=_manifest(incomplete),
        nquads=incomplete,
    )
    shapes = (
        Path(__file__).parents[1]
        / "schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl"
    ).read_bytes()

    report = view.validate_shacl(shapes=shapes)

    assert report["conforms"] is False
    assert report["claim_ceiling"] == view.claim_ceiling


def test_checked_in_shacl_profile_accepts_bootstrap_and_derivation_projection_modes() -> None:
    payload = _valid_hswm_projection_nquads()
    view = StandardGraphView.from_projection(
        projection_dataset_sha256=sha256(payload).hexdigest(),
        projection_manifest=_manifest(payload),
        nquads=payload,
    )
    shapes = (
        Path(__file__).parents[1]
        / "schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl"
    ).read_bytes()

    try:
        report = view.validate_shacl(shapes=shapes)
    except StandardGraphViewDependencyError:
        pytest.skip("PySHACL optional graph implementation is not installed")

    assert report["conforms"] is True
