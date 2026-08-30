"""One sealed DGX occurrence for the prospective ALFWorld B0 calibration.

This module is an execution envelope, not a result interpreter.  It writes
only under the two roots supplied by ``hswm-run`` and never writes a repository
artifact or generates a selection.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping

from _research.dnrd5.canonical_json import canonical_bytes
from .alfworld_b0_actor import ALFWorldB0Actor
from .alfworld_b0_calibration import (
    COMPLETE_STATUS,
    DGX_RUNTIME_QUALIFICATION,
    INCONCLUSIVE_STATUS,
    VLLM_METRICS_QUALIFICATION,
    run_b0_calibration,
    verify_private_selection,
    verify_protocol,
)
from .alfworld_b0_dgx import B0DgxLease, B0DgxLeaseSpec, SERVED_MODEL
from .alfworld_b0_selection import (
    GAME_DOMAIN,
    GROUP_DOMAIN,
    SELECTION_SCHEMA,
    TRAIN_GROUP_COUNT,
    VALID_SEEN_GROUP_COUNT,
)
from .alfworld_b0_runtime import DgxB0AlfworldTextRuntime, dgx_sandbox_identity
from .alfworld_text_runtime import LocalSandboxSpec
from .continual_live import OpenAIBackendConfig


LIVE_SCHEMA = "hswm-alfworld-b0-live-occurrence/v1"
VOID_STATUS = "VOID_PROTOCOL_OR_EVIDENCE_BINDING_BREACH"
_FORBIDDEN_PUBLIC = (
    "opaque_uid", "task_group_uid", "relative_path", '"action"',
    '"observation"', '"outcome"', '"actor_trace"', '"raw_'
)


class AlfworldB0LiveError(RuntimeError):
    """The one allowed B0 occurrence cannot start or seal safely."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except ValueError:
        return False
    return True


def _regular(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AlfworldB0LiveError(f"{label} must be an absolute non-symlink regular file")
    return path


def _directory(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise AlfworldB0LiveError(f"{label} must be an absolute non-symlink directory")
    return path


def _exclusive(path: Path, value: Mapping[str, object] | bytes) -> str:
    if not path.is_absolute() or not path.parent.is_dir() or path.exists():
        raise AlfworldB0LiveError("live output must have a fresh existing absolute parent")
    raw = value if isinstance(value, bytes) else canonical_bytes(dict(value)) + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        raise
    return _sha(raw)


def _git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(("git", "-C", str(repo), *args), check=False, capture_output=True)
    if completed.returncode or completed.stderr:
        raise AlfworldB0LiveError("git binding check failed")
    return completed.stdout


@dataclass(frozen=True, slots=True)
class LivePaths:
    repo: Path
    protocol: Path
    private_selection: Path
    public_selection: Path
    pool: Path
    locator: Path
    asset_root: Path
    upstream: Path
    venv: Path
    python: Path
    python_runtime_root: Path
    bubblewrap: Path
    sudo: Path
    model_snapshot: Path
    hf_hub: Path
    lock: Path
    container_name: str


def _roots() -> tuple[Path, Path]:
    output_raw, cache_raw = os.environ.get("HSWM_OUTPUT_ROOT"), os.environ.get("HSWM_CACHE_ROOT")
    if not output_raw or not cache_raw:
        raise AlfworldB0LiveError("must run through hswm-run with HSWM_OUTPUT_ROOT and HSWM_CACHE_ROOT")
    output, cache = Path(output_raw), Path(cache_raw)
    _directory(output, "HSWM_OUTPUT_ROOT")
    _directory(cache, "HSWM_CACHE_ROOT")
    return output, cache


def _verify_bindings(paths: LivePaths) -> tuple[dict[str, object], dict[str, str]]:
    repo = _directory(paths.repo, "repo")
    if _git(repo, "status", "--porcelain").strip():
        raise AlfworldB0LiveError("live repository checkout is dirty")
    commit = _git(repo, "rev-parse", "HEAD").decode().strip()
    tree = _git(repo, "rev-parse", "HEAD^{tree}").decode().strip()
    if len(commit) != 40 or len(tree) != 40:
        raise AlfworldB0LiveError("live commit/tree identity is invalid")
    protocol = _regular(paths.protocol, "protocol")
    if not _under(protocol, repo):
        raise AlfworldB0LiveError("protocol must be in the committed repository")
    try:
        value = json.loads(protocol.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldB0LiveError("protocol is unreadable JSON") from error
    if not isinstance(value, dict):
        raise AlfworldB0LiveError("protocol must be an object")
    binding = value.get("execution_source_binding")
    if not isinstance(binding, dict) or binding.get("required_clean_committed_checkout") is not True:
        raise AlfworldB0LiveError("protocol lacks its committed checkout requirement")
    sources = binding.get("start_marker_must_hash_paths")
    if not isinstance(sources, list) or not sources or any(not isinstance(item, str) for item in sources):
        raise AlfworldB0LiveError("protocol source binding is invalid")
    digests: dict[str, str] = {}
    for relative in sources:
        target = repo / relative
        _regular(target, f"bound source {relative}")
        if not _under(target, repo):
            raise AlfworldB0LiveError("bound source escaped repository")
        committed = _git(repo, "show", f"HEAD:{relative}")
        raw = target.read_bytes()
        if raw != committed:
            raise AlfworldB0LiveError("bound source differs from commit")
        digests[relative] = _sha(raw)
    if protocol.relative_to(repo).as_posix() not in digests:
        raise AlfworldB0LiveError("protocol omitted itself from source binding")
    return value, {"commit": commit, "tree": tree, **digests}


def _bound_public_receipt(
    paths: LivePaths,
    binding: Mapping[str, str],
    evidence: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    """Load one exact pre-selection public receipt from its evidence commit."""

    relative = evidence.get("path")
    file_sha = evidence.get("file_sha256")
    receipt_sha = evidence.get("receipt_sha256")
    evidence_commit = evidence.get("evidence_commit")
    if not all(isinstance(item, str) for item in (relative, file_sha, receipt_sha, evidence_commit)):
        raise AlfworldB0LiveError(f"{label} evidence binding is invalid")
    assert isinstance(relative, str)
    assert isinstance(file_sha, str)
    assert isinstance(receipt_sha, str)
    assert isinstance(evidence_commit, str)
    path = _regular(paths.repo / relative, label)
    if not _under(path, paths.repo):
        raise AlfworldB0LiveError(f"{label} escaped repository")
    raw = path.read_bytes()
    if (
        binding.get(relative) != file_sha
        or _sha(raw) != file_sha
        or _git(paths.repo, "show", f"{evidence_commit}:{relative}") != raw
    ):
        raise AlfworldB0LiveError(f"{label} bytes differ from bound evidence")
    _git(paths.repo, "merge-base", "--is-ancestor", evidence_commit, "HEAD")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldB0LiveError(f"{label} is unreadable JSON") from error
    if not isinstance(value, dict) or canonical_bytes(value) + b"\n" != raw:
        raise AlfworldB0LiveError(f"{label} is not canonical JSON")
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value.get("receipt_sha256") != receipt_sha or receipt_sha != _sha(canonical_bytes(unsigned)):
        raise AlfworldB0LiveError(f"{label} self receipt drifted")
    return value


def _verify_engineering_prerequisites(
    paths: LivePaths,
    protocol_value: Mapping[str, object],
    binding: Mapping[str, str],
) -> None:
    """Require both immutable engineering qualifications before selection use."""

    verify_protocol(paths.protocol)
    evidence = protocol_value.get("current_evidence")
    if (
        not isinstance(evidence, dict)
        or evidence.get("dgx_runtime_qualification") != DGX_RUNTIME_QUALIFICATION
        or evidence.get("vllm_metrics_qualification") != VLLM_METRICS_QUALIFICATION
    ):
        raise AlfworldB0LiveError("engineering evidence protocol binding drifted")
    runtime = _bound_public_receipt(
        paths, binding, DGX_RUNTIME_QUALIFICATION, "DGX runtime qualification"
    )
    metrics = _bound_public_receipt(
        paths, binding, VLLM_METRICS_QUALIFICATION, "vLLM metrics qualification"
    )
    environment = protocol_value.get("environment_runtime")
    model_runtime = protocol_value.get("model_runtime")
    metric_source = metrics.get("source_binding")
    if (
        runtime.get("schema_version")
        != "hswm-alfworld-b0-runtime-dgx-qualification-public/v1"
        or runtime.get("status") != DGX_RUNTIME_QUALIFICATION["status"]
        or runtime.get("claim_ceiling")
        != "ONE_SEALED_20_ACTION_FIXED_LOOK_RUNTIME_CHECK_ONLY_NOT_MODEL_OR_AGENT_EFFICACY_NOT_LEARNING_NOT_G0_NOT_G1"
        or runtime.get("fixed_action") != "look"
        or runtime.get("actor_frame_count") != 21
        or runtime.get("action_count") != 20
        or runtime.get("terminal")
        != {"done": True, "score": 0, "success": False, "won": False}
        or not isinstance(environment, dict)
        or runtime.get("sandbox") != environment.get("sandbox")
        or metrics.get("schema_version")
        != "hswm-alfworld-b0-vllm-metrics-public/v1"
        or metrics.get("status") != VLLM_METRICS_QUALIFICATION["status"]
        or metrics.get("claim_ceiling")
        != "FRESH_SERVICE_COUNTER_SEMANTICS_ONLY_NOT_ALFWORLD_NOT_AGENT_EFFICACY_NOT_G0_NOT_G1"
        or metrics.get("private_receipt_file_sha256")
        != VLLM_METRICS_QUALIFICATION["private_receipt_file_sha256"]
        or not isinstance(metric_source, dict)
        or metric_source.get("protocol_file_sha256")
        != VLLM_METRICS_QUALIFICATION["probe_predecessor_protocol_sha256"]
        or metrics.get("counter_deltas")
        != {
            "tokenize": {
                "running": 0,
                "success_total": 0,
                "prefix_hits": 0,
                "prefix_queries": 0,
            },
            "completion": {
                "running": 0,
                "success_total": 1,
                "prefix_hits": 0,
                "prefix_queries": 0,
            },
        }
        or not isinstance(model_runtime, dict)
        or model_runtime.get("request_success_counter_semantics")
        != "COMPLETED_GENERATION_REQUESTS_ONLY_TOKENIZE_EXCLUDED"
        or model_runtime.get("successful_tokenize_post_counter_delta") != 0
        or model_runtime.get("successful_completion_post_counter_delta") != 1
    ):
        raise AlfworldB0LiveError("engineering qualification semantics drifted")


def _verify_selection(paths: LivePaths, protocol_value: Mapping[str, object]) -> dict[str, object]:
    protocol = verify_protocol(paths.protocol)
    pool_sha = _sha(_regular(paths.pool, "pool").read_bytes())
    locator_sha = _sha(_regular(paths.locator, "locator").read_bytes())
    _rows, _private_semantic_sha, selection_sha = verify_private_selection(
        paths.private_selection, protocol, pool_manifest_sha256=pool_sha,
        local_locator_sha256=locator_sha,
    )
    expected_public = paths.repo / "manifests" / "HSWM_ALFWORLD_B0_SELECTION_2026-08-30.json"
    if paths.public_selection != expected_public:
        raise AlfworldB0LiveError("public selection must use the exact committed manifest path")
    public_path = _regular(paths.public_selection, "public selection")
    if not _under(public_path, paths.repo):
        raise AlfworldB0LiveError("public selection must remain in the repository")
    relative = public_path.relative_to(paths.repo).as_posix()
    public_raw = public_path.read_bytes()
    if public_raw != _git(paths.repo, "show", f"HEAD:{relative}"):
        raise AlfworldB0LiveError("public selection differs from its committed bytes")
    try:
        public = json.loads(public_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldB0LiveError("public selection is unreadable JSON") from error
    if not isinstance(public, dict):
        raise AlfworldB0LiveError("public selection must be an object")
    expected = {
        "schema_version", "record_role", "status", "protocol", "selector_source_sha256",
        "input_commitments", "selection", "no_claim", "private_receipt_sha256",
        "public_projection_sha256",
    }
    committed = public.get("selection")
    protocol_public = public.get("protocol")
    source = paths.repo / "src/hswm/experiments/alfworld_b0_selection.py"
    private_bytes_sha = _sha(_regular(paths.private_selection, "private selection").read_bytes())
    unsigned = {key: item for key, item in public.items() if key != "public_projection_sha256"}
    if (
        set(public) != expected
        or public.get("schema_version") != SELECTION_SCHEMA
        or public.get("record_role") != "AGGREGATE_PROSPECTIVE_B0_SELECTION_COMMITMENT_NOT_A_RESULT"
        or public.get("status") != "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN"
        or public.get("public_projection_sha256") != _sha(canonical_bytes(unsigned))
        or public.get("private_receipt_sha256") != private_bytes_sha
        or public.get("selector_source_sha256") != _sha(source.read_bytes())
        or not isinstance(committed, dict)
        or committed != {
            "algorithm": SELECTION_SCHEMA,
            "group_rank_domain": GROUP_DOMAIN,
            "game_rank_domain": GAME_DOMAIN,
            "without_replacement": True,
            "selected_group_counts": {"train": TRAIN_GROUP_COUNT, "valid_seen": VALID_SEEN_GROUP_COUNT},
            "valid_unseen_selected_group_count": 0,
            "valid_unseen_record_detail_access": "NONE_BEYOND_AGGREGATE_AND_SPLIT_COUNT",
            "selection_digest_sha256": selection_sha,
        }
        or not isinstance(protocol_public, dict)
        or protocol_public != {"uid": protocol.uid, "version": protocol.version, "protocol_file_sha256": protocol.binding_sha256}
    ):
        raise AlfworldB0LiveError("public selection does not match private selection")
    public_inputs = public.get("input_commitments")
    evidence = protocol_value.get("current_evidence")
    pool_evidence = evidence.get("pool_manifest") if isinstance(evidence, dict) else None
    if (
        not isinstance(public_inputs, dict)
        or public_inputs.get("pool_manifest_rendered_json_sha256") != pool_sha
        or public_inputs.get("local_locator_rendered_json_sha256") != locator_sha
        or not isinstance(pool_evidence, dict)
        or pool_evidence.get("rendered_json_sha256") != pool_sha
        or evidence.get("local_locator_rendered_json_sha256") != locator_sha
    ):
        raise AlfworldB0LiveError("pool or locator commitment differs from selection/protocol")
    if any(token in canonical_bytes(public).decode("utf-8").lower() for token in _FORBIDDEN_PUBLIC):
        raise AlfworldB0LiveError("public selection leaks private material")
    return {"private_selection_sha256": private_bytes_sha, "public_selection_sha256": _sha(public_raw), "selection_digest_sha256": selection_sha, "pool_manifest_sha256": pool_sha, "local_locator_sha256": locator_sha}


def _persist_lease_evidence(output: Path, lease: Any | None, known: dict[str, str]) -> dict[str, str]:
    """Preserve every already available raw lease observation exactly once."""
    if lease is None:
        return known
    for stage in ("startup", "final"):
        evidence = getattr(lease, stage, None)
        if not isinstance(evidence, dict):
            continue
        for name, raw in evidence.items():
            if not isinstance(raw, bytes):
                continue
            key, digest = f"{stage}:{name}", _sha(raw)
            if key in known:
                continue
            blob = output / "content" / digest
            blob.parent.mkdir(exist_ok=True)
            if blob.exists():
                if blob.is_symlink() or not blob.is_file() or blob.read_bytes() != raw:
                    raise AlfworldB0LiveError("content-addressed lease evidence drifted")
            else:
                _exclusive(blob, raw)
            known[key] = digest
    return known


def _public(private: Mapping[str, object], *, status: str, binding: Mapping[str, str], selection: Mapping[str, object], private_serialized_sha256: str | None = None) -> dict[str, object]:
    totals = private.get("resource_totals") if isinstance(private.get("resource_totals"), dict) else {}
    value: dict[str, object] = {
        "schema_version": LIVE_SCHEMA,
        "status": status,
        "claim_ceiling": "EXPLORATORY_B0_CALIBRATION_ONLY_G0_NOT_PASSED_NOT_G1",
        "execution": {"commit": binding.get("commit"), "tree": binding.get("tree"), "protocol_sha256": binding.get("_protocol")},
        "selection_commitments": dict(selection),
        "resource_totals": dict(totals),
        "private_receipt_sha256": private_serialized_sha256 or _sha(canonical_bytes(dict(private)) + b"\n"),
    }
    rendered = canonical_bytes(value).decode("utf-8").lower()
    if any(token in rendered for token in _FORBIDDEN_PUBLIC):
        raise AlfworldB0LiveError("live public projection leaks private material")
    value["public_projection_sha256"] = _sha(canonical_bytes(value))
    return value


def run_live(
    paths: LivePaths,
    *,
    lease_factory: Callable[[B0DgxLeaseSpec], Any] = B0DgxLease,
    calibration: Callable[..., tuple[dict[str, object], dict[str, object]]] = run_b0_calibration,
) -> tuple[dict[str, object], dict[str, object]]:
    """Run once; all ordinary failures are sealed as private/public terminal data."""
    output, cache = _roots()
    private_path, public_path, marker_path = output / "b0.private.json", output / "b0.public.json", output / "b0.start.json"
    try:
        protocol_value, binding = _verify_bindings(paths)
        binding["_protocol"] = _sha(paths.protocol.read_bytes())
        _verify_engineering_prerequisites(paths, protocol_value, binding)
        selection = _verify_selection(paths, protocol_value)
        for field in ("pool", "locator", "sudo", "bubblewrap", "python"):
            _regular(getattr(paths, field), field)
        for field in ("asset_root", "upstream", "venv", "python_runtime_root", "model_snapshot", "hf_hub"):
            _directory(getattr(paths, field), field)
        if paths.model_snapshot.parents[2] != paths.hf_hub:
            raise AlfworldB0LiveError("model snapshot is not under the declared Hugging Face hub")
        if not paths.lock.is_absolute() or paths.lock.is_symlink() or not paths.lock.parent.is_dir():
            raise AlfworldB0LiveError("lock path is invalid")
        dgx_sandbox_identity(sudo=paths.sudo, bubblewrap=paths.bubblewrap)
        marker = {
            "schema_version": LIVE_SCHEMA + "-start-marker",
            "terminal": "PRE_LEASE_PRE_ENV_PRE_MODEL_BINDING_SEALED",
            "execution_source_sha256": binding,
            "selection": selection,
            "pool_manifest_sha256": _sha(paths.pool.read_bytes()),
            "local_locator_sha256": _sha(paths.locator.read_bytes()),
        }
        _exclusive(marker_path, marker)
    except Exception as error:
        private = {"schema_version": LIVE_SCHEMA, "status": VOID_STATUS, "error_type": type(error).__name__, "terminal": "PRELEASE_BINDING_FAILURE"}
        public = _public(private, status=VOID_STATUS, binding={}, selection={}, private_serialized_sha256=_sha(canonical_bytes(private) + b"\n"))
        _exclusive(private_path, private); _exclusive(public_path, public)
        return private, public
    lease: Any | None = None
    inner_private: dict[str, object] | None = None
    issued_counts: dict[str, object] = {}
    lease_blobs: dict[str, str] = {}
    try:
        hf_cache, compile_cache = cache / "hf", cache / "compile"
        if hf_cache.exists() or compile_cache.exists():
            raise AlfworldB0LiveError("fresh B0 cache locations already exist")
        spec = B0DgxLeaseSpec(repo_root=paths.repo, protocol_path=paths.protocol, protocol_sha256=binding["_protocol"],
            declared_source_paths=tuple(paths.repo / key for key in binding if key not in {"commit", "tree", "_protocol"}),
            lock_path=paths.lock, container_name=paths.container_name, model_snapshot=paths.model_snapshot,
            hf_cache=hf_cache, compile_cache=compile_cache, endpoint="http://127.0.0.1:18080")
        lease = lease_factory(spec)
        with lease as active:
            actor = ALFWorldB0Actor.from_config(OpenAIBackendConfig(endpoint="http://127.0.0.1:18080", model=SERVED_MODEL, timeout_seconds=120.0))
            def factory(selection_row: Any, game_binding: Any, game_file: Path, pool_sha: str, locator_sha: str, protocol: Any) -> LocalSandboxSpec:
                return LocalSandboxSpec(paths.bubblewrap, paths.python, paths.python_runtime_root, paths.repo, paths.upstream, paths.venv, paths.asset_root, game_file, pool_sha, locator_sha, game_binding, selection_row.opaque_uid, max_steps=protocol.max_steps)
            inner_private, _ignored = calibration(protocol=paths.protocol, private_selection_receipt=paths.private_selection,
                pool_manifest=paths.pool, local_locator=paths.locator, asset_root=paths.asset_root,
                sandbox_spec_factory=factory, actor=actor,
                runtime_launcher=lambda sandbox: DgxB0AlfworldTextRuntime(sandbox, sudo=paths.sudo).launch())
            totals = inner_private.get("resource_totals", {})
            if not isinstance(totals, dict):
                raise AlfworldB0LiveError("calibration totals are invalid")
            issued_counts = {
                "issued_tokenize_post_count": totals.get("issued_tokenize_post_count"),
                "issued_completion_post_count": totals.get("issued_completion_post_count"),
                "issued_http_post_count": totals.get("issued_http_post_count"),
            }
            active.attest(
                int(issued_counts["issued_tokenize_post_count"]),
                int(issued_counts["issued_completion_post_count"]),
            )
        lease_blobs = _persist_lease_evidence(output, lease, lease_blobs)
        if not isinstance(inner_private, dict):
            raise AlfworldB0LiveError("calibration did not return a private receipt")
        private = {"schema_version": LIVE_SCHEMA, "status": inner_private.get("status", INCONCLUSIVE_STATUS), "start_marker_sha256": _sha(marker_path.read_bytes()), "inner_private_receipt": inner_private, "issued_counts": issued_counts, "lease_blobs": lease_blobs}
        public = _public(private, status=str(private["status"]), binding=binding, selection=selection, private_serialized_sha256=_sha(canonical_bytes(private) + b"\n"))
    except Exception as error:
        try:
            lease_blobs = _persist_lease_evidence(output, lease, lease_blobs)
        except Exception as blob_error:
            lease_blobs["preservation_error"] = type(blob_error).__name__
        private = {
            "schema_version": LIVE_SCHEMA, "status": INCONCLUSIVE_STATUS,
            "error_type": type(error).__name__, "terminal": "LIVE_OR_LEASE_FAILURE_NO_RETRY",
            "start_marker_sha256": _sha(marker_path.read_bytes()),
            "inner_private_receipt": inner_private,
            "issued_counts": issued_counts,
            "lease_blobs": lease_blobs,
        }
        public = _public(private, status=INCONCLUSIVE_STATUS, binding=binding, selection=selection, private_serialized_sha256=_sha(canonical_bytes(private) + b"\n"))
    _exclusive(private_path, private); _exclusive(public_path, public)
    return private, public


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "protocol", "private-selection", "public-selection", "pool", "locator", "asset-root", "upstream", "venv", "python", "python-runtime-root", "sudo", "bubblewrap", "model-snapshot", "hf-hub", "lock"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--container", required=True)
    args = parser.parse_args(argv)
    paths = LivePaths(args.repo, args.protocol, args.private_selection, args.public_selection, args.pool, args.locator, args.asset_root, args.upstream, args.venv, args.python, args.python_runtime_root, args.sudo, args.bubblewrap, args.model_snapshot, args.hf_hub, args.lock, args.container)
    private, _public_value = run_live(paths)
    return 0 if private["status"] == COMPLETE_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
