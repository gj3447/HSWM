"""No-network freezer for the separately preregistered DGX live-Q1 instrument.

It materializes public Q0 synthetic inputs under the live-Q1 protocol; it does
not contact a model, start a service, or authorize a dispatch.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import tempfile
from typing import Any

from _research.dnrd5.canonical_json import CanonicalJsonError, canonical_bytes, parse_canonical
from _research.dnrd5.q0_freeze import build_corpus
from _research.dgx_q1.github_ci_receipt import (
    GitHubCiReceiptRefusal,
    parse_github_actions_ci_receipt,
)
from _research.dgx_q1.live_protocol import (
    CALL_CLASSES, CONSUMPTION_REGISTRY, NAMESPACE, PLAN_SCHEMA, RUNNER_VERSION,
    TERMINALS, NONCLAIMS,
    LiveQ1CaseMaterial, LiveQ1Refusal, bind_case_material, build_live_q1_request, derive_live_q1_order,
    make_live_q1_start_marker, validate_live_q1_plan, validate_live_q1_start_marker,
)

FREEZE_SCHEMA = "hswm-dgx-q1-live-preregistration-freeze/v1"
CORPUS_SCHEMA = "hswm-dgx-q1-live-public-synthetic-corpus/v1"
IDENTITY_NAMES = (
    "endpoint_sha256", "model_identity_sha256", "runtime_identity_sha256",
    "tls_identity_sha256", "declared_isolation_contract_sha256",
    "model_snapshot_manifest_sha256",
)


class LiveQ1FreezeRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveQ1PreregistrationInputs:
    source_commit: str
    source_tree: str
    source_ci_receipt: bytes
    verifier_commit: str
    verifier_tree: str
    verifier_ci_receipt: bytes
    verifier_build: bytes
    identities: Mapping[str, bytes]
    call_order_seed: bytes
    root_genesis: bytes


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw:
        raise LiveQ1FreezeRefusal(f"{label} must be nonempty exact bytes")
    try:
        value = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        raise LiveQ1FreezeRefusal(f"{label} must be canonical JSON") from error
    if type(value) is not dict or not value:
        raise LiveQ1FreezeRefusal(f"{label} must be a nonempty canonical object")
    return value


def _git(value: str, label: str) -> str:
    if type(value) is not str or len(value) != 40 or value == "0" * 40 or any(c not in "0123456789abcdef" for c in value):
        raise LiveQ1FreezeRefusal(f"{label} must be a non-placeholder Git SHA-1")
    return value


def _served_model(raw: bytes, snapshot_raw: bytes) -> str:
    identity = _canonical_object(raw, "model identity")
    if (
        set(identity)
        != {
            "schema_version",
            "model",
            "repository",
            "revision",
            "snapshot_manifest_sha256",
        }
        or identity.get("schema_version") != "hswm-dgx-q1-model-identity/v1"
        or type(identity.get("model")) is not str
        or not identity["model"]
        or len(identity["model"]) > 160
        or type(identity.get("repository")) is not str
        or re.fullmatch(
            r"[A-Za-z0-9_.-]{1,120}/[A-Za-z0-9_.-]{1,160}",
            identity["repository"],
        ) is None
        or type(identity.get("revision")) is not str
        or re.fullmatch(r"[0-9a-f]{40}", identity["revision"])
        is None
        or identity.get("snapshot_manifest_sha256")
        != sha256(snapshot_raw).hexdigest()
    ):
        raise LiveQ1FreezeRefusal("canonical model identity must bind one served model")
    snapshot = _canonical_object(snapshot_raw, "model snapshot manifest")
    if (
        snapshot.get("schema_version")
        != "hswm-dgx-q1-model-snapshot-manifest/v1"
        or snapshot.get("repository") != identity["repository"]
        or snapshot.get("revision") != identity["revision"]
    ):
        raise LiveQ1FreezeRefusal("model identity/snapshot manifest join drifted")
    return identity["model"]


def _ci_receipt(raw: bytes, commit: str, tree: str, label: str) -> None:
    try:
        parse_github_actions_ci_receipt(
            raw,
            repository="gj3447/HSWM",
            commit=commit,
            tree=tree,
        )
    except GitHubCiReceiptRefusal as error:
        raise LiveQ1FreezeRefusal(
            f"{label} semantic binding drifted"
        ) from error


def build_verifier_source_manifest(source_raw: bytes) -> bytes:
    """Bind the standalone verifier source and its independently inspectable imports."""

    if type(source_raw) is not bytes or not source_raw:
        raise LiveQ1FreezeRefusal("verifier source must be nonempty bytes")
    try:
        source_text = source_raw.decode("utf-8", errors="strict")
        tree = ast.parse(source_text)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise LiveQ1FreezeRefusal("verifier source is not valid UTF-8 Python") from error
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {
        "_research.dgx_q1.live_protocol",
        "_research.dgx_q1.live_runner",
        "_research.dgx_q1.live_launcher",
        "_research.dgx_q1.live_preregistration",
    }
    if imports & forbidden:
        raise LiveQ1FreezeRefusal("independent verifier imports a producer module")
    return canonical_bytes(
        {
            "schema_version": "hswm-dgx-q1-independent-verifier-build/v1",
            "source_path": "_research/dgx_q1/independent_live_verifier.py",
            "source_sha256": sha256(source_raw).hexdigest(),
            "source_utf8": source_text,
            "imports": sorted(imports),
            "terminal": "INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND",
        }
    )


def _verifier_build(raw: bytes) -> None:
    value = _canonical_object(raw, "verifier build")
    if (
        set(value)
        != {
            "schema_version",
            "source_path",
            "source_sha256",
            "source_utf8",
            "imports",
            "terminal",
        }
        or value.get("schema_version")
        != "hswm-dgx-q1-independent-verifier-build/v1"
        or value.get("source_path")
        != "_research/dgx_q1/independent_live_verifier.py"
        or type(value.get("source_utf8")) is not str
        or sha256(value["source_utf8"].encode("utf-8")).hexdigest()
        != value.get("source_sha256")
        or value.get("terminal")
        != "INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND"
        or raw != build_verifier_source_manifest(value["source_utf8"].encode("utf-8"))
    ):
        raise LiveQ1FreezeRefusal("verifier build/source binding drifted")


def q0_public_materials() -> tuple[dict[str, Any], tuple[LiveQ1CaseMaterial, ...]]:
    """Convert, without changing, the Q0 24-case public synthetic corpus."""
    q0_manifest, q0_materials = build_corpus()
    materials = tuple(LiveQ1CaseMaterial(
        item.case_id, item.instruction_bytes, item.model_input_bytes,
        item.response_schema_bytes, item.rng_bytes, item.max_output_tokens,
    ) for item in q0_materials)
    if len(materials) != 24 or len({item.case_id for item in materials}) != 24:
        raise LiveQ1FreezeRefusal("Q0 corpus is not exactly 24 unique cases")
    classes = Counter(row["call_class"] for row in q0_manifest["cases"])
    if classes != Counter({name: 8 for name in CALL_CLASSES}):
        raise LiveQ1FreezeRefusal("Q0 corpus no longer has eight cases per class")
    return q0_manifest, materials


def build_live_preregistration(inputs: LiveQ1PreregistrationInputs) -> dict[str, bytes]:
    if type(inputs) is not LiveQ1PreregistrationInputs:
        raise LiveQ1FreezeRefusal("inputs must be exact LiveQ1PreregistrationInputs")
    source_commit, source_tree = _git(inputs.source_commit, "source commit"), _git(inputs.source_tree, "source tree")
    verifier_commit, verifier_tree = _git(inputs.verifier_commit, "verifier commit"), _git(inputs.verifier_tree, "verifier tree")
    _ci_receipt(inputs.source_ci_receipt, source_commit, source_tree, "source CI receipt")
    _ci_receipt(inputs.verifier_ci_receipt, verifier_commit, verifier_tree, "verifier CI receipt")
    _verifier_build(inputs.verifier_build)
    genesis = _canonical_object(inputs.root_genesis, "root genesis")
    if (
        set(genesis) != {"schema_version", "nonce_hex", "purpose", "terminal"}
        or genesis.get("schema_version") != "hswm-dgx-q1-evidence-root-genesis/v1"
        or type(genesis.get("nonce_hex")) is not str
        or len(genesis["nonce_hex"]) != 64
        or any(character not in "0123456789abcdef" for character in genesis["nonce_hex"])
        or genesis.get("purpose") != "FRESH_SINGLE_USE_LIVE_Q1_EVIDENCE_ROOT"
        or genesis.get("terminal") != "GENESIS_BOUND_BEFORE_ANY_LIVE_START"
    ):
        raise LiveQ1FreezeRefusal("root genesis semantic binding drifted")
    if type(inputs.call_order_seed) is not bytes or len(inputs.call_order_seed) != 32:
        raise LiveQ1FreezeRefusal("call-order seed must be exactly 32 bytes")
    if set(inputs.identities) != set(IDENTITY_NAMES):
        raise LiveQ1FreezeRefusal("all six exact identity blobs are required")
    identities = dict(inputs.identities)
    for name, raw in identities.items():
        _canonical_object(raw, name)
    model = _served_model(
        identities["model_identity_sha256"],
        identities["model_snapshot_manifest_sha256"],
    )
    q0_manifest, materials = q0_public_materials()
    class_by_id = {row["case_id"]: row["call_class"] for row in q0_manifest["cases"]}
    corpus: list[dict[str, Any]] = []
    for material in materials:
        call_class = class_by_id[material.case_id]
        request = bind_case_material({
            "case_id": material.case_id, "call_class": call_class,
            "instruction_sha256": sha256(material.instruction_bytes).hexdigest(),
            "model_input_sha256": sha256(material.model_input_bytes).hexdigest(),
            "response_schema_sha256": sha256(material.response_schema_bytes).hexdigest(),
            "rng_sha256": sha256(material.rng_bytes).hexdigest(),
            "max_output_tokens": material.max_output_tokens,
            "request_sha256": sha256(build_live_q1_request(model, call_class, material)).hexdigest(),
        }, material, model)
        corpus.append({"case_id": material.case_id, "call_class": call_class,
                       "request_sha256": sha256(request).hexdigest(),
                       "instruction_sha256": sha256(material.instruction_bytes).hexdigest(),
                       "model_input_sha256": sha256(material.model_input_bytes).hexdigest(),
                       "response_schema_sha256": sha256(material.response_schema_bytes).hexdigest(),
                       "rng_sha256": sha256(material.rng_bytes).hexdigest(),
                       "max_output_tokens": material.max_output_tokens})
    corpus_manifest = canonical_bytes({"schema_version": CORPUS_SCHEMA, "namespace": NAMESPACE,
                                       "q0_public_synthetic_manifest": q0_manifest, "corpus": corpus})
    attempts = [f"DNRD5-Q1L-{row['case_id'][-3:]}-R{rep:03d}" for row in corpus for rep in range(1, 5)]
    plan = {"schema_version": PLAN_SCHEMA, "namespace": NAMESPACE,
            "source": {"commit": source_commit, "tree": source_tree,
                       "ci_receipt_sha256": sha256(inputs.source_ci_receipt).hexdigest(),
                       "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"},
            "runner_version": RUNNER_VERSION, "corpus_manifest_sha256": sha256(corpus_manifest).hexdigest(),
            "corpus": corpus, "replicates": 4,
            "call_order": derive_live_q1_order(attempts, inputs.call_order_seed),
            "call_order_algorithm": "FROZEN_SHA256_FISHER_YATES_V1",
            "call_order_seed_hex": inputs.call_order_seed.hex(),
            "call_order_seed_sha256": sha256(inputs.call_order_seed).hexdigest(),
            "budget": 96, "zero_retry": True,
            "consumption_registry": dict(CONSUMPTION_REGISTRY),
            "identities": {name: sha256(raw).hexdigest() for name, raw in identities.items()},
            "verifier": {"source": {"commit": verifier_commit, "tree": verifier_tree,
                                        "ci_receipt_sha256": sha256(inputs.verifier_ci_receipt).hexdigest(),
                                       "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"},
                         "build_output_sha256": sha256(inputs.verifier_build).hexdigest()},
            "evidence_root_genesis_sha256": sha256(inputs.root_genesis).hexdigest(),
            "comparator": "EXACT_ASSISTANT_CONTENT_UTF8_WITH_CANONICAL_STRUCTURED_DIAGNOSTIC",
            "allowed_terminals": list(TERMINALS), "nonclaims": list(NONCLAIMS)}
    plan_raw = canonical_bytes(plan); validate_live_q1_plan(plan_raw)
    marker = make_live_q1_start_marker(plan_raw); validate_live_q1_start_marker(marker, plan_raw)
    artifacts: dict[str, bytes] = {"plan.json": plan_raw, "start_marker.json": marker,
        "corpus_manifest.json": corpus_manifest, "root_genesis.json": inputs.root_genesis,
        "provenance/source_ci_receipt_sha256.json": inputs.source_ci_receipt,
        "provenance/verifier_ci_receipt_sha256.json": inputs.verifier_ci_receipt,
        "provenance/verifier_build_output_sha256.json": inputs.verifier_build}
    artifacts |= {"identities/" + name + ".json": raw for name, raw in identities.items()}
    for material in materials:
        prefix = "materials/" + material.case_id + "/"
        artifacts |= {prefix + "instruction.txt": material.instruction_bytes, prefix + "model_input.json": material.model_input_bytes,
                      prefix + "response_schema.json": material.response_schema_bytes, prefix + "rng.bin": material.rng_bytes}
    closure = {"schema_version": FREEZE_SCHEMA, "namespace": NAMESPACE,
               "artifacts": [{"path": key, "sha256": sha256(value).hexdigest(), "byte_length": len(value)} for key, value in sorted(artifacts.items())]}
    artifacts["closure_manifest.json"] = canonical_bytes(closure)
    return artifacts


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def freeze_live_preregistration(output_dir: Path, inputs: LiveQ1PreregistrationInputs) -> dict[str, bytes]:
    artifacts = build_live_preregistration(inputs)
    if output_dir.exists() or not output_dir.parent.is_dir():
        raise LiveQ1FreezeRefusal("output directory must be a fresh child of an existing directory")
    output_dir.mkdir(mode=0o700)
    try:
        for relative, raw in artifacts.items():
            target = output_dir / relative; target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".freeze-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as handle: handle.write(raw); handle.flush(); os.fsync(handle.fileno())
                os.link(temporary, target)
            finally:
                try: os.unlink(temporary)
                except FileNotFoundError: pass
            _fsync_dir(target.parent)
        _fsync_dir(output_dir)
    except Exception:
        raise
    return artifacts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="freeze public synthetic live Q1 preregistration; no network/model calls")
    for name in ("source-commit", "source-tree", "source-ci", "verifier-commit", "verifier-tree", "verifier-ci", "verifier-build", "root-genesis", "seed-hex", "output"):
        parser.add_argument("--" + name, required=True)
    for name in IDENTITY_NAMES: parser.add_argument("--" + name.removesuffix("_sha256").replace("_", "-"), required=True)
    args = parser.parse_args(argv)
    try:
        identities = {name: Path(getattr(args, name.removesuffix("_sha256"))).read_bytes() for name in IDENTITY_NAMES}
        freeze_live_preregistration(Path(args.output), LiveQ1PreregistrationInputs(source_commit=args.source_commit, source_tree=args.source_tree, source_ci_receipt=Path(args.source_ci).read_bytes(), verifier_commit=args.verifier_commit, verifier_tree=args.verifier_tree, verifier_ci_receipt=Path(args.verifier_ci).read_bytes(), verifier_build=Path(args.verifier_build).read_bytes(), identities=identities, call_order_seed=bytes.fromhex(args.seed_hex), root_genesis=Path(args.root_genesis).read_bytes()))
    except (OSError, ValueError, LiveQ1FreezeRefusal): return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
