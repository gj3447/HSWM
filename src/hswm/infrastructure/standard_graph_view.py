"""Fail-closed, read-only standard RDF views of an HSWM projection.

This is an interoperability boundary, not an HSWM graph store.  It accepts an
already-produced canonical projection only after checking the projection's
dataset descriptor against caller-supplied source bytes.  It deliberately has
no writer, update, Permit, causal-credit, or learning API.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence


NQUADS_MEDIA_TYPE = "application/n-quads"
WRITE_BACK_FORBIDDEN = "FORBIDDEN"
RDF_PROJECTION_CONTRACT = "hswm-canonical-atom-v2-rdf-projection/v1"
RDF_PROJECTION_PROFILE = "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE"
RDF_PROJECTION_MAPPING = "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE"
SPARQL_PROFILE = "SPARQL_1_1_LOCAL_SELECT_ASK_NO_REMOTE_DATASET_OR_SERVICE"
CLAIM_CEILING = (
    "READ_ONLY_DERIVED_RDF_VIEW_NOT_CANONICAL_ADMISSION_PERMIT_CAUSAL_CREDIT_"
    "LEARNING_OR_EFFICACY_EVIDENCE"
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_QUERY_HEAD = re.compile(
    r"\A\s*(?:(?:#.*\n)|(?:BASE\s+<[^>]*>\s*)|(?:PREFIX\s+[^\s:]*:\s*<[^>]*>\s*))*"
    r"(SELECT|ASK)\b",
    re.IGNORECASE,
)
_REMOTE_OR_WRITE_TOKEN = re.compile(
    r"\b(?:SERVICE|FROM|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD|WITH|USING|INSERT|DELETE)\b",
    re.IGNORECASE,
)


class StandardGraphViewError(RuntimeError):
    """A source, binding, query, or view boundary was rejected."""


class StandardGraphViewDependencyError(StandardGraphViewError):
    """An optional, independently-qualified graph implementation is absent."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require(module: str, package: str) -> Any:
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError as error:
        if error.name == module.split(".")[0]:
            raise StandardGraphViewDependencyError(
                f"{package} is required for this standard RDF view; install the source-pinned optional dependency and qualify it before use"
            ) from error
        raise


def _read_bytes(*, nquads: bytes | None, nquads_path: str | Path | None) -> bytes:
    if (nquads is None) == (nquads_path is None):
        raise StandardGraphViewError("supply exactly one of nquads or nquads_path")
    if nquads is not None:
        if not isinstance(nquads, bytes):
            raise StandardGraphViewError("nquads must be immutable bytes")
        return bytes(nquads)
    path = Path(nquads_path)  # type: ignore[arg-type]
    if not path.is_file():
        raise StandardGraphViewError("N-Quads path is not a regular readable file")
    return path.read_bytes()


def _validate_binding(manifest: Mapping[str, Any], dataset_sha256: str, source_bytes: bytes) -> None:
    if not isinstance(manifest, Mapping):
        raise StandardGraphViewError("projection_manifest must be a mapping")
    if not isinstance(dataset_sha256, str) or _SHA256.fullmatch(dataset_sha256) is None:
        raise StandardGraphViewError("projection_dataset_sha256 must be a lowercase SHA-256 digest")
    observed = sha256(source_bytes).hexdigest()
    if observed != dataset_sha256:
        raise StandardGraphViewError("projection dataset SHA-256 does not describe supplied N-Quads bytes")
    if (
        manifest.get("_tag") != "CanonicalAtomV2RdfProjectionManifest"
        or manifest.get("contractVersion") != RDF_PROJECTION_CONTRACT
        or manifest.get("rdfProfile") != RDF_PROJECTION_PROFILE
        or manifest.get("mapping") != RDF_PROJECTION_MAPPING
    ):
        raise StandardGraphViewError("projection manifest is outside the exact HSWM RDF v1 profile")
    descriptor = manifest.get("dataset")
    if not isinstance(descriptor, Mapping):
        raise StandardGraphViewError("projection manifest lacks an exact dataset descriptor")
    if descriptor.get("mediaType") != NQUADS_MEDIA_TYPE:
        raise StandardGraphViewError("projection manifest is not bound to application/n-quads")
    if descriptor.get("sha256") != dataset_sha256 or descriptor.get("byteLength") != len(source_bytes):
        raise StandardGraphViewError("projection manifest dataset descriptor does not bind these bytes")
    if manifest.get("writeBack") != WRITE_BACK_FORBIDDEN:
        raise StandardGraphViewError("projection manifest must explicitly forbid write-back")
    nonclaim = manifest.get("nonclaim")
    if not isinstance(nonclaim, str) or "RDF_PROJECTION_ONLY" not in nonclaim:
        raise StandardGraphViewError("projection manifest lacks the RDF-only claim boundary")
    invalidated_by = manifest.get("invalidatedBy")
    if (
        not isinstance(invalidated_by, Sequence)
        or isinstance(invalidated_by, (str, bytes))
        or any(not isinstance(item, str) for item in invalidated_by)
    ):
        raise StandardGraphViewError("projection manifest lacks a source-invalidation contract")
    required = {
        "SCHEMA_CONTENT_BINDING_CHANGED",
        "STATE_DIGEST_CHANGED",
        "TAIL_DESCRIPTOR_OR_BYTES_CHANGED",
        "COMPILER_PROFILE_CHANGED",
    }
    if not required.issubset(set(invalidated_by)):
        raise StandardGraphViewError("projection manifest invalidation contract is insufficient")


def _parse_dataset(source_bytes: bytes) -> Any:
    """Parse one fresh private dataset and enforce the declared RDF profile."""
    rdflib = _require("rdflib", "RDFLib")
    dataset = rdflib.Dataset()
    try:
        dataset.parse(data=source_bytes, format="nquads")
    except Exception as error:
        raise StandardGraphViewError("RDF 1.1 N-Quads parsing failed") from error
    for subject, predicate, obj, graph in dataset.quads((None, None, None, None)):
        if any(
            isinstance(term, rdflib.BNode)
            for term in (subject, predicate, obj, graph)
        ):
            raise StandardGraphViewError(
                "blank nodes are forbidden by the exact HSWM RDF projection profile"
            )
    return dataset


def _sparql_code(query: str) -> str:
    """Blank comments, strings, and IRIs before checking dangerous keywords."""
    output = list(query)
    index = 0
    while index < len(query):
        character = query[index]
        if character == "#":
            end = query.find("\n", index)
            end = len(query) if end < 0 else end
            output[index:end] = " " * (end - index)
            index = end
            continue
        if character == "<":
            iri = re.match(r"<[^\s<>]*>", query[index:])
            if iri is not None:
                end = index + len(iri.group(0))
                output[index:end] = " " * (end - index)
                index = end
                continue
        if character in {'"', "'"}:
            delimiter = character * (3 if query.startswith(character * 3, index) else 1)
            end = index + len(delimiter)
            escaped = False
            while end < len(query):
                if query.startswith(delimiter, end) and not escaped:
                    end += len(delimiter)
                    break
                current = query[end]
                escaped = current == "\\" and not escaped
                if current != "\\":
                    escaped = False
                end += 1
            output[index:end] = " " * (end - index)
            index = end
            continue
        index += 1
    return "".join(output)


def _term(term: Any) -> Mapping[str, str]:
    """A deterministic, JSON-safe RDF term representation."""
    rdflib = _require("rdflib", "RDFLib")
    if isinstance(term, rdflib.URIRef):
        return MappingProxyType({"kind": "iri", "value": str(term)})
    if isinstance(term, rdflib.BNode):
        return MappingProxyType({"kind": "blank_node", "value": str(term)})
    if isinstance(term, rdflib.Literal):
        result = {"kind": "literal", "value": str(term)}
        if term.language is not None:
            result["language"] = str(term.language)
        elif term.datatype is not None:
            result["datatype"] = str(term.datatype)
        return MappingProxyType(result)
    raise StandardGraphViewError("RDF-star and unknown terms are outside this RDF 1.1 view contract")


def _jsonld_object(term: Any) -> dict[str, str]:
    item = dict(_term(term))
    if item["kind"] in {"iri", "blank_node"}:
        return {"@id": item["value"]}
    result: dict[str, str] = {"@value": item["value"]}
    if "language" in item:
        result["@language"] = item["language"]
    if "datatype" in item:
        result["@type"] = item["datatype"]
    return result


def _nodes(quads: Sequence[tuple[Any, Any, Any]], graph_id: str | None) -> list[dict[str, Any]]:
    by_subject: dict[str, dict[str, list[dict[str, str]]]] = {}
    for subject, predicate, obj in quads:
        if not isinstance(predicate, _require("rdflib", "RDFLib").URIRef):
            raise StandardGraphViewError("non-IRI predicate is outside RDF 1.1 JSON-LD export")
        subject_id = _jsonld_object(subject)["@id"]
        by_subject.setdefault(subject_id, {}).setdefault(str(predicate), []).append(_jsonld_object(obj))
    result: list[dict[str, Any]] = []
    for subject_id in sorted(by_subject):
        node: dict[str, Any] = {"@id": subject_id}
        for predicate in sorted(by_subject[subject_id]):
            node[predicate] = sorted(by_subject[subject_id][predicate], key=lambda value: _canonical_json(value))
        result.append(node)
    return result


@dataclass(frozen=True)
class StandardGraphView:
    """Immutable source bytes that create a fresh private RDFLib Dataset per operation."""

    _nquads: bytes
    projection_dataset_sha256: str
    projection_manifest: Mapping[str, Any]
    mapping_loss: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    @classmethod
    def from_projection(
        cls,
        *,
        projection_dataset_sha256: str,
        projection_manifest: Mapping[str, Any],
        nquads: bytes | None = None,
        nquads_path: str | Path | None = None,
    ) -> "StandardGraphView":
        """Parse a source-bound RDF 1.1 N-Quads projection without retaining a writer."""
        source_bytes = _read_bytes(nquads=nquads, nquads_path=nquads_path)
        _validate_binding(projection_manifest, projection_dataset_sha256, source_bytes)
        _parse_dataset(source_bytes)
        omitted = projection_manifest.get("rdfDatasetOmits", ())
        if (
            not isinstance(omitted, Sequence)
            or isinstance(omitted, (str, bytes))
            or any(not isinstance(item, str) for item in omitted)
        ):
            raise StandardGraphViewError("projection manifest lacks an explicit RDF mapping-loss declaration")
        return cls(
            _nquads=source_bytes,
            projection_dataset_sha256=projection_dataset_sha256,
            projection_manifest=_freeze(dict(projection_manifest)),
            mapping_loss=tuple(sorted(omitted)),
        )

    def _load_dataset(self) -> Any:
        """Return a disposable dataset so caller mutation cannot alter this view."""
        return _parse_dataset(self._nquads)

    def validate_shacl(
        self, *, shapes: bytes, shapes_format: str = "turtle"
    ) -> Mapping[str, Any]:
        """Validate the private dataset with SHACL 1.0; never modify either graph."""
        if not isinstance(shapes, bytes) or not shapes:
            raise StandardGraphViewError("shapes must be non-empty immutable bytes")
        if shapes_format not in {"turtle", "nquads"}:
            raise StandardGraphViewError("SHACL shapes format must be turtle or nquads")
        pyshacl = _require("pyshacl", "PySHACL")
        rdflib = _require("rdflib", "RDFLib")
        shapes_graph = rdflib.Graph()
        try:
            shapes_graph.parse(data=shapes, format=shapes_format)
            conforms, _results_graph, results_text = pyshacl.validate(
                self._load_dataset(), shacl_graph=shapes_graph, advanced=False, inference="none", inplace=False,
                abort_on_first=False, meta_shacl=False, serialize_report_graph=False,
            )
        except Exception as error:
            raise StandardGraphViewError("SHACL 1.0 validation failed") from error
        return _freeze({"conforms": bool(conforms), "report_text": str(results_text), "claim_ceiling": self.claim_ceiling})

    def query(self, sparql: str) -> bool | tuple[Mapping[str, Mapping[str, str] | None], ...]:
        """Execute only SPARQL 1.1 SELECT or ASK; updates and graph construction are refused."""
        if not isinstance(sparql, str) or not sparql.strip() or len(sparql) > 65_536:
            raise StandardGraphViewError("SPARQL query must be non-empty text")
        match = _QUERY_HEAD.match(sparql)
        if match is None:
            raise StandardGraphViewError("only SELECT and ASK SPARQL 1.1 operations are permitted")
        if _REMOTE_OR_WRITE_TOKEN.search(_sparql_code(sparql)) is not None:
            raise StandardGraphViewError(
                "remote datasets, SERVICE, and update keywords are forbidden"
            )
        operation = match.group(1).upper()
        try:
            result = self._load_dataset().query(sparql)
        except Exception as error:
            raise StandardGraphViewError("read-only SPARQL query failed") from error
        if operation == "ASK":
            return bool(result.askAnswer)
        variables = tuple(str(variable) for variable in result.vars)
        rows: list[Mapping[str, Mapping[str, str] | None]] = []
        for row in result:
            values = {name: None if row.get(name) is None else _term(row.get(name)) for name in variables}
            rows.append(MappingProxyType(values))
        return tuple(rows)

    def expanded_jsonld(self) -> bytes:
        """Return deterministic expanded JSON-LD 1.1 bytes, preserving named graphs."""
        dataset = self._load_dataset()
        default_id = dataset.default_graph.identifier
        default_quads: list[tuple[Any, Any, Any]] = []
        named: dict[str, list[tuple[Any, Any, Any]]] = {}
        for subject, predicate, obj, graph in dataset.quads((None, None, None, None)):
            if graph == default_id:
                default_quads.append((subject, predicate, obj))
            else:
                named.setdefault(str(graph), []).append((subject, predicate, obj))
        graph_items: list[dict[str, Any]] = _nodes(default_quads, None)
        for graph_id in sorted(named):
            graph_items.append({"@graph": _nodes(named[graph_id], graph_id), "@id": graph_id})
        return _canonical_json(graph_items)

    def aliased_jsonld(self, *, context: Mapping[str, str]) -> bytes:
        """Return a deterministic local alias view, not generic JSON-LD compaction.

        The separately source-pinned Effect adapter runs the JSON-LD 1.1
        FromRDF and Compaction algorithms.  This Python helper only rewrites
        exact property IRIs and therefore carries a deliberately narrower name.
        """
        if not isinstance(context, Mapping) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in context.items()):
            raise StandardGraphViewError("JSON-LD context must be a string-to-IRI mapping; remote contexts are forbidden")
        inverse: dict[str, str] = {}
        for alias, iri in sorted(context.items()):
            inverse.setdefault(iri, alias)
        expanded = json.loads(self.expanded_jsonld())
        def compact(value: Any) -> Any:
            if isinstance(value, list):
                return [compact(item) for item in value]
            if not isinstance(value, dict):
                return value
            result: dict[str, Any] = {}
            for key, item in value.items():
                compact_key = inverse.get(key, key)
                result[compact_key] = compact(item)
            return result
        return _canonical_json({"@context": dict(sorted(context.items())), "@graph": compact(expanded)})

    def prov_o_envelope(self) -> bytes:
        """Emit a constrained PROV-O exchange envelope, not causal or admission provenance."""
        source = f"urn:sha256:{self.projection_dataset_sha256}"
        view = f"urn:hswm:standard-graph-view:{self.projection_dataset_sha256}"
        activity = f"{view}:derivation"
        return _canonical_json({
            "@context": {
                "hswm": "https://hswm.invalid/vocab/standard-graph-view/",
                "prov": "http://www.w3.org/ns/prov#",
            },
            "@graph": [
                {"@id": source, "@type": "prov:Entity", "hswm:mediaType": NQUADS_MEDIA_TYPE},
                {"@id": activity, "@type": "prov:Activity", "prov:used": {"@id": source}},
                {"@id": view, "@type": "prov:Entity",
                 "prov:wasDerivedFrom": {"@id": source},
                 "prov:wasGeneratedBy": {"@id": activity},
                 "hswm:claimCeiling": self.claim_ceiling,
                 "hswm:mappingLoss": list(self.mapping_loss),
                 "hswm:writeBack": WRITE_BACK_FORBIDDEN},
            ],
        })
