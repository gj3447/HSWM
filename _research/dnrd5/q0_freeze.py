"""Build a deterministic, qualification-only DNRD-5 Q0 freeze artifact.

This module never opens a network connection and never dispatches a model.  It
only materializes the public synthetic corpus whose hashes a later Q gateway
must reconstruct before it is allowed to issue a qualification call.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    parse_canonical,
)
from _research.dnrd5.provider_gateway import Dnrd5ProviderConfig, _validate_json_schema
from _research.dnrd5.q0_qualification import (
    FALSIFIED,
    INCONCLUSIVE,
    NONCLAIMS,
    Q0_SCHEMA,
    Q_NAMESPACE,
    REPRODUCED,
    make_q_start_marker,
    validate_q0_plan,
)
from _research.dnrd5.q_provider_gateway import (
    Q_GATEWAY_VERSION,
    QCorpusMaterial,
    build_q_request,
)

FREEZE_SCHEMA = "hswm-dnrd5-q0-freeze-artifact/v1"
CORPUS_SCHEMA = "hswm-dnrd5-q0-public-synthetic-corpus/v1"
GENESIS_SCHEMA = "hswm-dnrd5-q0-evidence-root-genesis/v1"
ORDER_ALGORITHM = "FROZEN_SHA256_FISHER_YATES_V1"
REPLICATES = 4
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_UID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")


class Q0FreezeRefusal(ValueError):
    """The requested freeze would be ambiguous, mutable, or malformed."""


def _refuse(message: str) -> None:
    raise Q0FreezeRefusal(message)


def _sha(value: str, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None or value == "0" * 64:
        _refuse(f"{label} must be a non-placeholder SHA-256")
    return value


def _git(value: str, label: str) -> str:
    if type(value) is not str or _GIT.fullmatch(value) is None or value == "0" * 40:
        _refuse(f"{label} must be a non-placeholder Git SHA-1")
    return value


def _canonical_file(path: Path, label: str) -> bytes:
    if not path.is_file():
        _refuse(f"{label} must be a regular file")
    raw = path.read_bytes()
    if not raw:
        _refuse(f"{label} is empty")
    try:
        value = parse_canonical(raw)
    except CanonicalJsonError as error:
        _refuse(f"{label} must contain canonical-json/v1 bytes: {error}")
    if type(value) is not dict:
        _refuse(f"{label} must contain a canonical object")
    return raw


def _regular_bytes(path: Path, label: str) -> bytes:
    if not path.is_file():
        _refuse(f"{label} must be a regular file")
    raw = path.read_bytes()
    if not raw:
        _refuse(f"{label} is empty")
    return raw


def _validate_endpoint_descriptor(raw: bytes) -> str:
    try:
        value = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        _refuse(f"endpoint identity must be canonical-json/v1 bytes: {error}")
    if type(value) is not dict:
        _refuse("endpoint identity must be a canonical object")
    if set(value) != {"endpoint", "tlsStatus", "transport"}:
        _refuse("endpoint identity must have endpoint/transport/tlsStatus only")
    if (
        value["endpoint"] != "http://127.0.0.1:8000/v1/chat/completions"
        or value["transport"] != "HTTP_LOOPBACK"
        or value["tlsStatus"] != "NOT_APPLICABLE_LOOPBACK_HTTP"
    ):
        _refuse("endpoint identity does not name the frozen DGX loopback HTTP endpoint")
    return value["endpoint"]


def _endpoint_descriptor(path: Path) -> tuple[str, bytes]:
    raw = _canonical_file(path, "endpoint identity")
    return _validate_endpoint_descriptor(raw), raw


def identity_descriptor_templates() -> dict[str, Any]:
    """The checked fields expected in the five actual DGX identity files."""
    return {
        "endpoint": {
            "endpoint": "http://127.0.0.1:8000/v1/chat/completions",
            "transport": "HTTP_LOOPBACK",
            "tlsStatus": "NOT_APPLICABLE_LOOPBACK_HTTP",
        },
        "model_required": {
            "served_model_id": "qwen3.6-35b-a3b",
            "model_root": "Qwen/Qwen3.6-35B-A3B-FP8",
            "vllm_version": "0.25.1",
        },
        "runtime_required": {
            "hostname": "edgexpert-e229",
            "source_profile": "hswm-run",
        },
        "tls_required": {"status": "NOT_APPLICABLE_LOOPBACK_HTTP"},
        "isolation_required": {
            "transport": "HTTP_LOOPBACK",
            "provider_cache": "NOT_OBSERVABLE_BY_CLIENT",
        },
    }


def _require_fields(raw: bytes, label: str, required: Mapping[str, str]) -> None:
    value = parse_canonical(raw)
    for key, expected in required.items():
        if value.get(key) != expected:
            _refuse(f"{label}.{key} does not equal the frozen DGX value")


def _schema(size: str) -> dict[str, Any]:
    limits = {
        "S": (8, 12, 48),
        "M": (12, 32, 96),
        "L": (16, 80, 192),
    }
    answer_max, rationale_min, rationale_max = limits[size]
    return {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "pattern": f"^[A-Z]{{2,{answer_max}}}$",
                "minLength": 2,
                "maxLength": answer_max,
            },
            "rationale": {
                "type": "string",
                "pattern": f"^[A-Za-z0-9 .,;:!?'()/+-]{{{rationale_min},{rationale_max}}}$",
                "minLength": rationale_min,
                "maxLength": rationale_max,
            },
        },
        "required": ["answer", "rationale"],
        "additionalProperties": False,
    }


def _instruction(size: str) -> str:
    return {
        "S": "Read only the supplied public objects. Choose one uppercase label and give one plain-ASCII reason.",
        "M": "Read only the supplied public objects. Choose one uppercase label and explain the public cues in one plain-ASCII sentence.",
        "L": "Read only the supplied public objects. Choose one uppercase label and give two plain-ASCII sentences explaining the public cues.",
    }[size]


_ROWS: tuple[
    tuple[str, str, str, tuple[str, str, str], tuple[str, str], str, str], ...
] = (
    (
        "PRE_OUTCOME_TRAJECTORY",
        "S",
        "QP01",
        ("AMBER", "BIRCH", "CORAL"),
        ("A starts first", "C appears once"),
        "choose from listed labels",
        "north",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "S",
        "QP02",
        ("DUNE", "EMBER", "FIELD"),
        ("second cue is EMBER", "all labels public"),
        "choose one label",
        "east",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "M",
        "QP03",
        ("GLASS", "HARBOR", "INDIGO"),
        ("GLASS has five letters", "INDIGO has six letters"),
        "use both cues",
        "south",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "M",
        "QP04",
        ("JUNIPER", "KITE", "LANTERN"),
        ("KITE is shortest", "LANTERN ends with N"),
        "choose a noted label",
        "west",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "M",
        "QP05",
        ("MARBLE", "NOVA", "ORCHID"),
        ("MARBLE begins M", "NOVA has four letters"),
        "compare the cues",
        "ridge",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "M",
        "QP06",
        ("PEBBLE", "QUARTZ", "RIVER"),
        ("RIVER ends R", "QUARTZ begins Q"),
        "state a public preference",
        "shore",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "L",
        "QP07",
        ("SABLE", "TERRACE", "UMBER"),
        ("SABLE has two vowels", "TERRACE has three vowels"),
        "compare labels using public spelling",
        "valley",
    ),
    (
        "PRE_OUTCOME_TRAJECTORY",
        "L",
        "QP08",
        ("VIOLET", "WILLOW", "XENON"),
        ("VIOLET begins V", "XENON ends N"),
        "explain two public cues",
        "garden",
    ),
    (
        "REVISION_PROPOSAL",
        "S",
        "QT09",
        ("ALTO", "BRAVO", "CEDAR"),
        ("public trace carries ALTO", "static public cue"),
        "select and explain",
        "QF09",
    ),
    (
        "REVISION_PROPOSAL",
        "S",
        "QT10",
        ("DELTA", "ECHO", "FERN"),
        ("public trace carries ECHO", "static public cue"),
        "select and explain",
        "QF10",
    ),
    (
        "REVISION_PROPOSAL",
        "M",
        "QT11",
        ("GROVE", "HALO", "IVORY"),
        ("GROVE begins G", "HALO has four letters"),
        "select and explain",
        "QF11",
    ),
    (
        "REVISION_PROPOSAL",
        "M",
        "QT12",
        ("JASPER", "KELP", "LOOM"),
        ("KELP is short", "LOOM ends M"),
        "select and explain",
        "QF12",
    ),
    (
        "REVISION_PROPOSAL",
        "M",
        "QT13",
        ("MINT", "NEST", "OASIS"),
        ("MINT has four letters", "OASIS has three vowels"),
        "select and explain",
        "QF13",
    ),
    (
        "REVISION_PROPOSAL",
        "M",
        "QT14",
        ("PINE", "QUILL", "ROSE"),
        ("QUILL begins Q", "ROSE ends E"),
        "select and explain",
        "QF14",
    ),
    (
        "REVISION_PROPOSAL",
        "L",
        "QT15",
        ("SAND", "TULIP", "URSA"),
        ("SAND and URSA are four letters", "TULIP has five"),
        "compare public labels",
        "QF15",
    ),
    (
        "REVISION_PROPOSAL",
        "L",
        "QT16",
        ("VELVET", "WREN", "XENIA"),
        ("VELVET has two vowels", "XENIA begins X"),
        "compare public labels",
        "QF16",
    ),
    (
        "FRESH_PROBE",
        "S",
        "QP17",
        ("ACORN", "BLAZE", "CLOUD"),
        ("ACORN begins A", "CLOUD ends D"),
        "choose one public label",
        "dawn",
    ),
    (
        "FRESH_PROBE",
        "S",
        "QP18",
        ("DRIFT", "EMBER", "FROST"),
        ("EMBER has two vowels", "FROST begins F"),
        "choose one public label",
        "dusk",
    ),
    (
        "FRESH_PROBE",
        "M",
        "QP19",
        ("GROVE", "HONEY", "IRON"),
        ("HONEY ends Y", "IRON has four letters"),
        "use both cues",
        "field",
    ),
    (
        "FRESH_PROBE",
        "M",
        "QP20",
        ("JET", "KAPPA", "LILAC"),
        ("JET is shortest", "LILAC ends C"),
        "choose a noted label",
        "lake",
    ),
    (
        "FRESH_PROBE",
        "M",
        "QP21",
        ("MOSS", "NORTH", "OPAL"),
        ("MOSS has one vowel", "OPAL begins O"),
        "compare public spelling",
        "hill",
    ),
    (
        "FRESH_PROBE",
        "M",
        "QP22",
        ("PULSE", "QUARTZ", "REED"),
        ("PULSE ends E", "REED has four letters"),
        "state a public preference",
        "rain",
    ),
    (
        "FRESH_PROBE",
        "L",
        "QP23",
        ("SOLAR", "THYME", "UMBER"),
        ("SOLAR has two vowels", "THYME ends E"),
        "explain two public cues",
        "sun",
    ),
    (
        "FRESH_PROBE",
        "L",
        "QP24",
        ("VISTA", "WATER", "XENON"),
        ("VISTA begins V", "WATER has five letters"),
        "compare labels using public spelling",
        "wind",
    ),
)


def _input(
    case_id: str,
    row: tuple[str, str, str, tuple[str, str, str], tuple[str, str], str, str],
) -> dict[str, Any]:
    call_class, _size, record, labels, cues, rule, extra = row
    if call_class == "PRE_OUTCOME_TRAJECTORY":
        return {
            "publicTask": {
                "case": case_id,
                "cues": list(cues),
                "labels": list(labels),
                "rule": rule,
            },
            "behaviorProjection": {"context": extra, "snapshot": record},
        }
    if call_class == "REVISION_PROPOSAL":
        return {
            "sealedTrajectory": {
                "cues": list(cues),
                "labels": list(labels),
                "record": record,
            },
            "assignedFeedback": {"mode": "STATIC_PUBLIC", "receipt": extra},
            "revisionRequest": {
                "request": rule,
                "scope": "PUBLIC_SYNTHETIC",
                "target": "QR" + case_id[-3:],
            },
        }
    return {
        "behaviorProjection": {"context": extra, "snapshot": record},
        "freshProbe": {
            "case": case_id,
            "cues": list(cues),
            "labels": list(labels),
            "rule": rule,
        },
    }


def build_corpus() -> tuple[dict[str, Any], tuple[QCorpusMaterial, ...]]:
    """Return public corpus manifest and raw bytes used by the Q gateway."""
    entries: list[dict[str, Any]] = []
    materials: list[QCorpusMaterial] = []
    for index, row in enumerate(_ROWS, 1):
        call_class, size, _record, _labels, _cues, _rule, _extra = row
        case_id = f"QCASE-{index:03d}"
        instruction = _instruction(size).encode("utf-8")
        model_input = canonical_bytes(_input(case_id, row))
        response_schema = canonical_bytes(_schema(size))
        _validate_json_schema(parse_canonical(response_schema))
        rng = sha256(
            b"hswm-dnrd5-q0-public-synthetic-rng/v1\0" + case_id.encode("ascii")
        ).digest()
        max_tokens = {"S": 64, "M": 128, "L": 256}[size]
        material = QCorpusMaterial(
            case_id, instruction, model_input, response_schema, rng, max_tokens
        )
        materials.append(material)
        entries.append(
            {
                "case_id": case_id,
                "call_class": call_class,
                "instruction": instruction.decode("utf-8"),
                "max_output_tokens": max_tokens,
                "model_input": parse_canonical(model_input),
                "response_schema": parse_canonical(response_schema),
                "rng_hex": rng.hex(),
                "size_class": size,
            }
        )
    manifest = {
        "schema_version": CORPUS_SCHEMA,
        "classification": "PUBLIC_SYNTHETIC_QUALIFICATION_ONLY_NO_CORRECTNESS_EVALUATOR",
        "cases": entries,
    }
    return manifest, tuple(materials)


def fisher_yates_order(
    case_ids: Sequence[str], seed: bytes, *, replicates: int = REPLICATES
) -> list[str]:
    """Current Q0's domain-separated SHA-256 Fisher--Yates permutation, v1.

    This intentionally mirrors the checked-in Q0 validator's frozen byte
    stream, so the builder never emits a plan that the later gateway refuses.
    """
    if type(seed) is not bytes or len(seed) != 32 or not 2 <= replicates <= 32:
        _refuse("order seed must be 32 bytes and replicate count must be bounded")
    items = [
        f"DNRD5-Q-{case_id[-3:]}-R{replicate:03d}"
        for case_id in case_ids
        for replicate in range(1, replicates + 1)
    ]
    if len(items) != len(set(items)):
        _refuse("case IDs do not yield unique Q attempt IDs")
    for counter, index in enumerate(range(len(items) - 1, 0, -1)):
        digest = sha256(
            b"HSWM-DNRD5-Q0-CALL-ORDER-V1\0" + seed + counter.to_bytes(8, "big")
        ).digest()
        chosen = int.from_bytes(digest[:8], "big") % (index + 1)
        items[index], items[chosen] = items[chosen], items[index]
    return items


def _bound_source_and_verifier(
    *,
    source_commit: str,
    source_tree: str,
    source_ci_receipt: bytes,
    verifier_build: bytes,
    verifier_source: bytes,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Derive the sole admissible plan bindings from exact receipt bytes."""
    _git(source_commit, "source.commit")
    _git(source_tree, "source.tree")
    try:
        ci = parse_canonical(source_ci_receipt)
    except CanonicalJsonError as error:
        _refuse(f"source CI receipt must be canonical-json/v1 bytes: {error}")
    ci_keys = {
        "schema_version",
        "repository",
        "workflow",
        "head_sha",
        "run_attempt",
        "conclusion",
        "terminal",
    }
    if type(ci) is not dict or set(ci) != ci_keys:
        _refuse("source CI receipt shape drifted")
    if (
        ci.get("schema_version") != "hswm-dnrd5-q0-ci-receipt/v1"
        or ci.get("repository") != "gj3447/HSWM"
        or ci.get("workflow") != "CI"
        or ci.get("head_sha") != source_commit
        or ci.get("run_attempt") != 1
        or ci.get("conclusion") != "success"
        or ci.get("terminal") != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"
    ):
        _refuse("source CI receipt does not bind first successful CI for source commit")
    source = {
        "commit": source_commit,
        "tree": source_tree,
        "ci_receipt_sha256": sha256(source_ci_receipt).hexdigest(),
        "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD",
    }
    try:
        build = parse_canonical(verifier_build)
    except CanonicalJsonError as error:
        _refuse(f"verifier build must be canonical-json/v1 bytes: {error}")
    build_keys = {
        "schema_version",
        "source",
        "file_sha256",
        "forbidden_producer_imports_absent",
        "terminal",
    }
    if type(build) is not dict or set(build) != build_keys:
        _refuse("verifier build shape drifted")
    if (
        build.get("schema_version") != "hswm-dnrd5-q0-independent-verifier-build/v1"
        or build.get("source") != source
        or type(build.get("file_sha256")) is not str
        or _SHA.fullmatch(build["file_sha256"]) is None
        or build["file_sha256"] != sha256(verifier_source).hexdigest()
        or build.get("forbidden_producer_imports_absent") is not True
        or build.get("terminal") != "INDEPENDENT_RAW_BYTE_VERIFIER_BUILD_BOUND"
    ):
        _refuse("verifier build does not bind the exact source identity")
    try:
        tree = ast.parse(
            verifier_source.decode("utf-8"), filename="q0.verifier-source.py"
        )
    except (SyntaxError, UnicodeDecodeError) as error:
        _refuse(f"verifier source is not valid UTF-8 Python: {error}")
    forbidden = {
        "_research.dnrd5.q_provider_gateway",
        "_research.dnrd5.q0_freeze",
        "_research.dnrd5.q0_qualification",
    }
    forbidden_leaves = {name.rsplit(".", 1)[-1] for name in forbidden}
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [module, *(f"{module}.{alias.name}" for alias in node.names)]
            names.extend(alias.name for alias in node.names)
        if any(
            name in forbidden_leaves
            or any(name == item or name.startswith(item + ".") for item in forbidden)
            for name in names
        ):
            _refuse("verifier source imports a forbidden producer module")
    return source, {
        "source": source,
        "build_output_sha256": sha256(verifier_build).hexdigest(),
    }


def build_freeze(
    *,
    source_commit: str,
    source_tree: str,
    source_ci_receipt: bytes,
    verifier_build: bytes,
    verifier_source: bytes,
    order_seed: bytes,
    endpoint_descriptor: bytes,
    model_identity: bytes,
    runtime_identity: bytes,
    tls_identity: bytes,
    isolation_identity: bytes,
    root_uid: str,
) -> dict[str, bytes]:
    """Construct all canonical artifacts without writing them or dispatching calls."""
    if type(root_uid) is not str or _UID.fullmatch(root_uid) is None:
        _refuse("root_uid is not a canonical identifier")
    source, verifier = _bound_source_and_verifier(
        source_commit=source_commit,
        source_tree=source_tree,
        source_ci_receipt=source_ci_receipt,
        verifier_build=verifier_build,
        verifier_source=verifier_source,
    )
    endpoint = _validate_endpoint_descriptor(endpoint_descriptor)
    config = Dnrd5ProviderConfig(endpoint=endpoint, expected_model="qwen3.6-35b-a3b")
    _require_fields(
        model_identity,
        "model identity",
        identity_descriptor_templates()["model_required"],
    )
    _require_fields(
        runtime_identity,
        "runtime identity",
        identity_descriptor_templates()["runtime_required"],
    )
    _require_fields(
        tls_identity, "TLS identity", identity_descriptor_templates()["tls_required"]
    )
    _require_fields(
        isolation_identity,
        "isolation identity",
        identity_descriptor_templates()["isolation_required"],
    )
    corpus_manifest, materials = build_corpus()
    corpus_raw = canonical_bytes(corpus_manifest)
    corpus_plan: list[dict[str, Any]] = []
    for entry, material in zip(corpus_manifest["cases"], materials, strict=True):
        request = build_q_request(config, entry["call_class"], material)
        corpus_plan.append(
            {
                "case_id": material.case_id,
                "call_class": entry["call_class"],
                "request_sha256": sha256(request).hexdigest(),
                "instruction_sha256": sha256(material.instruction_bytes).hexdigest(),
                "model_input_sha256": sha256(material.model_input_bytes).hexdigest(),
                "response_schema_sha256": sha256(
                    material.response_schema_bytes
                ).hexdigest(),
                "rng_sha256": sha256(material.rng_bytes).hexdigest(),
                "max_output_tokens": material.max_output_tokens,
            }
        )
    identities = {
        "endpoint_sha256": sha256(endpoint.encode("utf-8")).hexdigest(),
        "model_identity_sha256": sha256(model_identity).hexdigest(),
        "runtime_identity_sha256": sha256(runtime_identity).hexdigest(),
        "tls_identity_sha256": sha256(tls_identity).hexdigest(),
        "isolation_identity_sha256": sha256(isolation_identity).hexdigest(),
    }
    genesis = {
        "schema_version": GENESIS_SCHEMA,
        "root_uid": root_uid,
        "corpus_manifest_sha256": sha256(corpus_raw).hexdigest(),
        "endpoint_descriptor_sha256": sha256(endpoint_descriptor).hexdigest(),
        "identity_descriptor_sha256s": {
            "model": identities["model_identity_sha256"],
            "runtime": identities["runtime_identity_sha256"],
            "tls": identities["tls_identity_sha256"],
            "isolation": identities["isolation_identity_sha256"],
        },
        "source": dict(source),
    }
    genesis_raw = canonical_bytes(genesis)
    order = fisher_yates_order([item["case_id"] for item in corpus_plan], order_seed)
    plan = {
        "schema_version": Q0_SCHEMA,
        "namespace": Q_NAMESPACE,
        "source": dict(source),
        "gateway_version": Q_GATEWAY_VERSION,
        "corpus_manifest_sha256": sha256(corpus_raw).hexdigest(),
        "corpus": corpus_plan,
        "replicates": REPLICATES,
        "comparator": "EXACT_REQUEST_RUNTIME_RNG_AND_MODEL_CONTENT_UTF8_STRUCTURED_EQUALITY",
        "call_order": order,
        "call_order_algorithm": ORDER_ALGORITHM,
        "call_order_seed_hex": order_seed.hex(),
        "call_order_seed_sha256": sha256(order_seed).hexdigest(),
        "budget": len(order),
        "zero_retry": True,
        "identities": identities,
        "verifier": dict(verifier),
        "evidence_root_genesis_sha256": sha256(genesis_raw).hexdigest(),
        "allowed_terminals": [REPRODUCED, FALSIFIED, INCONCLUSIVE],
        "nonclaims": list(NONCLAIMS),
    }
    plan_raw = canonical_bytes(plan)
    validate_q0_plan(plan_raw)
    templates_raw = canonical_bytes(
        {
            "schema_version": "hswm-dnrd5-q0-dgx-identity-templates/v1",
            "templates": identity_descriptor_templates(),
        }
    )
    return {
        "q0.plan.json": plan_raw,
        "q0.start-marker.json": make_q_start_marker(plan_raw),
        "q0.corpus.json": corpus_raw,
        "q0.root-genesis.json": genesis_raw,
        "q0.ci-receipt.json": source_ci_receipt,
        "q0.verifier-build.json": verifier_build,
        "q0.verifier-source.py": verifier_source,
        "q0.identity-templates.json": templates_raw,
        "identity.endpoint.json": endpoint_descriptor,
        "identity.model.json": model_identity,
        "identity.runtime.json": runtime_identity,
        "identity.tls.json": tls_identity,
        "identity.isolation.json": isolation_identity,
    }


def write_freeze(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    if output_dir.exists() or not output_dir.parent.is_dir():
        _refuse("output directory must be a new child of an existing directory")
    output_dir.mkdir(mode=0o700)
    for name, raw in artifacts.items():
        if "/" in name or not raw:
            _refuse("artifact name or bytes invalid")
        fd = os.open(output_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a no-network DNRD-5 Q0 qualification freeze artifact"
    )
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--source-ci-receipt", type=Path, required=True)
    parser.add_argument("--verifier-build", type=Path, required=True)
    parser.add_argument("--verifier-source", type=Path, required=True)
    parser.add_argument("--order-seed-hex", required=True)
    parser.add_argument("--endpoint-identity", type=Path, required=True)
    parser.add_argument("--model-identity", type=Path, required=True)
    parser.add_argument("--runtime-identity", type=Path, required=True)
    parser.add_argument("--tls-identity", type=Path, required=True)
    parser.add_argument("--isolation-identity", type=Path, required=True)
    parser.add_argument("--root-uid", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        seed = bytes.fromhex(args.order_seed_hex)
    except ValueError as error:
        raise Q0FreezeRefusal("order seed must be hex") from error
    endpoint, endpoint_raw = _endpoint_descriptor(args.endpoint_identity)
    del (
        endpoint
    )  # parsed again by build_freeze; this check gives the CLI an early boundary.
    artifacts = build_freeze(
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        source_ci_receipt=_canonical_file(args.source_ci_receipt, "source CI receipt"),
        verifier_build=_canonical_file(args.verifier_build, "verifier build"),
        verifier_source=_regular_bytes(args.verifier_source, "verifier source"),
        order_seed=seed,
        endpoint_descriptor=endpoint_raw,
        model_identity=_canonical_file(args.model_identity, "model identity"),
        runtime_identity=_canonical_file(args.runtime_identity, "runtime identity"),
        tls_identity=_canonical_file(args.tls_identity, "TLS identity"),
        isolation_identity=_canonical_file(
            args.isolation_identity, "isolation identity"
        ),
        root_uid=args.root_uid,
    )
    write_freeze(args.output_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
