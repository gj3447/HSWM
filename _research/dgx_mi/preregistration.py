"""No-network freezer for the separately preregistered QCASE-024 MI-1 study."""
from __future__ import annotations

import ast
import argparse
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import subprocess
import tempfile
from typing import Mapping, Sequence

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_q1.github_ci_receipt import GitHubCiReceiptRefusal, parse_github_actions_ci_receipt
from _research.dgx_mi.protocol import (
    ARMS, BLOCKS, EXPECTED_Q1_SELECTION, FREEZE_SCHEMA, IDENTITY_NAMES, NAMESPACE, NONCLAIMS, PINNED,
    PLAN_SCHEMA, REQUIRED_ENV, RUNNER_VERSION, SERVER_PREFIX, TERMINALS, USAGE_NORMALIZATION,
    MiRefusal, REGISTRY, build_mi_request, make_mi_start_marker,
    validate_arm_identities, validate_mi_plan, validate_mi_start_marker,
)

CORPUS_SCHEMA = "hswm-dgx-qcase024-mi-material-provenance/v3"
VERIFIER_SCHEMA = "hswm-dgx-qcase024-mi-independent-verifier-build/v3"


class MiFreezeRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class MiPreregistrationInputs:
    source_commit: str
    source_tree: str
    source_ci_receipt: bytes
    verifier_commit: str
    verifier_tree: str
    verifier_ci_receipt: bytes
    verifier_build: bytes
    arm_identities: Mapping[str, Mapping[str, bytes]]
    qcase024_material_root: Path
    post_result_selection: Mapping[str, str]
    root_genesis: bytes


def _git(value: str, label: str) -> str:
    if type(value) is not str or len(value) != 40 or value == "0" * 40 or any(c not in "0123456789abcdef" for c in value):
        raise MiFreezeRefusal(f"{label} must be a non-placeholder Git SHA-1")
    return value


def _sha(value: str, label: str) -> str:
    if type(value) is not str or len(value) != 64 or value == "0" * 64 or any(c not in "0123456789abcdef" for c in value):
        raise MiFreezeRefusal(f"{label} must be a non-placeholder SHA-256")
    return value


def _ci(raw: bytes, commit: str, tree: str, label: str) -> None:
    try:
        parse_github_actions_ci_receipt(raw, repository="gj3447/HSWM", commit=commit, tree=tree)
    except GitHubCiReceiptRefusal as error:
        raise MiFreezeRefusal(f"{label} semantic binding drifted") from error


def build_verifier_source_manifest(source_raw: bytes, *, source_path: str) -> bytes:
    """Bind a standalone future MI verifier without importing its producer."""
    if type(source_raw) is not bytes or not source_raw or type(source_path) is not str or not source_path:
        raise MiFreezeRefusal("MI verifier source/path is absent")
    try:
        text = source_raw.decode("utf-8", errors="strict")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise MiFreezeRefusal("MI verifier source is not valid UTF-8 Python") from error
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module)
    forbidden = {"_research.dgx_mi", "_research.dgx_mi.protocol", "_research.dgx_mi.preregistration", "_research.dgx_mi.runner", "_research.dgx_mi.launcher", "_research.dgx_mi.experiment"}
    if any(item == "_research.dgx_mi" or item.startswith("_research.dgx_mi.") for item in imports) or imports & forbidden:
        raise MiFreezeRefusal("MI verifier imports a producer module")
    return canonical_bytes({"schema_version": VERIFIER_SCHEMA, "source_path": source_path,
        "source_sha256": sha256(source_raw).hexdigest(), "source_utf8": text,
        "imports": sorted(imports), "terminal": "MI_INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND"})


def _validate_verifier_build(raw: bytes) -> dict[str, object]:
    try: item = parse_canonical(raw)
    except Exception as error: raise MiFreezeRefusal("MI verifier build is not canonical JSON") from error
    if (type(item) is not dict or set(item) != {"schema_version", "source_path", "source_sha256", "source_utf8", "imports", "terminal"}
            or item.get("schema_version") != VERIFIER_SCHEMA or type(item.get("source_path")) is not str
            or item.get("source_path") != "_research/dgx_mi/independent_verifier.py" or type(item.get("source_utf8")) is not str
            or sha256(item["source_utf8"].encode()).hexdigest() != item.get("source_sha256")
            or item.get("terminal") != "MI_INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND"
            or raw != build_verifier_source_manifest(item["source_utf8"].encode(), source_path=item["source_path"])):
        raise MiFreezeRefusal("MI verifier build/source binding drifted")
    return item


def _read_regular_bytes(path: Path, label: str) -> bytes:
    """Read a caller-selected input once, rejecting linked or non-file inputs."""
    if not isinstance(path, Path) or path.is_symlink():
        raise MiFreezeRefusal(f"{label} is unavailable or linked")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise MiFreezeRefusal(f"{label} cannot be read") from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise MiFreezeRefusal(f"{label} is not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk: return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _checked_in_verifier_bytes(repo_root: Path | None = None) -> bytes:
    """Read the one repository-owned verifier source through a closed path."""
    root = Path(__file__).resolve().parents[2] if repo_root is None else repo_root
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise MiFreezeRefusal("checked-in MI verifier repository root is unavailable or linked")
    target = root / "_research/dgx_mi/independent_verifier.py"
    try:
        if target.parent.resolve() != (root / "_research/dgx_mi").resolve() or not target.is_relative_to(root.resolve()):
            raise MiFreezeRefusal("checked-in MI verifier path escaped repository root")
    except (OSError, ValueError) as error:
        raise MiFreezeRefusal("checked-in MI verifier path is unavailable") from error
    return _read_regular_bytes(target, "checked-in MI verifier")


def derive_q1_v3_arm_identities(identity_root: Path) -> dict[str, dict[str, bytes]]:
    """Derive the sole two MI arms from Q1-v3's exact immutable identities.

    The five non-runtime identity byte strings are copied without reserialization.
    Runtime is reconstructed only to add MI's processed-logprob controls and one
    explicit, mutually-exclusive async-scheduling flag per arm.
    """
    if not isinstance(identity_root, Path) or identity_root.is_symlink() or not identity_root.is_dir():
        raise MiFreezeRefusal("Q1 v3 identity root is unavailable or linked")
    expected_paths = {f"{name}.json" for name in IDENTITY_NAMES}
    try:
        actual_paths = {item.name for item in identity_root.iterdir()}
    except OSError as error:
        raise MiFreezeRefusal("Q1 v3 identity root cannot be read") from error
    if actual_paths != expected_paths:
        raise MiFreezeRefusal("Q1 v3 identity directory key set drifted")
    base = {name: _read_regular_bytes(identity_root / f"{name}.json", f"Q1 v3 {name}") for name in IDENTITY_NAMES}
    try:
        q1_runtime = parse_canonical(base["runtime_identity_sha256"])
    except Exception as error:
        raise MiFreezeRefusal("Q1 v3 runtime identity is not canonical") from error
    if type(q1_runtime) is not dict:
        raise MiFreezeRefusal("Q1 v3 runtime identity must be an object")
    runtime_common = dict(q1_runtime)
    runtime_common.update({
        "schema_version": "hswm-dgx-qcase024-mi-runtime-identity/v3",
        "container_image": PINNED["image"], "image_id": PINNED["image_id"],
        "vllm_version": PINNED["vllm"], "gpu_uuid": PINNED["gpu_uuid"],
        "gpu_name": PINNED["gpu_name"], "gpu_driver_version": PINNED["driver"],
        "gpu_compute_capability": PINNED["cc"], "endpoint": PINNED["endpoint"],
        "served_model": PINNED["model"], "model_revision": PINNED["revision"],
        "model_snapshot_manifest_sha256": PINNED["snapshot"], "max_model_len": 32768,
        "max_num_seqs": 1, "gpu_memory_utilization_milli": 500, "prefix_cache": False,
        "enforce_eager": True, "batch_invariant": False, "v1_multiprocessing": False,
        "model_loading_offline": True, "generation_config": "vllm", "engine_seed": 0,
        "language_model_only": True, "container_internal_port": 8000,
        "container_network_mode": "bridge", "container_ipc_mode": "private",
        "host_publish_ip": "127.0.0.1", "required_environment": list(REQUIRED_ENV),
        "max_logprobs": 20, "logprobs_mode": "processed_logprobs",
    })

    identities: dict[str, dict[str, bytes]] = {}
    for arm, enabled in (("ASYNC_ENABLED", True), ("ASYNC_DISABLED", False)):
        runtime = dict(runtime_common)
        runtime["async_scheduling"] = enabled
        runtime["server_arguments"] = [*SERVER_PREFIX, "--async-scheduling" if enabled else "--no-async-scheduling"]
        identities[arm] = {**base, "runtime_identity_sha256": canonical_bytes(runtime)}
    try:
        validate_arm_identities(identities)
    except MiRefusal as error:
        raise MiFreezeRefusal("Q1 v3 identities cannot derive the exact MI arms") from error
    return identities


def fresh_root_genesis() -> bytes:
    """Create an internally generated, single-use 32-byte evidence-root nonce."""
    return canonical_bytes({
        "schema_version": "hswm-dgx-qcase024-mi-evidence-root-genesis/v3",
        "nonce_hex": secrets.token_bytes(32).hex(),
        "purpose": "FRESH_SINGLE_USE_QCASE024_MI_USAGE_V3_EVIDENCE_ROOT",
        "terminal": "GENESIS_BOUND_BEFORE_ANY_MI_LIVE_START",
    })


def load_qcase024_material(root: Path) -> dict[str, bytes]:
    """Read exactly the four checked-in Q1-v3 QCASE-024 source material files."""
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise MiFreezeRefusal("QCASE-024 v3 material root is unavailable")
    names = ("instruction.txt", "model_input.json", "response_schema.json", "rng.bin")
    result: dict[str, bytes] = {}
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise MiFreezeRefusal("QCASE-024 source material is unavailable")
        result[name] = path.read_bytes()
    try:
        value = parse_canonical(result["model_input.json"])
    except Exception as error:
        raise MiFreezeRefusal("QCASE-024 model input is not canonical") from error
    if type(value) is not dict or value.get("freshProbe", {}).get("case") != "QCASE-024":
        raise MiFreezeRefusal("source material is not QCASE-024")
    if len(result["rng.bin"]) != 32:
        raise MiFreezeRefusal("QCASE-024 RNG material drifted")
    return result


def _model_for_arm(identities: Mapping[str, bytes]) -> str:
    try: model = parse_canonical(identities["model_identity_sha256"])
    except Exception as error: raise MiFreezeRefusal("MI model identity is not canonical") from error
    if type(model) is not dict or type(model.get("model")) is not str or not model["model"]:
        raise MiFreezeRefusal("MI model identity lacks served model")
    return model["model"]


def _genesis(raw: bytes) -> None:
    try: item = parse_canonical(raw)
    except Exception as error: raise MiFreezeRefusal("MI root genesis is not canonical") from error
    if (type(item) is not dict or set(item) != {"schema_version", "nonce_hex", "purpose", "terminal"}
            or item.get("schema_version") != "hswm-dgx-qcase024-mi-evidence-root-genesis/v3"
            or type(item.get("nonce_hex")) is not str or len(item["nonce_hex"]) != 64 or item["nonce_hex"] == "0" * 64
            or any(c not in "0123456789abcdef" for c in item["nonce_hex"])
            or item.get("purpose") != "FRESH_SINGLE_USE_QCASE024_MI_USAGE_V3_EVIDENCE_ROOT"
            or item.get("terminal") != "GENESIS_BOUND_BEFORE_ANY_MI_LIVE_START"):
        raise MiFreezeRefusal("MI root genesis binding drifted")


def build_mi_preregistration(inputs: MiPreregistrationInputs) -> dict[str, bytes]:
    if type(inputs) is not MiPreregistrationInputs: raise MiFreezeRefusal("inputs must be exact MiPreregistrationInputs")
    source_commit, source_tree = _git(inputs.source_commit, "source commit"), _git(inputs.source_tree, "source tree")
    verifier_commit, verifier_tree = _git(inputs.verifier_commit, "verifier commit"), _git(inputs.verifier_tree, "verifier tree")
    _ci(inputs.source_ci_receipt, source_commit, source_tree, "source CI")
    _ci(inputs.verifier_ci_receipt, verifier_commit, verifier_tree, "verifier CI")
    verifier_build = _validate_verifier_build(inputs.verifier_build)
    if verifier_build["source_utf8"].encode("utf-8") != _checked_in_verifier_bytes():
        raise MiFreezeRefusal("verifier build does not bind checked-in MI verifier bytes")
    _genesis(inputs.root_genesis)
    try: validate_arm_identities(inputs.arm_identities)
    except MiRefusal as error: raise MiFreezeRefusal("MI arm identity binding drifted") from error
    material = load_qcase024_material(inputs.qcase024_material_root)
    request = build_mi_request(_model_for_arm(inputs.arm_identities[ARMS[0]]), material)
    if _model_for_arm(inputs.arm_identities[ARMS[1]]) != _model_for_arm(inputs.arm_identities[ARMS[0]]):
        raise MiFreezeRefusal("MI arms must serve the same model")
    selection_names = {"q1_source_commit", "q1_result_commit", "q1_v3_plan_sha256", "q1_live_receipt_sha256", "q1_evidence_receipt_sha256", "q1_exact_ledger_sha256", "q1_result_projection_sha256", "selected_request_sha256", "q1_terminal", "selected_case", "selection_status", "selection_basis"}
    if set(inputs.post_result_selection) != selection_names:
        raise MiFreezeRefusal("MI post-result selection key set drifted")
    selection = dict(inputs.post_result_selection)
    for name in ("q1_source_commit", "q1_result_commit"):
        _git(selection[name], name)
    for name in selection_names - {"q1_source_commit", "q1_result_commit", "q1_terminal", "selected_case", "selection_status", "selection_basis"}:
        _sha(selection[name], name)
    descriptors = {name.removesuffix(".txt").removesuffix(".json").removesuffix(".bin") + "_sha256": sha256(raw).hexdigest() for name, raw in material.items()}
    plan = {
        "schema_version": PLAN_SCHEMA, "namespace": NAMESPACE, "source": {"commit": source_commit, "tree": source_tree,
            "ci_receipt_sha256": sha256(inputs.source_ci_receipt).hexdigest(), "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"},
        "runner_version": RUNNER_VERSION,
        "material": {"case_id": "QCASE-024", "instruction_sha256": descriptors["instruction_sha256"],
            "model_input_sha256": descriptors["model_input_sha256"], "response_schema_sha256": descriptors["response_schema_sha256"],
            "rng_sha256": descriptors["rng_sha256"], "max_output_tokens": 256},
        "request_sha256": sha256(request).hexdigest(),
        "post_result_selection": selection,
        "arms": {arm: {name: sha256(raw).hexdigest() for name, raw in inputs.arm_identities[arm].items()} for arm in ARMS},
        "block_order": [{"arm": arm, "block_id": block} for arm, block in BLOCKS],
        "attempt_ids": [f"MI-024-V3-{arm}-{block}-R{rep:03d}" for arm, block in BLOCKS for rep in range(1, 5)],
        "attempts_per_block": 4, "budget": 16, "zero_retry": True, "consumption_registry": dict(REGISTRY),
        "usage_normalization": dict(USAGE_NORMALIZATION),
        "verifier": {"source": {"commit": verifier_commit, "tree": verifier_tree,
            "ci_receipt_sha256": sha256(inputs.verifier_ci_receipt).hexdigest(), "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"},
            "build_output_sha256": sha256(inputs.verifier_build).hexdigest()},
        "evidence_root_genesis_sha256": sha256(inputs.root_genesis).hexdigest(),
        "allowed_terminals": list(TERMINALS),
        "nonclaims": list(NONCLAIMS),
    }
    plan_raw = canonical_bytes(plan); validate_mi_plan(plan_raw)
    marker = make_mi_start_marker(plan_raw); validate_mi_start_marker(marker, plan_raw)
    material_manifest = canonical_bytes({"schema_version": CORPUS_SCHEMA, "namespace": NAMESPACE,
        "source": "Q1_V3_CHECKED_IN_QCASE024_MATERIAL", "case_id": "QCASE-024",
        "files": [{"path": name, "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)} for name, raw in sorted(material.items())]})
    artifacts: dict[str, bytes] = {"plan.json": plan_raw, "start_marker.json": marker, "root_genesis.json": inputs.root_genesis,
        "material_provenance.json": material_manifest, "request.json": request,
        "provenance/source_ci_receipt_sha256.json": inputs.source_ci_receipt,
        "provenance/verifier_ci_receipt_sha256.json": inputs.verifier_ci_receipt,
        "provenance/verifier_build_output_sha256.json": inputs.verifier_build}
    artifacts |= {"materials/QCASE-024/" + name: raw for name, raw in material.items()}
    for arm in ARMS:
        artifacts |= {f"identities/{arm}/{name}.json": raw for name, raw in inputs.arm_identities[arm].items()}
    closure = {"schema_version": FREEZE_SCHEMA, "namespace": NAMESPACE,
        "artifacts": [{"path": path, "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)} for path, raw in sorted(artifacts.items())]}
    artifacts["closure_manifest.json"] = canonical_bytes(closure)
    return artifacts


def freeze_mi_preregistration(output_dir: Path, inputs: MiPreregistrationInputs) -> dict[str, bytes]:
    artifacts = build_mi_preregistration(inputs)
    if output_dir.exists() or not output_dir.parent.is_dir(): raise MiFreezeRefusal("output directory must be a fresh child")
    def sync(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    output_dir.mkdir(mode=0o700)
    sync(output_dir.parent)
    for relative, raw in artifacts.items():
        target = output_dir / PurePosixPath(relative); target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".mi-freeze-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle: handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, target)
        finally:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
        sync(target.parent)
    sync(output_dir)
    return artifacts


def _path_argument(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("paths must be absolute")
    return path


def _git_output(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, check=False,
        )
    except OSError as error:
        raise MiFreezeRefusal("git is unavailable for preregistration chronology check") from error
    if completed.returncode != 0:
        raise MiFreezeRefusal("repository chronology check failed")
    return completed.stdout.rstrip("\n")


def _verify_cli_checkout(repo_root: Path, *, source_commit: str, source_tree: str,
                         verifier_commit: str, verifier_tree: str) -> bytes:
    """Bind the production freeze to one clean checkout and its verifier blob."""
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise MiFreezeRefusal("repo root is unavailable or linked")
    try:
        declared_root = Path(_git_output(repo_root, "rev-parse", "--show-toplevel"))
        if declared_root.resolve() != repo_root.resolve():
            raise MiFreezeRefusal("repo root is not the exact Git worktree root")
    except OSError as error:
        raise MiFreezeRefusal("repo root cannot be resolved") from error
    head = _git_output(repo_root, "rev-parse", "HEAD")
    tree = _git_output(repo_root, "rev-parse", "HEAD^{tree}")
    dirty = _git_output(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty or head != source_commit or head != verifier_commit or tree != source_tree or tree != verifier_tree:
        raise MiFreezeRefusal("repo checkout commit/tree/cleanliness chronology drifted")
    return _checked_in_verifier_bytes(repo_root)


def main(argv: Sequence[str] | None = None) -> int:
    """Freeze one fresh, local-only MI preregistration directory."""
    parser = argparse.ArgumentParser(
        description="freeze a no-network DNRD5 QCASE-024 MI preregistration",
    )
    parser.add_argument("--output-dir", required=True, type=_path_argument,
                        help="fresh absolute child directory for the immutable freeze")
    parser.add_argument("--repo-root", required=True, type=_path_argument,
                        help="clean absolute Git worktree root matching both source identities")
    parser.add_argument("--qcase024-material-root", required=True, type=_path_argument,
                        help="checked-in Q1-v3 materials/QCASE-024 directory")
    parser.add_argument("--q1-identity-root", required=True, type=_path_argument,
                        help="checked-in Q1-v3 identities directory")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--source-ci-receipt", required=True, type=_path_argument)
    parser.add_argument("--verifier-commit", required=True)
    parser.add_argument("--verifier-tree", required=True)
    parser.add_argument("--verifier-ci-receipt", required=True, type=_path_argument)
    args = parser.parse_args(argv)
    source_ci = _read_regular_bytes(args.source_ci_receipt, "source CI receipt")
    verifier_ci = _read_regular_bytes(args.verifier_ci_receipt, "verifier CI receipt")
    verifier_raw = _verify_cli_checkout(
        args.repo_root, source_commit=args.source_commit, source_tree=args.source_tree,
        verifier_commit=args.verifier_commit, verifier_tree=args.verifier_tree,
    )
    inputs = MiPreregistrationInputs(
        source_commit=args.source_commit, source_tree=args.source_tree, source_ci_receipt=source_ci,
        verifier_commit=args.verifier_commit, verifier_tree=args.verifier_tree, verifier_ci_receipt=verifier_ci,
        verifier_build=build_verifier_source_manifest(
            verifier_raw, source_path="_research/dgx_mi/independent_verifier.py"),
        arm_identities=derive_q1_v3_arm_identities(args.q1_identity_root),
        qcase024_material_root=args.qcase024_material_root,
        post_result_selection=dict(EXPECTED_Q1_SELECTION), root_genesis=fresh_root_genesis(),
    )
    artifacts = freeze_mi_preregistration(args.output_dir, inputs)
    print(canonical_bytes({
        "schema_version": "hswm-dgx-qcase024-mi-freeze-cli-result/v3",
        "output_dir": str(args.output_dir),
        "plan_sha256": sha256(artifacts["plan.json"]).hexdigest(),
        "start_marker_sha256": sha256(artifacts["start_marker.json"]).hexdigest(),
        "terminal": "FRESH_MI_PREREGISTRATION_FROZEN_NO_NETWORK",
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
