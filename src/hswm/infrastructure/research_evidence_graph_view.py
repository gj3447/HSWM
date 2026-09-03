"""Read-only RDF exchange view for the G1 opaque public receipt.

This is not the Canonical Atom RDF projection and cannot be used to read or
write HSWM state.  It accepts public receipt bytes, binds their exact raw-byte
digests, and exposes a deliberately small asserted-metadata view for local
SHACL and SPARQL SELECT/ASK inspection.  It is not PROV truth, a Permit,
outcome truth, causal credit, learning evidence, or a trace/telemetry store.
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
    _term,
    _require,
    _sparql_code,
)


NQUADS_MEDIA_TYPE = "application/n-quads"
RDF_PROFILE = "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE"
CONTRACT_VERSION = "hswm-research-evidence-rdf-projection/v1"
COMPILER_ID = "hswm-research-evidence-rdf-compiler/v1"
MAX_PUBLIC_RECEIPT_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 64
WRITE_BACK = "FORBIDDEN"
NONCLAIM = (
    "DERIVED_READ_ONLY_ASSERTED_EVIDENCE_EXCHANGE_NOT_CANONICAL_STATE_NOT_PERMIT_"
    "NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY"
)
CLAIM_CEILING = (
    "PUBLIC_RECEIPT_METADATA_AND_BYTE_BINDING_ONLY_NOT_PROVENANCE_TRUTH_NOT_"
    "CANONICAL_AUTHORITY_NOT_PERMIT_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_"
    "LEARNING_NOT_EFFICACY"
)
VOCAB = "https://hswm.invalid/research-evidence-rdf/v1/"
PROV = "http://www.w3.org/ns/prov#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_INTEGER = "http://www.w3.org/2001/XMLSchema#nonNegativeInteger"
XSD_BOOLEAN = "http://www.w3.org/2001/XMLSchema#boolean"
_SOURCE_ID = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STUDY_UID = re.compile(r"sym:[A-Za-z][A-Za-z0-9._:-]{0,239}\Z")

# These names are never exported, even when nested in the public receipt.  The
# projection is metadata exchange, not a way to launder payloads.
_FORBIDDEN_KEYS = frozenset(
    {
        "action",
        "answer",
        "causal_credit",
        "completion",
        "content",
        "credit",
        "message",
        "outcome",
        "permit",
        "prompt",
        "raw",
        "response",
        "traceparent",
        "tracestate",
    }
)
G1_OPAQUE_PUBLIC_SCHEMA = "hswm-g1-opaque-identifiability-public-redacted-projection/v1"
G1_OPAQUE_RECORD_ROLE = (
    "POST_EXECUTION_AGGREGATE_IDENTIFIABILITY_RESULT_NOT_G0_PROMOTION_OR_G1_EFFICACY"
)
G1_OPAQUE_TERMINAL = "PILOT_COMPLETE_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE"
G1_OPAQUE_SCIENTIFIC_STATUS = (
    "EXPLORATORY_G0_IDENTIFIABILITY_THRESHOLD_OBSERVED_G0_NOT_PASSED_"
    "G1_NOT_EVALUATED"
)
G1_OPAQUE_CLAIM_CEILING = "EXPLORATORY_G0_IDENTIFIABILITY_ONLY"
_CONSTRUCTION_TOKEN = object()
_EXPORTED_ROOT_FIELDS = (
    ("schema_version", "schemaVersion"),
    ("record_role", "recordRole"),
    ("study_uid", "studyUid"),
    ("terminal", "terminal"),
    ("scientific_status", "scientificStatus"),
)


class ResearchEvidenceGraphViewError(StandardGraphViewError):
    """A public-receipt projection input or operation was rejected."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _iri(value: str) -> str:
    return f"<{value}>"


def _walk_forbidden(value: Any) -> None:
    pending = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise ResearchEvidenceGraphViewError("public receipt exceeds JSON depth limit")
        if isinstance(current, Mapping):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ResearchEvidenceGraphViewError(
                        "receipt keys must be strings"
                    )
                if key.lower() in _FORBIDDEN_KEYS:
                    raise ResearchEvidenceGraphViewError(
                        f"receipt contains forbidden payload key: {key}"
                    )
                pending.append((item, depth + 1))
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)


def _duplicate_key_rejected(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ResearchEvidenceGraphViewError(f"public receipt has duplicate JSON key: {key}")
        value[key] = item
    return value


def _nonfinite_rejected(value: str) -> None:
    raise ResearchEvidenceGraphViewError(
        f"public receipt has non-finite JSON constant: {value}"
    )


def _strict_object(raw_bytes: bytes) -> dict[str, Any]:
    if len(raw_bytes) > MAX_PUBLIC_RECEIPT_BYTES:
        raise ResearchEvidenceGraphViewError("public receipt exceeds byte limit")
    try:
        text = raw_bytes.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_key_rejected,
            parse_constant=_nonfinite_rejected,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise ResearchEvidenceGraphViewError("public receipt is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ResearchEvidenceGraphViewError("public receipt root must be a JSON object")
    return value


def _frozen(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _frozen(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_frozen(item) for item in value)
    return value


@dataclass(frozen=True)
class PublicReceiptSource:
    """One exact G1 opaque public receipt; its JSON is never generically flattened."""

    source_id: str
    raw_bytes: bytes
    expected_sha256: str
    expected_byte_length: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_id, str)
            or _SOURCE_ID.fullmatch(self.source_id) is None
        ):
            raise ResearchEvidenceGraphViewError("source_id is not a safe stable identifier")
        if not isinstance(self.raw_bytes, bytes) or not self.raw_bytes:
            raise ResearchEvidenceGraphViewError(
                "public receipt source must be non-empty immutable bytes"
            )
        if len(self.raw_bytes) > MAX_PUBLIC_RECEIPT_BYTES:
            raise ResearchEvidenceGraphViewError("public receipt exceeds byte limit")
        if (
            not isinstance(self.expected_sha256, str)
            or _SHA256.fullmatch(self.expected_sha256) is None
        ):
            raise ResearchEvidenceGraphViewError(
                "expected_sha256 must be a lowercase SHA-256 digest"
            )
        if type(self.expected_byte_length) is not int or self.expected_byte_length < 0:
            raise ResearchEvidenceGraphViewError(
                "expected_byte_length must be a non-negative integer"
            )
        if len(self.raw_bytes) != self.expected_byte_length:
            raise ResearchEvidenceGraphViewError(
                "public receipt byte length differs from expected binding"
            )
        if sha256(self.raw_bytes).hexdigest() != self.expected_sha256:
            raise ResearchEvidenceGraphViewError(
                "public receipt SHA-256 differs from expected binding"
            )
        value = _strict_object(self.raw_bytes)
        _walk_forbidden(value)
        if value.get("schema_version") != G1_OPAQUE_PUBLIC_SCHEMA:
            raise ResearchEvidenceGraphViewError("unsupported public receipt schema")
        for key, _predicate in _EXPORTED_ROOT_FIELDS:
            if not isinstance(value.get(key), str):
                raise ResearchEvidenceGraphViewError(
                    f"public receipt field {key} must be a string"
                )
        boundary = value.get("claim_boundary")
        if not isinstance(boundary, dict):
            raise ResearchEvidenceGraphViewError("public receipt lacks a claim_boundary object")
        if not isinstance(boundary.get("claim_ceiling"), str):
            raise ResearchEvidenceGraphViewError("claim_boundary.claim_ceiling must be a string")
        for key in ("g0_gate_passed", "g1_gate_evaluated"):
            if type(boundary.get(key)) is not bool:
                raise ResearchEvidenceGraphViewError(f"claim_boundary.{key} must be a bool")
            if boundary[key] is not False:
                raise ResearchEvidenceGraphViewError(
                    f"claim_boundary.{key} cannot promote this receipt profile"
                )
        if value["record_role"] != G1_OPAQUE_RECORD_ROLE:
            raise ResearchEvidenceGraphViewError("unsupported public receipt record_role")
        if value["terminal"] != G1_OPAQUE_TERMINAL:
            raise ResearchEvidenceGraphViewError("unsupported public receipt terminal")
        if value["scientific_status"] != G1_OPAQUE_SCIENTIFIC_STATUS:
            raise ResearchEvidenceGraphViewError("unsupported public receipt scientific_status")
        if boundary["claim_ceiling"] != G1_OPAQUE_CLAIM_CEILING:
            raise ResearchEvidenceGraphViewError("unsupported public receipt claim ceiling")
        if _STUDY_UID.fullmatch(value["study_uid"]) is None:
            raise ResearchEvidenceGraphViewError("study_uid is not a bounded sym identifier")

    @property
    def sha256(self) -> str:
        return self.expected_sha256

    @property
    def byte_length(self) -> int:
        return self.expected_byte_length

    def asserted_metadata(self) -> Mapping[str, str | bool]:
        """Return only the explicit scalar allowlist, never arbitrary JSON."""
        value = _strict_object(self.raw_bytes)
        boundary = value["claim_boundary"]
        assert isinstance(boundary, dict)
        return MappingProxyType(
            {
                **{
                    predicate: value[key]
                    for key, predicate in _EXPORTED_ROOT_FIELDS
                },
                "assertedReceiptClaimCeiling": boundary["claim_ceiling"],
                "g0GatePassed": boundary["g0_gate_passed"],
                "g1GateEvaluated": boundary["g1_gate_evaluated"],
            }
        )


@dataclass(frozen=True, init=False)
class ResearchEvidenceGraphView:
    """Immutable, source-bound public-receipt RDF metadata view."""

    _nquads: bytes
    descriptor: Mapping[str, Any]
    mapping_loss: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    def __init__(
        self,
        token: object,
        nquads: bytes,
        descriptor: Mapping[str, Any],
        mapping_loss: tuple[str, ...],
    ) -> None:
        if token is not _CONSTRUCTION_TOKEN:
            raise ResearchEvidenceGraphViewError(
                "ResearchEvidenceGraphView must be built from bound public receipts"
            )
        if not isinstance(nquads, bytes) or not nquads or not isinstance(descriptor, Mapping):
            raise ResearchEvidenceGraphViewError("invalid private projection construction")
        object.__setattr__(self, "_nquads", bytes(nquads))
        object.__setattr__(self, "descriptor", _frozen(dict(descriptor)))
        object.__setattr__(self, "mapping_loss", tuple(mapping_loss))
        object.__setattr__(self, "claim_ceiling", CLAIM_CEILING)

    @classmethod
    def from_public_receipts(
        cls, *, sources: tuple[PublicReceiptSource, ...]
    ) -> "ResearchEvidenceGraphView":
        if not isinstance(sources, tuple) or not sources:
            raise ResearchEvidenceGraphViewError(
                "supply one or more public receipt sources as a tuple"
            )
        if any(not isinstance(source, PublicReceiptSource) for source in sources):
            raise ResearchEvidenceGraphViewError(
                "sources must contain only PublicReceiptSource values"
            )
        if len({source.source_id for source in sources}) != len(sources):
            raise ResearchEvidenceGraphViewError("public receipt source IDs must be unique")
        if len({source.sha256 for source in sources}) != len(sources):
            raise ResearchEvidenceGraphViewError(
                "public receipt source SHA-256 values must be unique"
            )
        ordered = tuple(sorted(sources, key=lambda source: source.source_id))
        source_set = [
            {
                "id": source.source_id,
                "mediaType": "application/json",
                "sha256": source.sha256,
                "byteLength": source.byte_length,
            }
            for source in ordered
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
        projection_iri = (
            "urn:hswm:research-evidence-projection:"
            f"{projection_identity_sha256}"
        )
        activity_iri = projection_iri + ":derivation"
        lines: list[tuple[str, str, str, str]] = []
        meta_graph = projection_iri + ":metadata"
        provenance_graph = projection_iri + ":provenance"
        lines.extend(
            [
                (projection_iri, RDF_TYPE, VOCAB + "EvidenceProjection", meta_graph),
                (projection_iri, RDF_TYPE, PROV + "Entity", provenance_graph),
                (
                    projection_iri,
                    VOCAB + "contractVersion",
                    _literal(CONTRACT_VERSION),
                    meta_graph,
                ),
                (
                    projection_iri,
                    VOCAB + "compilerId",
                    _literal(COMPILER_ID),
                    meta_graph,
                ),
                (projection_iri, VOCAB + "rdfProfile", _literal(RDF_PROFILE), meta_graph),
                (projection_iri, VOCAB + "writeBack", _literal(WRITE_BACK), meta_graph),
                (projection_iri, VOCAB + "nonclaim", _literal(NONCLAIM), meta_graph),
                (projection_iri, VOCAB + "claimCeiling", _literal(CLAIM_CEILING), meta_graph),
                (activity_iri, RDF_TYPE, PROV + "Activity", provenance_graph),
            ]
        )
        for source in ordered:
            source_iri = f"urn:sha256:{source.sha256}"
            lines.extend(
                [
                    (source_iri, RDF_TYPE, VOCAB + "PublicReceipt", meta_graph),
                    (source_iri, RDF_TYPE, PROV + "Entity", provenance_graph),
                    (source_iri, VOCAB + "sourceId", _literal(source.source_id), meta_graph),
                    (source_iri, VOCAB + "sourceSha256", _literal(source.sha256), meta_graph),
                    (
                        source_iri,
                        VOCAB + "sourceByteLength",
                        f'"{source.byte_length}"^^<{XSD_INTEGER}>',
                        meta_graph,
                    ),
                    (source_iri, VOCAB + "mediaType", _literal("application/json"), meta_graph),
                    (activity_iri, PROV + "used", source_iri, provenance_graph),
                    (projection_iri, PROV + "wasDerivedFrom", source_iri, provenance_graph),
                ]
            )
            for predicate, value in sorted(source.asserted_metadata().items()):
                object_value = (
                    f'"{str(value).lower()}"^^<{XSD_BOOLEAN}>'
                    if type(value) is bool
                    else _literal(value)
                )
                lines.append((source_iri, VOCAB + predicate, object_value, meta_graph))
        lines.extend(
            [
                (projection_iri, PROV + "wasGeneratedBy", activity_iri, provenance_graph),
                (
                    projection_iri,
                    VOCAB + "sourceSetSha256",
                    _literal(source_set_sha256),
                    meta_graph,
                ),
            ]
        )
        nquads = "".join(
            (
                f"{_iri(subject)} {_iri(predicate)} "
                f"{obj if obj.startswith(chr(34)) else _iri(obj)} "
                f"{_iri(graph)} .\n"
            )
            for subject, predicate, obj, graph in sorted(lines)
        ).encode("utf-8")
        dataset_sha256 = sha256(nquads).hexdigest()
        descriptor = MappingProxyType(
            {
                "_tag": "HSWMResearchEvidenceRdfProjectionManifest",
                "contractVersion": CONTRACT_VERSION,
                "compilerId": COMPILER_ID,
                "rdfProfile": RDF_PROFILE,
                "mapping": "PUBLIC_RECEIPT_ASSERTED_METADATA_ONLY",
                "dataset": MappingProxyType(
                    {
                        "mediaType": NQUADS_MEDIA_TYPE,
                        "sha256": dataset_sha256,
                        "byteLength": len(nquads),
                    }
                ),
                "sources": tuple(MappingProxyType(item) for item in source_set),
                "sourceSetSha256": source_set_sha256,
                "projectionIdentitySha256": projection_identity_sha256,
                "writeBack": WRITE_BACK,
                "nonclaim": NONCLAIM,
                "invalidatedBy": (
                    "ANY_BOUND_SOURCE_BYTES_CHANGED",
                    "PROJECTION_PROFILE_OR_COMPILER_CHANGED",
                ),
                "rdfDatasetOmits": (
                    "PRIVATE_RAW_TRAFFIC",
                    "TASK_AND_SELECTION_IDENTIFIERS",
                    "PROMPT_AND_COMPLETION_CONTENT",
                    "SECRETS_AND_COMMITMENT_PREIMAGES",
                    "CANONICAL_STATE_AND_PERMIT_CONTENT",
                    "CAUSAL_CREDIT_AND_LEARNING_ASSERTIONS",
                    "TRACE_CONTEXT_AND_TELEMETRY_PAYLOADS",
                ),
            }
        )
        return cls(
            _CONSTRUCTION_TOKEN,
            nquads,
            descriptor,
            tuple(descriptor["rdfDatasetOmits"]),
        )

    @property
    def nquads(self) -> bytes:
        return bytes(self._nquads)

    def _load_dataset(self) -> Any:
        rdflib = _require("rdflib", "RDFLib")
        dataset = rdflib.Dataset()
        try:
            dataset.parse(data=self._nquads, format="nquads")
        except Exception as error:
            raise ResearchEvidenceGraphViewError("RDF 1.1 N-Quads parsing failed") from error
        for quad in dataset.quads((None, None, None, None)):
            if any(isinstance(term, rdflib.BNode) for term in quad):
                raise ResearchEvidenceGraphViewError(
                    "blank nodes are forbidden by the receipt RDF profile"
                )
        return dataset

    def validate_shacl(self, *, shapes: bytes) -> Mapping[str, Any]:
        """Run SHACL 1.0 over a fresh private dataset without any write-back."""
        if not isinstance(shapes, bytes) or not shapes:
            raise ResearchEvidenceGraphViewError("SHACL shapes must be non-empty bytes")
        pyshacl = _require("pyshacl", "PySHACL")
        rdflib = _require("rdflib", "RDFLib")
        graph = rdflib.Graph()
        try:
            graph.parse(data=shapes, format="turtle")
            conforms, _report, text = pyshacl.validate(
                self._load_dataset(),
                shacl_graph=graph,
                advanced=False,
                inference="none",
                inplace=False,
                abort_on_first=False,
                meta_shacl=False,
                serialize_report_graph=False,
            )
        except Exception as error:
            raise ResearchEvidenceGraphViewError("SHACL 1.0 validation failed") from error
        return MappingProxyType(
            {
                "conforms": bool(conforms),
                "report_text": str(text),
                "claim_ceiling": CLAIM_CEILING,
            }
        )

    def query(
        self, sparql: str
    ) -> bool | tuple[Mapping[str, Mapping[str, str] | None], ...]:
        """Execute local SPARQL 1.1 SELECT/ASK only; remote and write forms fail closed."""
        if not isinstance(sparql, str) or not sparql.strip() or len(sparql) > 65_536:
            raise ResearchEvidenceGraphViewError("SPARQL query must be non-empty text")
        match = _QUERY_HEAD.match(sparql)
        if match is None:
            raise ResearchEvidenceGraphViewError(
                "only SELECT and ASK SPARQL 1.1 operations are permitted"
            )
        if _REMOTE_OR_WRITE_TOKEN.search(_sparql_code(sparql)) is not None:
            raise ResearchEvidenceGraphViewError(
                "remote datasets, SERVICE, and update keywords are forbidden"
            )
        try:
            result = self._load_dataset().query(sparql)
        except Exception as error:
            raise ResearchEvidenceGraphViewError("read-only SPARQL query failed") from error
        if match.group(1).upper() == "ASK":
            return bool(result.askAnswer)
        variables = tuple(str(variable) for variable in result.vars)
        return tuple(
            MappingProxyType(
                {
                    name: None if row.get(name) is None else _term(row.get(name))
                    for name in variables
                }
            )
            for row in result
        )

    def prov_o_envelope(self) -> bytes:
        """Emit only asserted source/dataset derivation, never outcome or causal provenance."""
        dataset = self.descriptor["dataset"]
        assert isinstance(dataset, Mapping)
        digest = dataset["sha256"]
        projection_identity_sha = self.descriptor["projectionIdentitySha256"]
        assert isinstance(digest, str) and _SHA256.fullmatch(digest)
        assert isinstance(projection_identity_sha, str) and _SHA256.fullmatch(
            projection_identity_sha
        )
        projection_iri = (
            "urn:hswm:research-evidence-projection:"
            f"{projection_identity_sha}"
        )
        return _canonical_json(
            {
                "@context": {"prov": PROV, "re": VOCAB},
                "@graph": [
                    {
                        "@id": projection_iri + ":derivation",
                        "@type": "prov:Activity",
                        "prov:used": [
                            {"@id": f"urn:sha256:{item['sha256']}"}
                            for item in self.descriptor["sources"]
                        ],
                    },
                    {
                        "@id": projection_iri,
                        "@type": "prov:Entity",
                        "prov:wasDerivedFrom": [
                            {"@id": f"urn:sha256:{item['sha256']}"}
                            for item in self.descriptor["sources"]
                        ],
                        "prov:wasGeneratedBy": {
                            "@id": projection_iri + ":derivation"
                        },
                        "re:datasetSha256": digest,
                        "re:writeBack": WRITE_BACK,
                        "re:claimCeiling": CLAIM_CEILING,
                    },
                ],
            }
        )
