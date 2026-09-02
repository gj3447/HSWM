#!/usr/bin/env python3
"""Qualify a deliberately read-only SPARQL 1.1 SELECT/ASK adapter.

This is an experimental engineering runner, not a canonical HSWM graph writer,
Permit path, provenance authority, learning path, or a universal SPARQL
conformance claim.  It consumes only a detached checkout of the official W3C
``rdf-tests`` repository at the commit recorded below.  The root manifest is
walked through its own ``mf:include`` lists; no hand-maintained list of tests is
used to inflate a pass count.

The profile has a narrow adapter contract: parse SELECT/ASK query syntax and
evaluate SELECT/ASK over caller-supplied local RDF data.  Updates, CONSTRUCT,
DESCRIBE, SERVICE/federation, protocol/graph-store cases, and entailment are
reported as exclusions, never successes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any, Iterable
from urllib.parse import unquote, urlparse

import rdflib
from rdflib import Dataset, Graph, RDF, URIRef
from rdflib.collection import Collection
from rdflib.namespace import Namespace
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.query import Result


SCHEMA = "hswm-sparql11-readonly-qualification/v1"
RDF_TESTS_REPOSITORY = "https://github.com/w3c/rdf-tests.git"
RDF_TESTS_COMMIT = "369a90d1a60c021b746df2e411da0ff36258a758"
PROFILES = {
    "sparql11-readonly-diagnostic": {
        "selected_root": "sparql/sparql11", "root_manifest": "manifest-all.ttl",
        "allowed_manifest_directories": None,
    },
    "sparql11-rdflib-hswm-basic": {
        "selected_root": "sparql/sparql10", "root_manifest": "manifest-evaluation.ttl",
        "allowed_manifest_directories": frozenset({"basic", "triple-match", "graph", "ask"}),
    },
}
MF = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#")
QT = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/test-query#")
DAWGT = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/test-dawg#")
SPARQL = Namespace("http://www.w3.org/ns/sparql#")
RS = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/result-set#")
QUERY_EVALUATION = MF.QueryEvaluationTest
POSITIVE_SYNTAX = MF.PositiveSyntaxTest11
NEGATIVE_SYNTAX = MF.NegativeSyntaxTest11
_QUERY_FORM = re.compile(r"^\s*(?:BASE\s+<[^>]*>\s+|PREFIX\s+[^\s:]*:\s*<[^>]*>\s+)*(SELECT|ASK|CONSTRUCT|DESCRIBE)\b", re.I | re.S)
_SERVICE = re.compile(r"\bSERVICE\b", re.I)


class QualificationError(RuntimeError):
    """A source pin or local qualification precondition was violated."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git(checkout: Path, *arguments: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise QualificationError(f"pinned source checkout verification failed: {arguments}") from error


def _verify_checkout(checkout: Path, profile: dict[str, object]) -> dict[str, str]:
    checkout = checkout.resolve(strict=True)
    if not (checkout / ".git").exists():
        raise QualificationError("--suite-checkout must be a detached official rdf-tests git checkout")
    if _git(checkout, "rev-parse", "HEAD") != RDF_TESTS_COMMIT:
        raise QualificationError("rdf-tests commit drift")
    selected_root = str(profile["selected_root"])
    selected = checkout / selected_root
    if not selected.is_dir():
        raise QualificationError(f"missing selected root: {selected_root}")
    dirty = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all", "--", selected_root)
    if dirty:
        raise QualificationError("selected official test tree is dirty")
    return {
        "commit": RDF_TESTS_COMMIT,
        "repository": RDF_TESTS_REPOSITORY,
        "selected_root": selected_root,
        "root_manifest_sha256": _sha256(selected / str(profile["root_manifest"])),
        "selected_tree_sha1": _git(checkout, "rev-parse", f"HEAD:{selected_root}"),
        "selected_archive_sha256": sha256(
            subprocess.run(
                ["git", "-C", str(checkout), "archive", "--format=tar", "HEAD", "--", selected_root],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout
        ).hexdigest(),
    }


def _local_path(root: Path, uri: object) -> Path:
    if not isinstance(uri, URIRef) or not str(uri).startswith("file:"):
        raise QualificationError(f"manifest path is not a local file URI: {uri!r}")
    parsed = urlparse(str(uri))
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise QualificationError(f"manifest path is not a local file URI: {uri!r}")
    path = Path(unquote(parsed.path)).resolve(strict=True)
    if root not in path.parents and path != root:
        raise QualificationError(f"manifest path escapes selected root: {path}")
    return path


def _manifest_graph(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def _walk_manifests(root: Path, profile: dict[str, object]) -> tuple[list[tuple[Path, Graph]], Counter[str]]:
    pending = [root / str(profile["root_manifest"])]
    seen: set[Path] = set()
    result: list[tuple[Path, Graph]] = []
    excluded = Counter()
    allowed = profile["allowed_manifest_directories"]
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        graph = _manifest_graph(path)
        result.append((path, graph))
        for manifest in graph.subjects(RDF.type, MF.Manifest):
            for include_head in graph.objects(manifest, MF.include):
                for include in Collection(graph, include_head):
                    include_path = _local_path(root, include)
                    relative = include_path.relative_to(root)
                    if allowed is not None and path == root / str(profile["root_manifest"]) and relative.parts[0] not in allowed:
                        # Count the official manifest's entries as excluded
                        # capability surface, rather than pretending they passed.
                        include_graph = _manifest_graph(include_path)
                        entry_count = sum(
                            len(list(Collection(include_graph, entries)))
                            for owner in include_graph.subjects(RDF.type, MF.Manifest)
                            for entries in include_graph.objects(owner, MF.entries)
                        )
                        excluded["PROFILE_MANIFEST_NOT_SELECTED"] += entry_count
                        continue
                    pending.append(include_path)
    return sorted(result, key=lambda item: item[0].as_posix()), excluded


def _query_form(query: Path) -> str | None:
    match = _QUERY_FORM.search(query.read_text(encoding="utf-8"))
    return match.group(1).upper() if match else None


def _term_key(value: object) -> tuple[str, str, str]:
    """Strict lexical RDF-term key; blank-node labels intentionally stay visible."""
    if isinstance(value, rdflib.Literal):
        return ("literal", str(value.datatype or ""), value.n3())
    if isinstance(value, rdflib.URIRef):
        return ("iri", "", str(value))
    if isinstance(value, rdflib.BNode):
        return ("blank-node", "", str(value))
    raise QualificationError(f"unsupported SPARQL result term: {value!r}")


def _select_bindings(result: Result) -> tuple[frozenset[str], Counter[tuple[tuple[str, tuple[str, str, str]], ...]]]:
    if result.type != "SELECT":
        raise QualificationError(f"expected SELECT result, got {result.type!r}")
    variables = frozenset(str(variable) for variable in result.vars)
    rows: Counter[tuple[tuple[str, tuple[str, str, str]], ...]] = Counter()
    for binding in result.bindings:
        rows[tuple(sorted(
            (str(variable), _term_key(value))
            for variable, value in binding.items()
            if value is not None
        ))] += 1
    return variables, rows


def _select_equal(actual: Result, expected: Result) -> bool:
    """Compare result multisets strictly, modulo one global blank-node bijection.

    Result-set RDF serializations may assign fresh labels to source blank nodes.
    Labels therefore cannot be compared literally, but their identity and reuse
    across every solution must still be preserved.
    """
    actual_variables, actual_rows = _select_bindings(actual)
    expected_variables, expected_rows = _select_bindings(expected)
    if actual_variables != expected_variables or sum(actual_rows.values()) != sum(expected_rows.values()):
        return False
    if not any(isinstance(value, rdflib.BNode) for row in actual.bindings + expected.bindings for value in row.values() if value is not None):
        return actual_rows == expected_rows
    actual_rows_raw = [dict(row) for row in actual.bindings]
    expected_rows_raw = [dict(row) for row in expected.bindings]

    def compatible(left: dict[object, object], right: dict[object, object], forward: dict[object, object], reverse: dict[object, object]) -> tuple[dict[object, object], dict[object, object]] | None:
        if set(left) != set(right):
            return None
        next_forward, next_reverse = dict(forward), dict(reverse)
        for variable, left_value in left.items():
            right_value = right[variable]
            if left_value is None or right_value is None:
                if left_value is not right_value:
                    return None
            elif isinstance(left_value, rdflib.BNode) and isinstance(right_value, rdflib.BNode):
                if next_forward.get(left_value, right_value) != right_value or next_reverse.get(right_value, left_value) != left_value:
                    return None
                next_forward[left_value] = right_value
                next_reverse[right_value] = left_value
            elif isinstance(left_value, rdflib.BNode) or isinstance(right_value, rdflib.BNode) or _term_key(left_value) != _term_key(right_value):
                return None
        return next_forward, next_reverse

    def search(index: int, remaining: list[dict[object, object]], forward: dict[object, object], reverse: dict[object, object]) -> bool:
        if index == len(actual_rows_raw):
            return not remaining
        for candidate_index, candidate in enumerate(remaining):
            mapping = compatible(actual_rows_raw[index], candidate, forward, reverse)
            if mapping is not None and search(index + 1, remaining[:candidate_index] + remaining[candidate_index + 1:], *mapping):
                return True
        return False

    return search(0, expected_rows_raw, {}, {})


def _parse_expected(path: Path) -> Result:
    suffix_to_format = {".srx": "xml", ".srj": "json", ".csv": "csv", ".tsv": "tsv", ".ttl": "turtle"}
    try:
        if path.suffix.lower() == ".ttl":
            graph = Graph().parse(path, format="turtle")
            result_set = next(graph.subjects(RDF.type, RS.ResultSet), None)
            if result_set is None:
                raise QualificationError("Turtle expected result has no DAWG ResultSet")
            result = Result("SELECT")
            result.vars = [rdflib.Variable(str(value)) for value in graph.objects(result_set, RS.resultVariable)]
            bindings = []
            for solution in graph.objects(result_set, RS.solution):
                binding: dict[rdflib.Variable, object] = {}
                for row in graph.objects(solution, RS.binding):
                    variable = graph.value(row, RS.variable)
                    value = graph.value(row, RS.value)
                    if variable is None or value is None:
                        raise QualificationError("Turtle expected result has malformed binding")
                    binding[rdflib.Variable(str(variable))] = value
                bindings.append(binding)
            result.bindings = bindings
            return result
        with path.open("rb") as stream:
            return Result.parse(stream, format=suffix_to_format[path.suffix.lower()])
    except KeyError as error:
        raise QualificationError(f"unsupported SELECT/ASK expected result format: {path.suffix}") from error


def _load_dataset(action: object, graph: Graph, root: Path) -> Dataset:
    dataset = Dataset()
    for data in graph.objects(action, QT.data):
        dataset.default_graph.parse(_local_path(root, data))
    for data in graph.objects(action, QT.graphData):
        path = _local_path(root, data)
        dataset.graph(URIRef(data)).parse(path)
    return dataset


def _approved(graph: Graph, test: object) -> bool:
    return (test, DAWGT.approval, DAWGT.Approved) in graph


def _excluded_reason(manifest: Path, graph: Graph, test: object, root: Path) -> str | None:
    relative = manifest.relative_to(root).as_posix()
    if "/entailment/" in f"/{relative}":
        return "ENTAILMENT_REGIME_OUT_OF_SCOPE"
    types = set(graph.objects(test, RDF.type))
    if QUERY_EVALUATION not in types and POSITIVE_SYNTAX not in types and NEGATIVE_SYNTAX not in types:
        return "NON_QUERY_TEST_TYPE"
    action = graph.value(test, MF.action)
    if action is None:
        return "MISSING_ACTION"
    query = _local_path(root, graph.value(action, QT.query) or action)
    text = query.read_text(encoding="utf-8")
    if _SERVICE.search(text):
        return "SERVICE_OR_FEDERATION_OUT_OF_SCOPE"
    form = _query_form(query)
    if form not in {"SELECT", "ASK"}:
        return f"{form or 'UNRECOGNIZED'}_OUT_OF_SCOPE"
    if not _approved(graph, test):
        return "NOT_DAWGT_APPROVED"
    if QUERY_EVALUATION in types and graph.value(test, MF.result) is None:
        return "MISSING_EXPECTED_RESULT"
    return None


def _run_test(manifest: Path, graph: Graph, test: object, root: Path) -> tuple[bool, str]:
    action = graph.value(test, MF.action)
    assert action is not None
    query = _local_path(root, graph.value(action, QT.query) or action)
    types = set(graph.objects(test, RDF.type))
    try:
        if NEGATIVE_SYNTAX in types:
            try:
                parseQuery(query.read_text(encoding="utf-8"))
            except Exception:
                return True, "negative syntax rejected"
            return False, "negative syntax accepted"
        if POSITIVE_SYNTAX in types:
            parseQuery(query.read_text(encoding="utf-8"))
            return True, "positive syntax accepted"
        actual = _load_dataset(action, graph, root).query(query.read_text(encoding="utf-8"))
        expected = _parse_expected(_local_path(root, graph.value(test, MF.result)))
        if actual.type != expected.type:
            return False, f"result type mismatch: {actual.type!r} != {expected.type!r}"
        if actual.type == "ASK":
            return (actual.askAnswer == expected.askAnswer, "ASK result mismatch")
        if not _select_equal(actual, expected):
            return False, "strict SELECT variable/binding multiset mismatch"
        return True, "SELECT binding multiset matched"
    except Exception as error:
        return False, f"{type(error).__name__}: {error}"


def qualify(checkout: Path, profile_id: str) -> dict[str, Any]:
    try:
        profile = PROFILES[profile_id]
    except KeyError as error:
        raise QualificationError(f"unknown profile: {profile_id}") from error
    source = _verify_checkout(checkout, profile)
    root = checkout.resolve() / str(profile["selected_root"])
    excluded: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    passed = 0
    attempted = 0
    discovered = 0
    manifests, profile_excluded = _walk_manifests(root, profile)
    for manifest, graph in manifests:
        for owner in graph.subjects(RDF.type, MF.Manifest):
            for entries in graph.objects(owner, MF.entries):
                for test in Collection(graph, entries):
                    discovered += 1
                    reason = _excluded_reason(manifest, graph, test, root)
                    if reason:
                        excluded[reason] += 1
                        continue
                    attempted += 1
                    ok, detail = _run_test(manifest, graph, test, root)
                    if ok:
                        passed += 1
                    else:
                        failures.append({
                            "id": str(test), "manifest": manifest.relative_to(root).as_posix(), "detail": detail,
                        })
    # An empty profile is not an adapter qualification and a skip is never a pass.
    status = "PASS" if attempted > 0 and not failures else "FAIL"
    return {
        "schema_version": SCHEMA,
        "profile": profile_id,
        "status": status,
        "adapter": {"package": "RDFLib", "version": rdflib.__version__, "mode": "READ_ONLY_LOCAL_DATASET"},
        "manifest_sha256": source["root_manifest_sha256"],
        "runtime": {
            "implementation": platform.python_implementation(),
            "python": platform.python_version(),
        },
        "source": source,
        "root_manifest": profile["root_manifest"],
        "capability": {
            "included": ["SELECT_SYNTAX", "ASK_SYNTAX", "SELECT_EVALUATION", "ASK_EVALUATION"],
            "excluded": ["UPDATE", "CONSTRUCT", "DESCRIBE", "SERVICE", "ENTAILMENT", "PROTOCOL", "GRAPH_STORE"],
            "write_back": "FORBIDDEN",
        },
        "counts": {"manifests": len(manifests), "discovered": discovered, "attempted": attempted, "passed": passed, "failed": len(failures), "excluded": sum(excluded.values()) + sum(profile_excluded.values())},
        "excluded_by_reason": dict(sorted(excluded.items())),
        "profile_excluded_by_reason": dict(sorted(profile_excluded.items())),
        "failures": failures,
        "nonclaim": "READ_ONLY_QUALIFICATION_ONLY_NOT_HSWM_CANONICAL_ADMISSION_PERMIT_PROVENANCE_CAUSAL_CREDIT_LEARNING_OR_UNIVERSAL_SPARQL_CONFORMANCE",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-checkout", required=True, type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="sparql11-readonly-diagnostic")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = qualify(args.suite_checkout, args.profile)
    except QualificationError as error:
        result = {"schema_version": SCHEMA, "status": "ERROR", "error": str(error)}
    except Exception as error:  # fail closed while retaining the JSON CLI contract
        result = {
            "schema_version": SCHEMA,
            "status": "ERROR",
            "error": f"{type(error).__name__}: {error}",
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
