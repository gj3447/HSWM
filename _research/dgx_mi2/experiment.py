"""Checked-in MI-2 launch entrypoint; DGX invokes it through ``hswm-run``."""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi2.launcher import Mi2LeaseSpec, global_quiescence
from _research.dgx_mi2.protocol import ARMS, IDENTITY_NAMES, REGISTRY, validate_arm_identities, validate_mi2_plan, validate_mi2_start_marker
from _research.dgx_mi2.runner import Mi2Runner, _load_freeze, _validate_global_quiescence
from _research.dgx_q1.github_ci_receipt import parse_github_actions_ci_receipt
from _research.dgx_q1.model_snapshot_manifest import build_model_snapshot_manifest


def make_specs(*, plan_raw: bytes, arm_runtime: Mapping[str, Mapping[str, Any]], cache_root: Path,
               lock_path: Path, model_snapshot: Path) -> dict[int, Mi2LeaseSpec]:
    plan = validate_mi2_plan(plan_raw)
    if cache_root.exists() or not cache_root.parent.is_dir() or set(arm_runtime) != set(ARMS):
        raise ValueError("MI-2 fresh cache/arm runtime boundary")
    cache_root.mkdir(mode=0o700); result: dict[int, Mi2LeaseSpec] = {}
    needed = {"endpoint","image","image_id","gpu_uuid","served_model","model_revision","max_model_len","gpu_memory_utilization_milli","model_repository","snapshot_manifest_raw"}
    for index, row in enumerate(plan["block_order"], 1):
        runtime = arm_runtime[row["arm"]]
        if set(runtime) != needed: raise ValueError("MI-2 runtime keys")
        base = cache_root / f"launch-{index:02d}"; hf, compile = base / "hf", base / "compile"
        hf.mkdir(parents=True,mode=0o700); compile.mkdir(mode=0o700)
        result[index] = Mi2LeaseSpec(pair_id=row["pair_id"], launch_index=index, arm=row["arm"],
            container_name=f"hswm-mi2-{index:02d}", lock_path=lock_path, model_snapshot=model_snapshot,
            hf_cache=hf, compile_cache=compile, async_scheduling=row["arm"] == "ASYNC_ENABLED", **runtime)
    return result

_SHARED_CONTAINERS = ("vllm-receiver", "vllm", "comfyui-10eros")
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")


def _docker(*args: str) -> bytes:
    try:
        result = subprocess.run(("docker", *args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as error:
        raise RuntimeError("MI-2 Docker lifecycle command unavailable") from error
    if result.returncode != 0:
        raise RuntimeError("MI-2 Docker lifecycle command failed: " + args[0])
    return result.stdout


def _container_state(name: str) -> tuple[str, bool, bool]:
    raw = _docker("inspect", "--format", "{{.Id}}\t{{.State.Running}}\t{{.HostConfig.AutoRemove}}", name).decode("utf-8", "strict").strip()
    fields = raw.split("\t")
    if len(fields) != 3 or _CONTAINER_ID.fullmatch(fields[0]) is None or any(value not in {"true", "false"} for value in fields[1:]):
        raise RuntimeError("MI-2 Docker container state malformed")
    return fields[0], fields[1] == "true", fields[2] == "true"


def _active_shared_containers() -> list[tuple[str, str]]:
    """Snapshot every active Docker container before changing any one of them."""
    names = [line.strip() for line in _docker("ps", "--format", "{{.Names}}").decode("utf-8", "strict").splitlines() if line.strip()]
    if len(set(names)) != len(names) or any(name not in _SHARED_CONTAINERS for name in names):
        raise RuntimeError("MI-2 refuses unknown or ambiguous active Docker container")
    snapshot: list[tuple[str, str]] = []
    for name in _SHARED_CONTAINERS:
        if name in names:
            identifier, running, auto_remove = _container_state(name)
            if not running or auto_remove:
                raise RuntimeError("MI-2 Docker active-container snapshot drifted")
            snapshot.append((name, identifier))
    return snapshot


def _preflight_services() -> None:
    """Read-only Docker ownership gate; host listeners (including Ollama) stay untouched."""
    _active_shared_containers()


def _stop_services(stopped: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    stopped = [] if stopped is None else stopped
    if stopped:
        raise ValueError("MI-2 service restore set must start empty")
    stopped.extend(_active_shared_containers())
    try:
        for name, identifier in stopped:
            _docker("stop", "--time", "30", identifier)
            observed_id, running, auto_remove = _container_state(name)
            if observed_id != identifier or running or auto_remove:
                raise RuntimeError("MI-2 Docker container did not stop exactly")
    except Exception:
        # A stop command may report failure after taking effect.  Restore the
        # complete pre-mutation snapshot before propagating the refusal.
        _restore_services(stopped)
        raise
    return stopped


def _restore_services(stopped: list[tuple[str, str]]) -> None:
    expected = dict(stopped)
    failures: list[str] = []
    for name in reversed(_SHARED_CONTAINERS):
        if name not in expected:
            continue
        try:
            observed_id, running, auto_remove = _container_state(name)
            if observed_id != expected[name] or auto_remove:
                raise RuntimeError("identity/state mismatch")
            if not running:
                _docker("start", expected[name])
                observed_id, running, auto_remove = _container_state(name)
            if observed_id != expected[name] or not running or auto_remove:
                raise RuntimeError("identity/state mismatch")
        except Exception:
            failures.append(name)
    if failures:
        raise RuntimeError("MI-2 Docker service restore: " + ",".join(failures))

def _under(path: Path, parent: Path, label: str) -> Path:
    """Resolve an explicit CLI path without allowing it to escape its root."""
    if not path.is_absolute() or not parent.is_absolute():
        raise ValueError(f"MI-2 {label} must be absolute")
    try:
        path.relative_to(parent)
    except ValueError as error:
        raise ValueError(f"MI-2 {label} must stay under {parent}") from error
    return path

def _local_identity_preflight(files: Mapping[str, bytes], model_snapshot: Path,
                              publication_commit: str, publication_tree: str) -> None:
    """Read-only checks of local model/GPU/image and publication checkout."""
    runtime = parse_canonical(files["identities/ASYNC_ENABLED/runtime_identity_sha256.json"])
    model = parse_canonical(files["identities/ASYNC_ENABLED/model_identity_sha256.json"])
    frozen_manifest = files["identities/ASYNC_ENABLED/model_snapshot_manifest_sha256.json"]
    rebuilt = build_model_snapshot_manifest(model_snapshot.parents[2], repository=model["repository"], revision=model["revision"])
    if canonical_bytes(rebuilt) != frozen_manifest:
        raise ValueError("MI-2 local snapshot manifest drifted")
    def command(*args: str) -> bytes:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0: raise ValueError("MI-2 local identity command failed: " + args[0])
        return result.stdout
    gpu = command("nvidia-smi", "--query-gpu=uuid,driver_version,compute_cap", "--format=csv,noheader,nounits").decode("utf-8", "strict").splitlines()
    if len(gpu) != 1 or [item.strip() for item in gpu[0].split(",")] != [runtime["gpu_uuid"], runtime["gpu_driver_version"], runtime["gpu_compute_capability"]]:
        raise ValueError("MI-2 local GPU identity drifted")
    image = json.loads(command("docker", "image", "inspect", runtime["container_image"]).decode("utf-8", "strict"))
    if (type(image) is not list or len(image) != 1 or image[0].get("Id") != runtime["image_id"]
            or runtime["container_image"] not in image[0].get("RepoDigests", [])):
        raise ValueError("MI-2 local Docker image/digest drifted")
    head = command("git", "rev-parse", "HEAD").decode().strip()
    tree = command("git", "rev-parse", "HEAD^{tree}").decode().strip()
    if head != publication_commit or tree != publication_tree or command("git", "status", "--porcelain"):
        raise ValueError("MI-2 publication checkout is not exact and clean")
    dependencies = ("_research/dgx_mi2/protocol.py", "_research/dgx_mi2/runner.py", "_research/dgx_mi2/launcher.py", "_research/dgx_mi2/experiment.py", "_research/dgx_mi2/independent_verifier.py", "_research/dnrd5/canonical_json.py", "_research/dgx_q1/live_protocol.py", "_research/dgx_q1/live_launcher.py", "_research/dgx_q1/model_snapshot_manifest.py", "_research/dgx_q1/github_ci_receipt.py")
    source_commit = parse_canonical(files["plan.json"])["source"]["commit"]
    ancestry = subprocess.run(("git", "merge-base", "--is-ancestor", source_commit, publication_commit), check=False)
    if ancestry.returncode != 0:
        raise ValueError("MI-2 frozen source is not an ancestor of publication checkout")
    changed = subprocess.run(("git", "diff", "--quiet", source_commit, publication_commit, "--", *dependencies), check=False)
    if changed.returncode not in (0, 1) or changed.returncode == 1:
        raise ValueError("MI-2 executable study path drifted since frozen source")

def _preflight(*, freeze: Path, registry: Path, publication_commit: str, publication_tree: str,
               publication_ci_receipt: Path, model_snapshot: Path, lock_path: Path,
               output_root: Path, cache_parent: Path) -> dict[str, bytes]:
    """Read-only gate: no plan burn, target launch, cache, or evidence creation."""
    files = _load_freeze(freeze)
    plan = validate_mi2_plan(files["plan.json"], seed_material_raw=files["schedule_seed_material.json"])
    validate_mi2_start_marker(files["start_marker.json"], files["plan.json"], files["schedule_seed_material.json"])
    validate_arm_identities({arm: {name: files[f"identities/{arm}/{name}.json"] for name in IDENTITY_NAMES}
                             for arm in ARMS})
    if plan["consumption_registry"] != REGISTRY or registry != Path(REGISTRY["path"]):
        raise ValueError("MI-2 registry does not equal frozen plan")
    if registry.is_symlink() or not registry.is_dir():
        raise ValueError("MI-2 registry unavailable")
    if (registry / (sha256(files["plan.json"]).hexdigest() + ".consumed")).exists():
        raise ValueError("MI-2 frozen plan is already consumed")
    receipt = publication_ci_receipt.read_bytes()
    parse_github_actions_ci_receipt(receipt, repository="gj3447/HSWM", commit=publication_commit, tree=publication_tree)
    if (not model_snapshot.is_absolute() or model_snapshot.is_symlink() or not model_snapshot.is_dir()
            or not lock_path.is_absolute() or lock_path.is_symlink() or lock_path.parent.is_symlink() or not lock_path.parent.is_dir()):
        raise ValueError("MI-2 model snapshot or lock path unavailable")
    if not output_root.parent.is_dir() or output_root.exists():
        raise ValueError("MI-2 evidence root must be a new child of output root")
    if cache_parent.exists() or not cache_parent.parent.is_dir():
        raise ValueError("MI-2 cache directory must be a new child of cache root")
    _local_identity_preflight(files, model_snapshot, publication_commit, publication_tree)
    _preflight_services()
    return files
def _runtime(files: Mapping[str,bytes]) -> dict[str,dict[str,Any]]:
    result={}
    for arm in ARMS:
        runtime=parse_canonical(files[f"identities/{arm}/runtime_identity_sha256.json"])
        model=parse_canonical(files[f"identities/{arm}/model_identity_sha256.json"])
        result[arm]={"endpoint":runtime["endpoint"],"image":runtime["container_image"],"image_id":runtime["image_id"],"gpu_uuid":runtime["gpu_uuid"],"served_model":runtime["served_model"],"model_revision":runtime["model_revision"],"max_model_len":runtime["max_model_len"],"gpu_memory_utilization_milli":runtime["gpu_memory_utilization_milli"],"model_repository":model["repository"],"snapshot_manifest_raw":files[f"identities/{arm}/model_snapshot_manifest_sha256.json"]}
    return result

def run_experiment(*, evidence_root: Path, freeze_root: Path, registry: Path, specs: Mapping[int,Mi2LeaseSpec], publication_commit: str, publication_tree: str, publication_ci_receipt: bytes, stop_shared_services: Callable[[],None] | None=None, restore_shared_services: Callable[[],None] | None=None, postrun_quiescence: Callable[[], tuple[bytes, bytes]] | None=None, **deps: Any) -> dict[str,Any]:
    post_error: Exception | None = None
    runner: Mi2Runner | None = None
    try:
        if stop_shared_services: stop_shared_services()
        runner=Mi2Runner(evidence_root,freeze_root=freeze_root,registry=registry,specs=specs,publication_commit=publication_commit,publication_tree=publication_tree,publication_ci_receipt=publication_ci_receipt,**deps); runner.execute(release_exclusive_lock=False)
    finally:
        # Never restart shared GPU services until the experiment has observed
        # that no experiment container/listener/compute process survived.
        try:
            first = specs[1]
            attestation, gpu_raw = (postrun_quiescence() if postrun_quiescence else global_quiescence(gpu_uuid=first.gpu_uuid, endpoint=first.endpoint))
            _validate_global_quiescence(attestation, gpu_raw, first)
        except Exception as error:
            post_error = error
        finally:
            if runner is not None:
                runner.release_exclusive_lock()
        if post_error is None and restore_shared_services:
            restore_shared_services()
    if post_error is not None:
        raise RuntimeError("MI-2 post-run quiescence failed; shared services were left stopped") from post_error
    return parse_canonical((evidence_root/"receipt.json").read_bytes())

def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-dir",required=True); parser.add_argument("--evidence-root")
    parser.add_argument("--cache-root"); parser.add_argument("--registry",required=True)
    parser.add_argument("--publication-commit",required=True); parser.add_argument("--publication-tree",required=True)
    parser.add_argument("--publication-ci-receipt",required=True); parser.add_argument("--model-snapshot",required=True); parser.add_argument("--lock-path",required=True); parser.add_argument("--preflight-only",action="store_true")
    args=parser.parse_args(argv); freeze=Path(args.freeze_dir)
    output_base=Path(os.environ["HSWM_OUTPUT_ROOT"])
    cache_base=Path(os.environ["HSWM_CACHE_ROOT"])
    output_root=_under(Path(args.evidence_root) if args.evidence_root else output_base/"mi2_evidence", output_base, "evidence root")
    cache_parent=_under(Path(args.cache_root) if args.cache_root else cache_base/"mi2-launch-crossed", cache_base, "cache root")
    files=_preflight(freeze=freeze, registry=Path(args.registry), publication_commit=args.publication_commit,
                     publication_tree=args.publication_tree, publication_ci_receipt=Path(args.publication_ci_receipt),
                     model_snapshot=Path(args.model_snapshot), lock_path=Path(args.lock_path),
                     output_root=output_root, cache_parent=cache_parent)
    plan=validate_mi2_plan(files["plan.json"],seed_material_raw=files["schedule_seed_material.json"])
    if args.preflight_only: return 0
    receipt=Path(args.publication_ci_receipt).read_bytes(); specs=make_specs(plan_raw=files["plan.json"],arm_runtime=_runtime(files),cache_root=cache_parent,lock_path=Path(args.lock_path),model_snapshot=Path(args.model_snapshot))
    stopped: list[tuple[str, str]]=[]
    result=run_experiment(evidence_root=output_root,freeze_root=freeze,registry=Path(args.registry),specs=specs,publication_commit=args.publication_commit,publication_tree=args.publication_tree,publication_ci_receipt=receipt,stop_shared_services=lambda:_stop_services(stopped),restore_shared_services=lambda:_restore_services(stopped))
    print(canonical_bytes(result).decode()); return 0

if __name__ == "__main__": raise SystemExit(main())

__all__=["make_specs","run_experiment","main"]
