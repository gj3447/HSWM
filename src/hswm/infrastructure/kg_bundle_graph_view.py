"""Read-only W3C-standard RDF view of an HSWM KG bundle projection.

An HSWM KG bundle (``ontology/identity/hswm_core/*_ONTOLOGY.v*.json``) is a
bounded property-graph projection that is normally published to Neo4j through
its fail-closed upsert script.  This module gives the same bytes a
deterministic, blank-node-free RDF 1.1 N-Quads view so the bundle can be
checked with SHACL 1.0, queried with local read-only SPARQL 1.1, and described
with a constrained PROV-O derivation, without any write path.

It is an interoperability boundary only.  It is not canonical HSWM state, a
Permit, a user ratification, a gate pass, causal credit, learning, or efficacy
evidence, and it cannot publish to or read from the live KG.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any

from .standard_graph_view import (
    StandardGraphViewError,
    _QUERY_HEAD,
    _REMOTE_OR_WRITE_TOKEN,
    _require,
    _sparql_code,
    _term,
)


NQUADS_MEDIA_TYPE = "application/n-quads"
RDF_PROFILE = "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE"
CONTRACT_VERSION = "hswm-kg-bundle-rdf-projection/v1"
COMPILER_ID = "hswm-kg-bundle-rdf-compiler/v1"
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 32
WRITE_BACK = "FORBIDDEN"
NONCLAIM = (
    "DERIVED_READ_ONLY_KG_BUNDLE_EXCHANGE_NOT_CANONICAL_STATE_NOT_PERMIT_NOT_USER_"
    "RATIFICATION_NOT_GATE_PASS_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY"
)
CLAIM_CEILING = (
    "KG_BUNDLE_STRUCTURE_AND_BYTE_BINDING_ONLY_NOT_LIVE_KG_STATE_NOT_PROVENANCE_"
    "TRUTH_NOT_CANONICAL_AUTHORITY_NOT_PERMIT_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_"
    "NOT_LEARNING_NOT_EFFICACY"
)
VOCAB = "https://hswm.invalid/kg-bundle-rdf/v1/"
LABEL_NS = VOCAB + "label/"
ROLE_NS = VOCAB + "role/"
PROP_NS = VOCAB + "prop/"
REL_NS = VOCAB + "rel/"
NODE_IRI_PREFIX = "urn:hswm:kg:node:"
RELATION_IRI_PREFIX = "urn:hswm:kg:relation:"
PROV = "http://www.w3.org/ns/prov#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD = "http://www.w3.org/2001/XMLSchema#"
XSD_INTEGER = XSD + "integer"
XSD_NON_NEGATIVE_INTEGER = XSD + "nonNegativeInteger"
XSD_BOOLEAN = XSD + "boolean"
XSD_DOUBLE = XSD + "double"
ROLE_KEYS = ("standard_graph_role", "plan_graph_role")
TOP_LEVEL_REQUIRED = frozenset(
    {
        "schema_version",
        "bundle_uid",
        "status",
        "nonclaim",
        "artifact_bindings",
        "expected_counts",
        "anchors",
        "nodes",
        "relations",
    }
)
TOP_LEVEL_OPTIONAL = frozenset({"authority_boundary", "source_accessed_on"})
_SOURCE_ID = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UID = re.compile(r"sym:[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_RELATION_TYPE = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_PROPERTY_KEY = re.compile(r"[a-z][a-z0-9_]*\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./:+-]{0,255}\Z")
_FORBIDDEN_PROPERTY_KEYS = frozenset(
    {"password", "secret", "token", "api_key", "apikey", "private_key", "credential"}
)
_CONSTRUCTION_TOKEN = object()


class KgBundleGraphViewError(StandardGraphViewError):
    """A KG bundle projection input or operation was rejected."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _typed(value: str, datatype: str) -> str:
    return f'"{value}"^^<{datatype}>'


def _iri(value: str) -> str:
    return f"<{value}>"


def _duplicate_key_rejected(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise KgBundleGraphViewError(f"bundle has duplicate JSON key: {key}")
        value[key] = item
    return value


def _nonfinite_rejected(value: str) -> None:
    raise KgBundleGraphViewError(f"bundle has non-finite JSON constant: {value}")


def _strict_object(raw_bytes: bytes) -> dict[str, Any]:
    if len(raw_bytes) > MAX_BUNDLE_BYTES:
        raise KgBundleGraphViewError("bundle exceeds byte limit")
    try:
        value = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_duplicate_key_rejected,
            parse_constant=_nonfinite_rejected,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise KgBundleGraphViewError("bundle is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise KgBundleGraphViewError("bundle root must be a JSON object")
    return value


def _scalar(value: Any) -> bool:
    return isinstance(value, (str, bool, int, float)) and not (
        isinstance(value, float) and value != value
    )


def _scalar_object(value: Any) -> str:
    if not _scalar(value):
        raise KgBundleGraphViewError("only scalar values can become RDF literals")
    if isinstance(value, bool):
        return _typed("true" if value else "false", XSD_BOOLEAN)
    if isinstance(value, int):
        return _typed(str(value), XSD_INTEGER)
    if isinstance(value, float):
        return _typed(repr(value), XSD_DOUBLE)
    return _literal(value)


def _frozen(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _frozen(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_frozen(item) for item in value)
    return value


def _validate_bundle(value: Mapping[str, Any]) -> None:
    keys = set(value)
    if not TOP_LEVEL_REQUIRED <= keys or not keys <= TOP_LEVEL_REQUIRED | TOP_LEVEL_OPTIONAL:
        raise KgBundleGraphViewError("bundle top-level shape is outside the HSWM KG bundle contract")
    for key in ("schema_version", "bundle_uid", "status", "nonclaim"):
        if not isinstance(value[key], str) or not value[key]:
            raise KgBundleGraphViewError(f"bundle {key} must be a non-empty string")
    if not _UID.fullmatch(value["bundle_uid"]) or not value["bundle_uid"].startswith(
        "sym:AbstractNode:"
    ):
        raise KgBundleGraphViewError("bundle_uid must be a sym:AbstractNode uid")
    for key in ("authority_boundary", "source_accessed_on"):
        if key in value and (not isinstance(value[key], str) or not value[key]):
            raise KgBundleGraphViewError(f"bundle {key} must be a non-empty string")
    bindings = value["artifact_bindings"]
    if not isinstance(bindings, list) or not bindings:
        raise KgBundleGraphViewError("bundle must declare at least one artifact binding")
    seen_paths: set[str] = set()
    for row in bindings:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"path", "sha256"}
            or not isinstance(row["path"], str)
            or not _TOKEN.fullmatch(row["path"])
            or row["path"].startswith("/")
            or ".." in row["path"].split("/")
            or not isinstance(row["sha256"], str)
            or not _SHA256.fullmatch(row["sha256"])
        ):
            raise KgBundleGraphViewError("artifact binding shape is invalid")
        if row["path"] in seen_paths:
            raise KgBundleGraphViewError(f"duplicate artifact binding: {row['path']}")
        seen_paths.add(row["path"])
    counts = value["expected_counts"]
    if not isinstance(counts, Mapping) or any(
        not _PROPERTY_KEY.fullmatch(str(key)) or type(item) is not int or item < 0
        for key, item in counts.items()
    ):
        raise KgBundleGraphViewError("expected_counts must map property keys to non-negative integers")
    anchors = value["anchors"]
    nodes = value["nodes"]
    relations = value["relations"]
    if not isinstance(anchors, list) or not isinstance(nodes, list) or not isinstance(relations, list):
        raise KgBundleGraphViewError("anchors, nodes, and relations must be arrays")
    if not nodes:
        raise KgBundleGraphViewError("bundle must own at least one node")
    uids: set[str] = set()
    for row in anchors:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"uid", "name", "required_labels"}
            or not isinstance(row["uid"], str)
            or not _UID.fullmatch(row["uid"])
            or not isinstance(row["name"], str)
            or not row["name"]
            or not isinstance(row["required_labels"], list)
            or not row["required_labels"]
            or any(not isinstance(label, str) or not _LABEL.fullmatch(label) for label in row["required_labels"])
        ):
            raise KgBundleGraphViewError("anchor descriptor is invalid")
        if row["uid"] in uids:
            raise KgBundleGraphViewError(f"duplicate uid: {row['uid']}")
        uids.add(row["uid"])
    node_uids: set[str] = set()
    for row in nodes:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"uid", "labels", "properties"}
            or not isinstance(row["uid"], str)
            or not _UID.fullmatch(row["uid"])
            or not isinstance(row["labels"], list)
            or not row["labels"]
            or len(row["labels"]) != len(set(row["labels"]))
            or any(not isinstance(label, str) or not _LABEL.fullmatch(label) for label in row["labels"])
            or not isinstance(row["properties"], Mapping)
        ):
            raise KgBundleGraphViewError("node descriptor is invalid")
        if row["uid"] in uids:
            raise KgBundleGraphViewError(f"duplicate uid: {row['uid']}")
        uids.add(row["uid"])
        node_uids.add(row["uid"])
        properties = row["properties"]
        if not isinstance(properties.get("name"), str) or not properties["name"]:
            raise KgBundleGraphViewError(f"node without a name: {row['uid']}")
        for key, item in properties.items():
            if not isinstance(key, str) or not _PROPERTY_KEY.fullmatch(key):
                raise KgBundleGraphViewError(f"unsafe property key on {row['uid']}: {key}")
            if key in _FORBIDDEN_PROPERTY_KEYS:
                raise KgBundleGraphViewError(f"forbidden property key on {row['uid']}: {key}")
            if not (
                _scalar(item)
                or (isinstance(item, list) and all(_scalar(element) for element in item))
            ):
                raise KgBundleGraphViewError(f"non-scalar property on {row['uid']}: {key}")
        for key in ROLE_KEYS:
            role = properties.get(key)
            if role is not None and (not isinstance(role, str) or not _LABEL.fullmatch(role)):
                raise KgBundleGraphViewError(f"unsafe role token on {row['uid']}: {key}")
    seen_relations: set[tuple[str, str, str]] = set()
    for row in relations:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}
            or any(not isinstance(row[key], str) or not row[key] for key in row)
            or not _RELATION_TYPE.fullmatch(row["type"])
        ):
            raise KgBundleGraphViewError("relation descriptor is invalid")
        if row["from_uid"] not in node_uids:
            raise KgBundleGraphViewError(f"relation must originate from an owned node: {row['from_uid']}")
        if row["to_uid"] not in uids:
            raise KgBundleGraphViewError(f"relation target is neither owned nor anchored: {row['to_uid']}")
        key = (row["from_uid"], row["type"], row["to_uid"])
        if key in seen_relations:
            raise KgBundleGraphViewError(f"duplicate relation: {key}")
        seen_relations.add(key)
    declared = counts
    for key, observed in (("nodes", len(nodes)), ("anchors", len(anchors)), ("relations", len(relations))):
        if key in declared and declared[key] != observed:
            raise KgBundleGraphViewError(f"expected_counts.{key} disagrees with the bundle body")


@dataclass(frozen=True)
class KgBundleSource:
    """One exact HSWM KG bundle file, bound by raw-byte digest and length."""

    source_id: str
    raw_bytes: bytes
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not _SOURCE_ID.fullmatch(self.source_id):
            raise KgBundleGraphViewError("source_id must be a short safe identifier")
        if not isinstance(self.raw_bytes, bytes) or not self.raw_bytes:
            raise KgBundleGraphViewError("raw_bytes must be non-empty bytes")
        if not isinstance(self.sha256, str) or not _SHA256.fullmatch(self.sha256):
            raise KgBundleGraphViewError("sha256 must be 64 lowercase hex characters")
        observed = sha256(self.raw_bytes).hexdigest()
        if observed != self.sha256:
            raise KgBundleGraphViewError("bundle SHA-256 differs from the expected digest")
        if type(self.byte_length) is not int or self.byte_length != len(self.raw_bytes):
            raise KgBundleGraphViewError("bundle byte length differs from the expected length")
        _validate_bundle(_strict_object(self.raw_bytes))

    def bundle(self) -> Mapping[str, Any]:
        return _frozen(_strict_object(self.raw_bytes))


def _node_iri(uid: str) -> str:
    return NODE_IRI_PREFIX + uid


class KgBundleGraphView:
    """Immutable, source-bound RDF exchange view of one or more KG bundles."""

    _nquads: bytes
    descriptor: Mapping[str, Any]
    claim_ceiling: str

    def __init__(self, token: object, nquads: bytes, descriptor: Mapping[str, Any]) -> None:
        if token is not _CONSTRUCTION_TOKEN:
            raise KgBundleGraphViewError("KgBundleGraphView must be built from bound bundle sources")
        if not isinstance(nquads, bytes) or not nquads or not isinstance(descriptor, Mapping):
            raise KgBundleGraphViewError("invalid private projection construction")
        object.__setattr__(self, "_nquads", bytes(nquads))
        object.__setattr__(self, "descriptor", _frozen(dict(descriptor)))
        object.__setattr__(self, "claim_ceiling", CLAIM_CEILING)

    def __setattr__(self, name: str, value: Any) -> None:
        raise KgBundleGraphViewError("KgBundleGraphView is immutable")

    @classmethod
    def from_bundles(cls, *, sources: tuple[KgBundleSource, ...]) -> "KgBundleGraphView":
        if not isinstance(sources, tuple) or not sources:
            raise KgBundleGraphViewError("supply one or more bundle sources as a tuple")
        if any(not isinstance(source, KgBundleSource) for source in sources):
            raise KgBundleGraphViewError("sources must contain only KgBundleSource values")
        if len({source.source_id for source in sources}) != len(sources):
            raise KgBundleGraphViewError("bundle source IDs must be unique")
        if len({source.sha256 for source in sources}) != len(sources):
            raise KgBundleGraphViewError("bundle source SHA-256 values must be unique")
        ordered = tuple(sorted(sources, key=lambda source: source.source_id))
        bundles = [source.bundle() for source in ordered]
        if len({bundle["bundle_uid"] for bundle in bundles}) != len(bundles):
            raise KgBundleGraphViewError("bundle UIDs must be unique across sources")
        owned: dict[str, str] = {}
        for bundle in bundles:
            for row in bundle["nodes"]:
                if row["uid"] in owned:
                    raise KgBundleGraphViewError(f"node owned by two bundles: {row['uid']}")
                owned[row["uid"]] = bundle["bundle_uid"]
        for bundle in bundles:
            for row in bundle["anchors"]:
                if owned.get(row["uid"]) == bundle["bundle_uid"]:
                    raise KgBundleGraphViewError(
                        f"anchor collides with a node owned by the same bundle: {row['uid']}"
                    )

        source_set = [
            {
                "id": source.source_id,
                "mediaType": "application/json",
                "sha256": source.sha256,
                "byteLength": source.byte_length,
                "bundleUid": bundle["bundle_uid"],
            }
            for source, bundle in zip(ordered, bundles)
        ]
        source_set_sha256 = sha256(_canonical_json(source_set)).hexdigest()
        projection_identity_sha256 = sha256(
            _canonical_json(
                {
                    "compilerId": COMPILER_ID,
                    "contractVersion": CONTRACT_VERSION,
                    "rdfProfile": RDF_PROFILE,
                    "sourceSetSha256": source_set_sha256,
                }
            )
        ).hexdigest()
        projection_iri = f"urn:hswm:kg-bundle-projection:{projection_identity_sha256}"
        activity_iri = projection_iri + ":derivation"
        meta_graph = projection_iri + ":metadata"
        provenance_graph = projection_iri + ":provenance"
        lines: list[tuple[str, str, str, str]] = [
            (projection_iri, RDF_TYPE, VOCAB + "Projection", meta_graph),
            (projection_iri, RDF_TYPE, PROV + "Entity", provenance_graph),
            (projection_iri, VOCAB + "contractVersion", _literal(CONTRACT_VERSION), meta_graph),
            (projection_iri, VOCAB + "compilerId", _literal(COMPILER_ID), meta_graph),
            (projection_iri, VOCAB + "rdfProfile", _literal(RDF_PROFILE), meta_graph),
            (projection_iri, VOCAB + "writeBack", _literal(WRITE_BACK), meta_graph),
            (projection_iri, VOCAB + "nonclaim", _literal(NONCLAIM), meta_graph),
            (projection_iri, VOCAB + "claimCeiling", _literal(CLAIM_CEILING), meta_graph),
            (projection_iri, VOCAB + "sourceSetSha256", _literal(source_set_sha256), meta_graph),
            (projection_iri, PROV + "wasGeneratedBy", activity_iri, provenance_graph),
            (activity_iri, RDF_TYPE, PROV + "Activity", provenance_graph),
        ]
        node_count = 0
        relation_count = 0
        for source, bundle in zip(ordered, bundles):
            bundle_iri = f"urn:sha256:{source.sha256}"
            data_graph = f"urn:hswm:kg-bundle:{source.sha256}"
            lines.extend(
                [
                    (bundle_iri, RDF_TYPE, VOCAB + "Bundle", meta_graph),
                    (bundle_iri, RDF_TYPE, PROV + "Entity", provenance_graph),
                    (bundle_iri, VOCAB + "sourceId", _literal(source.source_id), meta_graph),
                    (bundle_iri, VOCAB + "sourceSha256", _literal(source.sha256), meta_graph),
                    (bundle_iri, VOCAB + "sourceByteLength", _typed(str(source.byte_length), XSD_NON_NEGATIVE_INTEGER), meta_graph),
                    (bundle_iri, VOCAB + "mediaType", _literal("application/json"), meta_graph),
                    (bundle_iri, VOCAB + "bundleUid", _literal(bundle["bundle_uid"]), meta_graph),
                    (bundle_iri, VOCAB + "schemaVersion", _literal(bundle["schema_version"]), meta_graph),
                    (bundle_iri, VOCAB + "status", _literal(bundle["status"]), meta_graph),
                    (bundle_iri, VOCAB + "nonclaim", _literal(bundle["nonclaim"]), meta_graph),
                    (bundle_iri, VOCAB + "nodeCount", _typed(str(len(bundle["nodes"])), XSD_NON_NEGATIVE_INTEGER), meta_graph),
                    (bundle_iri, VOCAB + "relationCount", _typed(str(len(bundle["relations"])), XSD_NON_NEGATIVE_INTEGER), meta_graph),
                    (bundle_iri, VOCAB + "anchorCount", _typed(str(len(bundle["anchors"])), XSD_NON_NEGATIVE_INTEGER), meta_graph),
                    (bundle_iri, VOCAB + "dataGraph", data_graph, meta_graph),
                    (activity_iri, PROV + "used", bundle_iri, provenance_graph),
                    (projection_iri, PROV + "wasDerivedFrom", bundle_iri, provenance_graph),
                ]
            )
            for key in ("authority_boundary", "source_accessed_on"):
                if key in bundle:
                    lines.append((bundle_iri, VOCAB + _camel(key), _literal(bundle[key]), meta_graph))
            for key, item in sorted(bundle["expected_counts"].items()):
                lines.append((bundle_iri, VOCAB + "expectedCount/" + key, _typed(str(item), XSD_NON_NEGATIVE_INTEGER), meta_graph))
            for row in bundle["artifact_bindings"]:
                binding_iri = f"urn:sha256:{row['sha256']}"
                lines.extend(
                    [
                        (binding_iri, RDF_TYPE, VOCAB + "ArtifactBinding", meta_graph),
                        (binding_iri, RDF_TYPE, PROV + "Entity", provenance_graph),
                        (binding_iri, VOCAB + "bindingPath", _literal(row["path"]), meta_graph),
                        (binding_iri, VOCAB + "bindingSha256", _literal(row["sha256"]), meta_graph),
                        (bundle_iri, VOCAB + "hasArtifactBinding", binding_iri, meta_graph),
                        (bundle_iri, PROV + "wasDerivedFrom", binding_iri, provenance_graph),
                    ]
                )
            for row in bundle["anchors"]:
                anchor_iri = _node_iri(row["uid"])
                lines.append((bundle_iri, VOCAB + "anchorsTo", anchor_iri, data_graph))
                if row["uid"] in owned:
                    # The anchor is an owned node of another bundle in this same
                    # projection; it is typed once as kb:Node by its owner.
                    continue
                lines.extend(
                    [
                        (anchor_iri, RDF_TYPE, VOCAB + "Anchor", data_graph),
                        (anchor_iri, VOCAB + "uid", _literal(row["uid"]), data_graph),
                        (anchor_iri, VOCAB + "anchorName", _literal(row["name"]), data_graph),
                    ]
                )
                for label in row["required_labels"]:
                    lines.append((anchor_iri, VOCAB + "requiredLabel", _literal(label), data_graph))
            for row in bundle["nodes"]:
                node_count += 1
                node_iri = _node_iri(row["uid"])
                lines.extend(
                    [
                        (node_iri, RDF_TYPE, VOCAB + "Node", data_graph),
                        (node_iri, VOCAB + "uid", _literal(row["uid"]), data_graph),
                        (node_iri, VOCAB + "ownedBy", bundle_iri, data_graph),
                        (bundle_iri, VOCAB + "ownsNode", node_iri, data_graph),
                    ]
                )
                for label in row["labels"]:
                    lines.append((node_iri, RDF_TYPE, LABEL_NS + label, data_graph))
                    lines.append((node_iri, VOCAB + "label", _literal(label), data_graph))
                for key, item in row["properties"].items():
                    predicate = PROP_NS + key
                    if isinstance(item, (list, tuple)):
                        for element in item:
                            lines.append((node_iri, predicate, _scalar_object(element), data_graph))
                        if len(item) > 1:
                            lines.append((node_iri, VOCAB + "propOrder/" + key, _literal(_canonical_json(list(item)).decode("utf-8")), data_graph))
                    else:
                        lines.append((node_iri, predicate, _scalar_object(item), data_graph))
                    if key in ROLE_KEYS:
                        lines.append((node_iri, RDF_TYPE, ROLE_NS + str(item), data_graph))
            for row in bundle["relations"]:
                relation_count += 1
                relation_iri = RELATION_IRI_PREFIX + sha256(_canonical_json(dict(row))).hexdigest()
                from_iri = _node_iri(row["from_uid"])
                to_iri = _node_iri(row["to_uid"])
                lines.extend(
                    [
                        (relation_iri, RDF_TYPE, VOCAB + "Relation", data_graph),
                        (relation_iri, VOCAB + "from", from_iri, data_graph),
                        (relation_iri, VOCAB + "to", to_iri, data_graph),
                        (relation_iri, VOCAB + "relationType", _literal(row["type"]), data_graph),
                        (relation_iri, VOCAB + "authorityClass", _literal(row["authority_class"]), data_graph),
                        (relation_iri, VOCAB + "scope", _literal(row["scope"]), data_graph),
                        (relation_iri, VOCAB + "status", _literal(row["status"]), data_graph),
                        (relation_iri, VOCAB + "ownedBy", bundle_iri, data_graph),
                        (bundle_iri, VOCAB + "ownsRelation", relation_iri, data_graph),
                        (from_iri, REL_NS + row["type"], to_iri, data_graph),
                    ]
                )
        nquads = "".join(
            (
                f"{_iri(subject)} {_iri(predicate)} "
                f"{obj if obj.startswith(chr(34)) else _iri(obj)} "
                f"{_iri(graph)} .\n"
            )
            for subject, predicate, obj, graph in sorted(set(lines))
        ).encode("utf-8")
        dataset_sha256 = sha256(nquads).hexdigest()
        descriptor = {
            "_tag": "HSWMKgBundleRdfProjectionManifest",
            "contractVersion": CONTRACT_VERSION,
            "compilerId": COMPILER_ID,
            "rdfProfile": RDF_PROFILE,
            "mapping": "ROLE_PRESERVING_REIFIED_RELATIONS_WITH_DIRECT_TYPED_EDGES",
            "dataset": {"mediaType": NQUADS_MEDIA_TYPE, "sha256": dataset_sha256, "byteLength": len(nquads)},
            "sources": source_set,
            "sourceSetSha256": source_set_sha256,
            "projectionIdentitySha256": projection_identity_sha256,
            "projectionIri": projection_iri,
            "nodeCount": node_count,
            "relationCount": relation_count,
            "writeBack": WRITE_BACK,
            "nonclaim": NONCLAIM,
            "claimCeiling": CLAIM_CEILING,
            "invalidatedBy": ("ANY_BOUND_BUNDLE_BYTES_CHANGED", "PROJECTION_PROFILE_OR_COMPILER_CHANGED"),
            "rdfDatasetOmits": (
                "LIVE_KG_STATE_AND_PUBLICATION_STATUS",
                "ARTIFACT_BINDING_CONTENT_BYTES",
                "CANONICAL_STATE_AND_PERMIT_CONTENT",
                "CAUSAL_CREDIT_AND_LEARNING_ASSERTIONS",
            ),
        }
        return cls(_CONSTRUCTION_TOKEN, nquads, descriptor)

    @property
    def nquads(self) -> bytes:
        return bytes(self._nquads)

    def _load_union(self) -> Any:
        """Parse the private N-Quads into a fresh union graph; blank nodes fail closed."""
        rdflib = _require("rdflib", "RDFLib")
        dataset = rdflib.Dataset()
        try:
            dataset.parse(data=self._nquads, format="nquads")
        except Exception as error:
            raise KgBundleGraphViewError("RDF 1.1 N-Quads parsing failed") from error
        union = rdflib.Graph()
        for subject, predicate, obj, _graph in dataset.quads((None, None, None, None)):
            if any(isinstance(term, rdflib.BNode) for term in (subject, predicate, obj)):
                raise KgBundleGraphViewError("blank nodes are forbidden by the bundle RDF profile")
            union.add((subject, predicate, obj))
        return union

    def validate_shacl(self, *, shapes: bytes) -> Mapping[str, Any]:
        """Run SHACL 1.0 over the union of the private dataset without write-back."""
        if not isinstance(shapes, bytes) or not shapes:
            raise KgBundleGraphViewError("SHACL shapes must be non-empty bytes")
        pyshacl = _require("pyshacl", "PySHACL")
        rdflib = _require("rdflib", "RDFLib")
        shapes_graph = rdflib.Graph()
        try:
            shapes_graph.parse(data=shapes, format="turtle")
            conforms, _report, text = pyshacl.validate(
                self._load_union(),
                shacl_graph=shapes_graph,
                advanced=False,
                inference="none",
                inplace=False,
                abort_on_first=False,
                meta_shacl=False,
                serialize_report_graph=False,
            )
        except Exception as error:
            raise KgBundleGraphViewError("SHACL 1.0 validation failed") from error
        return MappingProxyType(
            {"conforms": bool(conforms), "report_text": str(text), "claim_ceiling": CLAIM_CEILING}
        )

    def query(self, sparql: str) -> bool | tuple[Mapping[str, Mapping[str, str] | None], ...]:
        """Execute local SPARQL 1.1 SELECT/ASK only over the union graph."""
        if not isinstance(sparql, str) or not sparql.strip() or len(sparql) > 65_536:
            raise KgBundleGraphViewError("SPARQL query must be non-empty text")
        match = _QUERY_HEAD.match(sparql)
        if match is None:
            raise KgBundleGraphViewError("only SELECT and ASK SPARQL 1.1 operations are permitted")
        if _REMOTE_OR_WRITE_TOKEN.search(_sparql_code(sparql)) is not None:
            raise KgBundleGraphViewError("remote datasets, SERVICE, and update keywords are forbidden")
        try:
            result = self._load_union().query(sparql)
        except Exception as error:
            raise KgBundleGraphViewError("read-only SPARQL query failed") from error
        if match.group(1).upper() == "ASK":
            return bool(result.askAnswer)
        variables = tuple(str(variable) for variable in result.vars)
        rows = tuple(
            MappingProxyType(
                {name: None if row.get(name) is None else _term(row.get(name)) for name in variables}
            )
            for row in result
        )
        return tuple(sorted(rows, key=lambda row: _canonical_json({k: dict(v) if v else None for k, v in row.items()})))

    def prov_o_envelope(self) -> bytes:
        """Emit only asserted bundle/dataset derivation; never outcome or causal provenance."""
        projection_iri = self.descriptor["projectionIri"]
        sources = [f"urn:sha256:{item['sha256']}" for item in self.descriptor["sources"]]
        return _canonical_json(
            {
                "@context": {"prov": PROV, "kb": VOCAB},
                "@graph": [
                    {
                        "@id": projection_iri + ":derivation",
                        "@type": "prov:Activity",
                        "prov:used": [{"@id": iri} for iri in sources],
                    },
                    {
                        "@id": projection_iri,
                        "@type": "prov:Entity",
                        "prov:wasDerivedFrom": [{"@id": iri} for iri in sources],
                        "prov:wasGeneratedBy": {"@id": projection_iri + ":derivation"},
                        "kb:datasetSha256": self.descriptor["dataset"]["sha256"],
                        "kb:writeBack": WRITE_BACK,
                        "kb:claimCeiling": CLAIM_CEILING,
                    },
                ],
            }
        )


def _camel(key: str) -> str:
    head, *tail = key.split("_")
    return head + "".join(part.capitalize() for part in tail)
