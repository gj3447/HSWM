"""No-network freezer for the fresh MI-2 launch-crossed identity."""
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
from _research.dgx_mi2.protocol import (
    ARMS, EXPECTED_MATERIAL_SHA256, EXPECTED_MI1_SELECTION, EXPECTED_REQUEST_SHA256, FREEZE_SCHEMA,
    GENESIS_SCHEMA, IDENTITY_NAMES, INSTRUMENT_ID, NAMESPACE, NONCLAIMS,
    PLAN_SCHEMA, RANDOMIZATION_CONTRACT, REGISTRY, RUNNER_VERSION, TERMINALS, Mi2Refusal,
    SCHEDULE_SELECTION_LIMIT, SCHEDULE_SELECTION_METHOD, make_mi2_start_marker, make_seed_material, select_schedule,
    validate_arm_identities, validate_mi2_plan,
)


class Mi2FreezeRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Mi2PreregistrationInputs:
    source_commit: str
    source_tree: str
    source_ci_receipt: bytes
    verifier_commit: str
    verifier_tree: str
    verifier_ci_receipt: bytes
    verifier_build: bytes
    arm_identities: Mapping[str, Mapping[str, bytes]]
    material_root: Path
    request_raw: bytes
    post_result_selection: Mapping[str, str]
    schedule_seed_material: bytes
    root_genesis: bytes


def fresh_schedule_seed_material() -> bytes:
    """Record the first direct-rejection-accepted independent CSPRNG draw."""
    while True:
        raw_draw = secrets.token_bytes(32)
        if int.from_bytes(raw_draw, "big") < SCHEDULE_SELECTION_LIMIT:
            return make_seed_material(raw_draw)


def fresh_root_genesis() -> bytes:
    nonce = secrets.token_bytes(32)
    return canonical_bytes({
        "schema_version": GENESIS_SCHEMA, "nonce_hex": nonce.hex(),
        "purpose": "FRESH_SINGLE_USE_QCASE024_MI2_LAUNCH_CROSSED_EVIDENCE_ROOT",
        "terminal": "GENESIS_BOUND_BEFORE_ANY_MI2_LIVE_START",
    })


def build_verifier_source_manifest(source_raw: bytes, *, source_path: str) -> bytes:
    if type(source_raw) is not bytes or not source_raw or source_path != "_research/dgx_mi2/independent_verifier.py":
        raise Mi2FreezeRefusal("MI-2 verifier source/path is absent")
    try:
        text = source_raw.decode("utf-8", "strict")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise Mi2FreezeRefusal("MI-2 verifier source is not valid UTF-8 Python") from error
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module)
    if any(item.startswith("_research.dgx_mi2") for item in imports):
        raise Mi2FreezeRefusal("MI-2 verifier imports a producer module")
    return canonical_bytes({
        "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-independent-verifier-build/v1",
        "source_path": source_path, "source_sha256": sha256(source_raw).hexdigest(),
        "source_utf8": text, "imports": sorted(imports),
        "terminal": "MI2_INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND",
    })


def _source(commit: str, tree: str, receipt: bytes, label: str) -> dict[str, str]:
    if (type(commit) is not str or len(commit) != 40 or type(tree) is not str or len(tree) != 40
            or any(char not in "0123456789abcdef" for char in commit + tree)
            or commit == "0" * 40 or tree == "0" * 40 or type(receipt) is not bytes or not receipt):
        raise Mi2FreezeRefusal(f"MI-2 {label} provenance drifted")
    try:
        parse_github_actions_ci_receipt(receipt, repository="gj3447/HSWM", commit=commit, tree=tree)
    except GitHubCiReceiptRefusal as error:
        raise Mi2FreezeRefusal(f"MI-2 {label} CI receipt binding drifted") from error
    return {"commit": commit, "tree": tree, "ci_receipt_sha256": sha256(receipt).hexdigest(), "ci_terminal": "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"}


def _read_material(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise Mi2FreezeRefusal("MI-2 material root unavailable")
    expected = set(EXPECTED_MATERIAL_SHA256)
    if {item.name for item in root.iterdir()} != expected:
        raise Mi2FreezeRefusal("MI-2 material directory key set drifted")
    material = {
        name: _read_regular_bytes(root / name, f"QCASE-024 material {name}")
        for name in expected
    }
    if {name: sha256(raw).hexdigest() for name, raw in material.items()} != EXPECTED_MATERIAL_SHA256:
        raise Mi2FreezeRefusal("MI-2 material bytes drifted")
    return material


def _validate_genesis(raw: bytes) -> None:
    try: value = parse_canonical(raw)
    except Exception as error: raise Mi2FreezeRefusal("MI-2 genesis is not canonical") from error
    if (type(value) is not dict or set(value) != {"schema_version", "nonce_hex", "purpose", "terminal"}
            or value.get("schema_version") != GENESIS_SCHEMA or type(value.get("nonce_hex")) is not str
            or len(value["nonce_hex"]) != 64 or value["nonce_hex"] == "0" * 64
            or any(char not in "0123456789abcdef" for char in value["nonce_hex"])
            or value.get("purpose") != "FRESH_SINGLE_USE_QCASE024_MI2_LAUNCH_CROSSED_EVIDENCE_ROOT"
            or value.get("terminal") != "GENESIS_BOUND_BEFORE_ANY_MI2_LIVE_START"):
        raise Mi2FreezeRefusal("MI-2 genesis boundary drifted")


def _validate_verifier_build(raw: bytes) -> None:
    try:
        value = parse_canonical(raw)
    except Exception as error:
        raise Mi2FreezeRefusal("MI-2 verifier build is not canonical") from error
    keys = {"schema_version", "source_path", "source_sha256", "source_utf8", "imports", "terminal"}
    if (type(value) is not dict or set(value) != keys
            or value.get("schema_version") != "hswm-dgx-qcase024-mi2-launch-crossed-independent-verifier-build/v1"
            or value.get("source_path") != "_research/dgx_mi2/independent_verifier.py"
            or type(value.get("source_utf8")) is not str or type(value.get("imports")) is not list
            or value.get("terminal") != "MI2_INDEPENDENT_VERIFIER_SOURCE_AND_IMPORTS_BOUND"
            or sha256(value["source_utf8"].encode()).hexdigest() != value.get("source_sha256")
            or any(type(item) is not str or item.startswith("_research.dgx_mi2") for item in value["imports"])
            or raw != build_verifier_source_manifest(value["source_utf8"].encode(), source_path=value["source_path"])):
        raise Mi2FreezeRefusal("MI-2 verifier build/source binding drifted")


def build_mi2_preregistration(inputs: Mi2PreregistrationInputs) -> dict[str, bytes]:
    try:
        source = _source(inputs.source_commit, inputs.source_tree, inputs.source_ci_receipt, "source")
        verifier_source = _source(inputs.verifier_commit, inputs.verifier_tree, inputs.verifier_ci_receipt, "verifier")
        if (source["commit"], source["tree"]) != (verifier_source["commit"], verifier_source["tree"]):
            raise Mi2FreezeRefusal("MI-2 source and verifier must share one published commit/tree")
        validate_arm_identities(inputs.arm_identities)
        material = _read_material(inputs.material_root)
        _validate_genesis(inputs.root_genesis)
    except (Mi2Refusal, OSError) as error:
        raise Mi2FreezeRefusal(str(error)) from error
    if type(inputs.request_raw) is not bytes or sha256(inputs.request_raw).hexdigest() != EXPECTED_REQUEST_SHA256:
        raise Mi2FreezeRefusal("MI-2 frozen instrumented request drifted")
    _validate_verifier_build(inputs.verifier_build)
    try:
        schedule_index, schedule = select_schedule(inputs.schedule_seed_material)
    except Mi2Refusal as error:
        raise Mi2FreezeRefusal(str(error)) from error
    selection = dict(inputs.post_result_selection)
    if selection != EXPECTED_MI1_SELECTION:
        raise Mi2FreezeRefusal("MI-2 post-result selection key set drifted")
    arms = {arm: {name: sha256(inputs.arm_identities[arm][name]).hexdigest() for name in IDENTITY_NAMES} for arm in ARMS}
    plan = {
        "schema_version": PLAN_SCHEMA, "namespace": NAMESPACE, "instrument_id": INSTRUMENT_ID,
        "source": source, "runner_version": RUNNER_VERSION,
        "material": {"case_id": "QCASE-024", "instruction_sha256": EXPECTED_MATERIAL_SHA256["instruction.txt"], "model_input_sha256": EXPECTED_MATERIAL_SHA256["model_input.json"], "response_schema_sha256": EXPECTED_MATERIAL_SHA256["response_schema.json"], "rng_sha256": EXPECTED_MATERIAL_SHA256["rng.bin"], "max_output_tokens": 256},
        "request_sha256": sha256(inputs.request_raw).hexdigest(), "post_result_selection": selection,
        "arms": arms,
        "schedule_selection": {"method": SCHEDULE_SELECTION_METHOD, "seed_material_sha256": sha256(inputs.schedule_seed_material).hexdigest(), "schedule_index": schedule_index, "schedule": list(schedule), "schedule_domain_count": 400},
        "block_order": [], "attempt_ids": [], "replicates_per_launch": 2, "fresh_launches": 24,
        "primary_posts": 24, "budget": 48, "zero_retry": True, "no_refill_resume_or_early_stop": True,
        "consumption_registry": REGISTRY,
        "randomization": RANDOMIZATION_CONTRACT,
        "verifier": {"source": verifier_source, "build_output_sha256": sha256(inputs.verifier_build).hexdigest()},
        "evidence_root_genesis_sha256": sha256(inputs.root_genesis).hexdigest(),
        "allowed_terminals": list(TERMINALS), "nonclaims": list(NONCLAIMS),
    }
    # Build order-dependent fields only after the canonical schedule is fixed.
    from _research.dgx_mi2.protocol import attempt_ids, block_order
    plan["block_order"] = block_order(schedule)
    plan["attempt_ids"] = attempt_ids(schedule)
    plan_raw = canonical_bytes(plan)
    try: validate_mi2_plan(plan_raw, seed_material_raw=inputs.schedule_seed_material)
    except Mi2Refusal as error: raise Mi2FreezeRefusal(str(error)) from error
    marker = make_mi2_start_marker(plan_raw, inputs.schedule_seed_material)
    artifacts: dict[str, bytes] = {
        "plan.json": plan_raw, "start_marker.json": marker, "schedule_seed_material.json": inputs.schedule_seed_material,
        "root_genesis.json": inputs.root_genesis, "request.json": inputs.request_raw,
        "provenance/source_ci_receipt_sha256.json": inputs.source_ci_receipt,
        "provenance/verifier_ci_receipt_sha256.json": inputs.verifier_ci_receipt,
        "provenance/verifier_build_output_sha256.json": inputs.verifier_build,
    }
    artifacts |= {"materials/QCASE-024/" + name: raw for name, raw in material.items()}
    artifacts |= {f"identities/{arm}/{name}.json": raw for arm in ARMS for name, raw in inputs.arm_identities[arm].items()}
    closure = {"schema_version": FREEZE_SCHEMA, "namespace": NAMESPACE,
               "artifacts": [{"path": path, "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)} for path, raw in sorted(artifacts.items())]}
    artifacts["closure_manifest.json"] = canonical_bytes(closure)
    return artifacts


def freeze_mi2_preregistration(output_dir: Path, inputs: Mi2PreregistrationInputs) -> dict[str, bytes]:
    artifacts = build_mi2_preregistration(inputs)
    if (not isinstance(output_dir, Path) or output_dir.exists() or output_dir.is_symlink()
            or output_dir.parent.is_symlink() or not output_dir.parent.is_dir()):
        raise Mi2FreezeRefusal("MI-2 output directory must be a fresh child")
    def sync(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    output_dir.mkdir(mode=0o700)
    sync(output_dir.parent)
    for relative, raw in artifacts.items():
        target = output_dir / PurePosixPath(relative)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".mi2-freeze-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
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


def _read_regular_bytes(path: Path, label: str) -> bytes:
    """Read one caller-selected regular file without following a final symlink."""
    if not isinstance(path, Path) or path.is_symlink():
        raise Mi2FreezeRefusal(f"MI-2 {label} is unavailable or linked")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise Mi2FreezeRefusal(f"MI-2 {label} cannot be read") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise Mi2FreezeRefusal(f"MI-2 {label} is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1 << 20):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _load_arm_identities(root: Path) -> dict[str, dict[str, bytes]]:
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise Mi2FreezeRefusal("MI-2 arm identity root is unavailable or linked")
    try:
        if {item.name for item in root.iterdir()} != set(ARMS):
            raise Mi2FreezeRefusal("MI-2 arm identity root key set drifted")
    except OSError as error:
        raise Mi2FreezeRefusal("MI-2 arm identity root cannot be read") from error
    result: dict[str, dict[str, bytes]] = {}
    expected = {f"{name}.json" for name in IDENTITY_NAMES}
    for arm in ARMS:
        arm_root = root / arm
        if arm_root.is_symlink() or not arm_root.is_dir():
            raise Mi2FreezeRefusal("MI-2 arm identity directory is unavailable or linked")
        try:
            if {item.name for item in arm_root.iterdir()} != expected:
                raise Mi2FreezeRefusal("MI-2 arm identity directory key set drifted")
        except OSError as error:
            raise Mi2FreezeRefusal("MI-2 arm identity directory cannot be read") from error
        result[arm] = {
            name: _read_regular_bytes(arm_root / f"{name}.json", f"{arm} {name}")
            for name in IDENTITY_NAMES
        }
    return result


def _checked_in_verifier_bytes(repo_root: Path) -> bytes:
    if not isinstance(repo_root, Path) or repo_root.is_symlink() or not repo_root.is_dir():
        raise Mi2FreezeRefusal("MI-2 repository root is unavailable or linked")
    target = repo_root / "_research/dgx_mi2/independent_verifier.py"
    try:
        if target.parent.resolve() != (repo_root / "_research/dgx_mi2").resolve() or not target.is_relative_to(repo_root.resolve()):
            raise Mi2FreezeRefusal("MI-2 checked-in verifier path escaped repository root")
    except (OSError, ValueError) as error:
        raise Mi2FreezeRefusal("MI-2 checked-in verifier path is unavailable") from error
    return _read_regular_bytes(target, "checked-in verifier")


def _git_output(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, check=False,
        )
    except OSError as error:
        raise Mi2FreezeRefusal("MI-2 git is unavailable for preregistration chronology check") from error
    if completed.returncode != 0:
        raise Mi2FreezeRefusal("MI-2 repository chronology check failed")
    return completed.stdout.rstrip("\n")


def _verify_cli_checkout(repo_root: Path, *, source_commit: str, source_tree: str,
                         verifier_commit: str, verifier_tree: str) -> bytes:
    """Require one clean checkout to bind both frozen source identities."""
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise Mi2FreezeRefusal("MI-2 repo root is unavailable or linked")
    try:
        if Path(_git_output(repo_root, "rev-parse", "--show-toplevel")).resolve() != repo_root.resolve():
            raise Mi2FreezeRefusal("MI-2 repo root is not the exact Git worktree root")
    except OSError as error:
        raise Mi2FreezeRefusal("MI-2 repo root cannot be resolved") from error
    head = _git_output(repo_root, "rev-parse", "HEAD")
    tree = _git_output(repo_root, "rev-parse", "HEAD^{tree}")
    dirty = _git_output(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if (dirty or head != source_commit or head != verifier_commit
            or tree != source_tree or tree != verifier_tree):
        raise Mi2FreezeRefusal("MI-2 repo checkout commit/tree/cleanliness chronology drifted")
    return _checked_in_verifier_bytes(repo_root)


def main(argv: Sequence[str] | None = None) -> int:
    """Freeze one fresh, local-only MI-2 preregistration without shell snippets."""
    parser = argparse.ArgumentParser(
        description="freeze a no-network DNRD5 QCASE-024 MI-2 preregistration",
    )
    parser.add_argument("--output-dir", required=True, type=_path_argument,
                        help="fresh absolute child directory for the immutable freeze")
    parser.add_argument("--repo-root", required=True, type=_path_argument,
                        help="clean absolute Git worktree root matching both source identities")
    parser.add_argument("--material-root", required=True, type=_path_argument,
                        help="checked-in Q1 QCASE-024 materials directory")
    parser.add_argument("--request-path", required=True, type=_path_argument,
                        help="checked-in immutable MI-1 request.json")
    parser.add_argument("--arm-identities-root", required=True, type=_path_argument,
                        help="checked-in immutable MI-1 identities directory")
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
    inputs = Mi2PreregistrationInputs(
        source_commit=args.source_commit, source_tree=args.source_tree, source_ci_receipt=source_ci,
        verifier_commit=args.verifier_commit, verifier_tree=args.verifier_tree, verifier_ci_receipt=verifier_ci,
        verifier_build=build_verifier_source_manifest(
            verifier_raw, source_path="_research/dgx_mi2/independent_verifier.py"),
        arm_identities=_load_arm_identities(args.arm_identities_root), material_root=args.material_root,
        request_raw=_read_regular_bytes(args.request_path, "immutable MI-1 request"),
        post_result_selection=dict(EXPECTED_MI1_SELECTION),
        schedule_seed_material=fresh_schedule_seed_material(), root_genesis=fresh_root_genesis(),
    )
    artifacts = freeze_mi2_preregistration(args.output_dir, inputs)
    print(canonical_bytes({
        "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-freeze-cli-result/v1",
        "output_dir": str(args.output_dir),
        "plan_sha256": sha256(artifacts["plan.json"]).hexdigest(),
        "start_marker_sha256": sha256(artifacts["start_marker.json"]).hexdigest(),
        "schedule_seed_material_sha256": sha256(artifacts["schedule_seed_material.json"]).hexdigest(),
        "terminal": "FRESH_MI2_PREREGISTRATION_FROZEN_NO_NETWORK",
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
