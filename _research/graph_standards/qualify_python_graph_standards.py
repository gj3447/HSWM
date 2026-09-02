#!/usr/bin/env python3
"""Run the approved W3C SHACL 1.0 Core tests against a pinned local checkout.

The runner is deliberately a read-only qualification tool.  It does not load
HSWM data, write a graph store, or establish any HSWM authority or evidence.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import logging
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from io import StringIO
from pathlib import Path
import platform
import sys
from typing import Any, Iterable
from urllib.parse import unquote, urlparse
import warnings


PROFILE_ALL_CORE = "shacl10-pyshacl-core"
PROFILE_HSWM_CORE = "shacl10-pyshacl-hswm-core"
PROFILES = frozenset((PROFILE_ALL_CORE, PROFILE_HSWM_CORE))
_HSWM_UNSUPPORTED_SUFFIX = "/property/uniqueLang-002"
_HSWM_UNSUPPORTED_REASON = "UNSUPPORTED_COMPONENT_NOT_USED_BY_HSWM_PROFILE"
MF = "http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SHT = "http://www.w3.org/ns/shacl-test#"
SHACL = "http://www.w3.org/ns/shacl#"


class QualificationError(RuntimeError):
    """The source suite, runner input, or installed adapter is unsafe or unavailable."""


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError as error:
        raise QualificationError(f"required adapter package is not installed: {name}") from error


def _safe_file_uri(uri: Any, suite_root: Path, *, label: str) -> Path:
    """Resolve only local file URIs and prove their real path remains in suite_root."""
    text = str(uri)
    parsed = urlparse(text)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise QualificationError(f"{label} is not a local file URI: {text}")
    candidate = Path(unquote(parsed.path))
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(suite_root)
    except (OSError, ValueError) as error:
        raise QualificationError(f"{label} escapes the selected suite root: {text}") from error
    if not resolved.is_file():
        raise QualificationError(f"{label} is not a regular file: {text}")
    return resolved


def _objects_one(graph: Any, subject: Any, predicate: Any, *, label: str) -> Any:
    values = list(graph.objects(subject, predicate))
    if len(values) != 1:
        raise QualificationError(f"{label} must occur exactly once")
    return values[0]


def _iter_entries(graph: Any, rdflib: Any) -> Iterable[Any]:
    manifests = set(graph.subjects(rdflib.RDF.type, rdflib.URIRef(f"{MF}Manifest")))
    for manifest in sorted(manifests, key=str):
        for head in graph.objects(manifest, rdflib.URIRef(f"{MF}entries")):
            try:
                yield from rdflib.collection.Collection(graph, head)
            except Exception as error:
                raise QualificationError(f"manifest entries list is malformed: {manifest}") from error


def _load_recursive(manifest_path: Path, suite_root: Path, rdflib: Any) -> list[tuple[Any, Path]]:
    """Load manifest files and their mf:include targets without following external URLs."""
    pending = [manifest_path]
    seen: set[Path] = set()
    loaded: list[tuple[Any, Path]] = []
    include = rdflib.URIRef(f"{MF}include")
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        graph = rdflib.Graph()
        try:
            graph.parse(location=str(path), format="turtle")
        except Exception as error:
            raise QualificationError(f"cannot parse Turtle suite file: {path}") from error
        loaded.append((graph, path))
        includes = sorted(graph.objects(None, include), key=str)
        pending.extend(_safe_file_uri(uri, suite_root, label="mf:include") for uri in includes)
    return loaded


def _graph_from_action(uri: Any, suite_root: Path, rdflib: Any, *, label: str) -> Any:
    path = _safe_file_uri(uri, suite_root, label=label)
    graph = rdflib.Graph()
    try:
        graph.parse(location=str(path))
    except Exception as error:
        raise QualificationError(f"cannot parse {label}: {path}") from error
    return graph


def qualify_shacl10_core(suite_root: Path, *, profile: str) -> dict[str, Any]:
    if profile not in PROFILES:
        raise QualificationError(f"unknown SHACL qualification profile: {profile}")
    try:
        import rdflib
        import pyshacl
        from pyshacl.validator_conformance import check_sht_result
    except ModuleNotFoundError as error:
        raise QualificationError(f"required adapter dependency is not installed: {error.name}") from error

    root = suite_root.resolve(strict=True)
    selected = root / "data-shapes-test-suite"
    try:
        selected = selected.resolve(strict=True)
        selected.relative_to(root)
    except (OSError, ValueError) as error:
        raise QualificationError("suite root does not contain data-shapes-test-suite") from error
    manifest_path = selected / "tests/core/manifest.ttl"
    try:
        manifest_path = manifest_path.resolve(strict=True)
        manifest_path.relative_to(selected)
    except (OSError, ValueError) as error:
        raise QualificationError("SHACL Core manifest is absent or escapes selected suite") from error

    loaded = _load_recursive(manifest_path, selected, rdflib)
    validate_type = rdflib.URIRef(f"{SHT}Validate")
    approved = rdflib.URIRef(f"{SHT}approved")
    status_predicate = rdflib.URIRef(f"{MF}status")
    action_predicate = rdflib.URIRef(f"{MF}action")
    result_predicate = rdflib.URIRef(f"{MF}result")
    data_predicate = rdflib.URIRef(f"{SHT}dataGraph")
    shapes_predicate = rdflib.URIRef(f"{SHT}shapesGraph")
    label_predicate = rdflib.RDFS.label

    candidates = 0
    selected_entries: list[tuple[Any, Any, Path]] = []
    for graph, source_path in loaded:
        for entry in _iter_entries(graph, rdflib):
            if (entry, rdflib.RDF.type, validate_type) not in graph:
                continue
            candidates += 1
            if (entry, status_predicate, approved) in graph:
                selected_entries.append((graph, entry, source_path))
    selected_entries.sort(key=lambda item: str(item[1]))
    excluded: list[dict[str, str]] = []
    attempted_entries = selected_entries
    if profile == PROFILE_HSWM_CORE:
        excluded_entries = [item for item in selected_entries if str(item[1]).endswith(_HSWM_UNSUPPORTED_SUFFIX)]
        if len(excluded_entries) != 1:
            raise QualificationError("HSWM production exclusion did not match exactly one approved Core test")
        excluded = [{
            "id": str(excluded_entries[0][1]),
            "reason": _HSWM_UNSUPPORTED_REASON,
            "source": str(excluded_entries[0][2].relative_to(selected)),
        }]
        attempted_entries = [item for item in selected_entries if item not in excluded_entries]

    failures: list[dict[str, str]] = []
    prior_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with warnings.catch_warnings():
            # Individual negative/edge fixtures intentionally trigger RDFLib warnings.
            # Their sole qualification outcome is retained below, never discarded.
            warnings.simplefilter("ignore")
            for graph, entry, source_path in attempted_entries:
                label = next(iter(graph.objects(entry, label_predicate)), entry)
                try:
                    action = _objects_one(graph, entry, action_predicate, label="mf:action")
                    expected = _objects_one(graph, entry, result_predicate, label="mf:result")
                    data_uri = _objects_one(graph, action, data_predicate, label="sht:dataGraph")
                    shapes_uri = _objects_one(graph, action, shapes_predicate, label="sht:shapesGraph")
                    data_graph = _graph_from_action(data_uri, selected, rdflib, label="sht:dataGraph")
                    shapes_graph = _graph_from_action(shapes_uri, selected, rdflib, label="sht:shapesGraph")
                    _conforms, report_graph, _report_text = pyshacl.validate(
                        data_graph,
                        shacl_graph=shapes_graph,
                        inference="rdfs",
                        advanced=False,
                        meta_shacl=False,
                        inplace=False,
                        abort_on_first=False,
                        serialize_report_graph=False,
                    )
                    if not check_sht_result(report_graph, graph, expected):
                        raise QualificationError("pyshacl report differs from official expected report")
                except Exception as error:
                    failures.append({"id": str(entry), "name": str(label), "source": str(source_path.relative_to(selected)), "error": str(error)})
    finally:
        logging.disable(prior_disable)

    return {
        "adapter": {
            "package": "pyshacl",
            "version": _package_version("pyshacl"),
            "supporting_package": "rdflib",
            "supporting_version": _package_version("rdflib"),
        },
        "counts": {
            "candidate_validate": candidates,
            "attempted": len(attempted_entries),
            "excluded": len(excluded),
            "failed": len(failures),
            "passed": len(attempted_entries) - len(failures),
            "selected_approved_validate": len(selected_entries),
            "total_approved": len(selected_entries),
            "total_loaded_files": len(loaded),
        },
        "excluded": excluded,
        "failures": failures,
        "manifest_path": "data-shapes-test-suite/tests/core/manifest.ttl",
        "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "profile": profile,
        "runtime": {
            "implementation": platform.python_implementation(),
            "python": platform.python_version(),
        },
        "selected_path": "data-shapes-test-suite",
        "status": "PASS" if not failures else "FAIL",
    }


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--suite-root", required=True)
    parsed = parser.parse_args(argv)
    if parsed.profile not in PROFILES:
        parser.error("--profile must be one of " + ", ".join(sorted(PROFILES)))
    return parsed


def main(argv: list[str] | None = None) -> int:
    try:
        args = _arguments(sys.argv[1:] if argv is None else argv)
        # Test fixtures intentionally exercise malformed lexical forms.  Keep the
        # machine interface one JSON line; every resulting qualification failure
        # remains in ``result.failures`` rather than becoming ignored console noise.
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = qualify_shacl10_core(Path(args.suite_root), profile=args.profile)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0 if result["status"] == "PASS" else 1
    except (QualificationError, OSError, ValueError) as error:
        print(json.dumps({"error": str(error), "status": "ERROR"}, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
