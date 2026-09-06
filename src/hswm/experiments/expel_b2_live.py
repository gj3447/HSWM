"""Frozen-envelope host for one prospective B2 text-lesson sequence.

The module deliberately has no import-time side effects.  A caller supplies a
previously written B2 selection; this envelope only rebinds it, starts a fresh
lease, and seals the private/public occurrence wrappers.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from hswm.selfmod.contracts import canonical_json_bytes

from .alfworld_b0_live import (
    LivePaths, _bound_public_receipt, _directory, _exclusive, _persist_lease_evidence,
    _regular, _roots, _sha, _verify_bindings, _verify_runtime_environment,
)
from .alfworld_b0_runtime import DgxB0AlfworldTextRuntime, dgx_sandbox_identity, load_local_game_binding
from .alfworld_text_runtime import LocalSandboxSpec
from .continual_live import OpenAIBackendConfig, OpenAICompatibleBackend
from .expel_b2_dgx import ExpelB2DgxLease, ExpelB2DgxLeaseSpec, MODEL_RUNTIME, PROTOCOL_SCHEMA
from .expel_b2_selection import B2Selection, select_prospective_b2, verify_private_selection
from .expel_b2_sequence import COMPLETE as SEQUENCE_COMPLETE, run_b2_sequence
from .expel_b2_transport import ExpelB2Transport


LIVE_SCHEMA = "hswm-expel-b2-live-occurrence/v1"
VOID_STATUS = "VOID_PROTOCOL_OR_EVIDENCE_BINDING_BREACH"
INCONCLUSIVE_STATUS = "INCONCLUSIVE_MEASUREMENT_NOT_READY"
COMPLETE_STATUS = "EXPLORATORY_B2_COMPARATOR_COMPLETE_G0_NOT_PASSED"
_FORBIDDEN_PUBLIC = ("opaque_uid", "task_group_uid", "relative_path", '"action"',
                     '"observation"', '"outcome"', '"actor_trace"', '"raw_')


class ExpelB2LiveError(RuntimeError):
    """The B2 occurrence could not be sealed under its frozen envelope."""


def _sealed(path: Path, value: Mapping[str, object]) -> str:
    """Write wrappers in the sequence's canonical JSON dialect.

    Successful sequence rates are JSON numbers, while the legacy B0 serializer
    used by its helper is intentionally integer-only.
    """
    raw = canonical_json_bytes(dict(value)) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return _sha(raw)


def _protocol_identity(value: Mapping[str, object], protocol_sha256: str) -> dict[str, str]:
    """Extract the selector identity from the B2 protocol's explicit binding."""
    selection, evidence = value.get("selection"), value.get("current_evidence")
    if not isinstance(selection, dict) or not isinstance(evidence, dict):
        raise ExpelB2LiveError("B2 protocol selection binding is absent")
    result = {
        "occurrence_uid": value.get("occurrence_uid"),
        "protocol_uid": value.get("study_uid"),
        "protocol_version": value.get("protocol_version"),
        "protocol_sha256": protocol_sha256,
        "pool_manifest_sha256": (evidence.get("pool_manifest") or {}).get("rendered_json_sha256") if isinstance(evidence.get("pool_manifest"), dict) else None,
        "local_locator_sha256": evidence.get("local_locator_rendered_json_sha256"),
    }
    if any(not isinstance(item, str) or not item for item in result.values()):
        raise ExpelB2LiveError("B2 protocol selection identity is invalid")
    return result  # type: ignore[return-value]


def _verify_protocol(paths: LivePaths, value: Mapping[str, object]) -> None:
    """Delegate semantic protocol checks to the B2 protocol module."""
    from . import expel_b2_protocol

    verified = expel_b2_protocol.verify_protocol(paths.protocol)
    if not isinstance(verified, dict) or verified != value:
        raise ExpelB2LiveError("B2 protocol verifier disagrees with source binding")
    if value.get("schema_version") != PROTOCOL_SCHEMA or value.get("model_runtime") != MODEL_RUNTIME:
        raise ExpelB2LiveError("B2 protocol lease identity drifted")


def _verify_b0_evidence(paths: LivePaths, binding: Mapping[str, str], protocol: Mapping[str, object]) -> Mapping[str, object]:
    """Bind each named B0 engineering receipt retained by the B2 protocol."""
    evidence = protocol.get("current_evidence")
    if not isinstance(evidence, dict):
        raise ExpelB2LiveError("B2 current evidence is absent")
    receipts = {name: evidence.get(name) for name in ("dgx_runtime_qualification", "vllm_metrics_qualification")}
    if any(not isinstance(item, dict) for item in receipts.values()):
        raise ExpelB2LiveError("B2 current evidence lacks named B0 pins")
    loaded: dict[str, object] = {}
    for name, descriptor in receipts.items():
        if not isinstance(name, str) or not isinstance(descriptor, dict):
            raise ExpelB2LiveError("B2 B0 evidence descriptor is invalid")
        loaded[name] = _bound_public_receipt(paths, binding, descriptor, "B2 " + name)
    runtime = loaded.get("dgx_runtime_qualification")
    if not isinstance(runtime, dict):
        raise ExpelB2LiveError("B2 B0 runtime qualification pin is absent")
    return runtime


def _verify_selection(paths: LivePaths, protocol: Mapping[str, object], protocol_sha256: str) -> tuple[B2Selection, dict[str, str]]:
    """Verify the private receipt, then independently recompute it from pins."""
    identity = _protocol_identity(protocol, protocol_sha256)
    raw = _regular(paths.private_selection, "B2 private selection").read_bytes()
    try:
        receipt = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExpelB2LiveError("B2 private selection is unreadable JSON") from error
    if not isinstance(receipt, dict):
        raise ExpelB2LiveError("B2 private selection must be an object")
    verified_rows = verify_private_selection(
        paths.private_selection, occurrence_uid=identity["occurrence_uid"], protocol_uid=identity["protocol_uid"],
        protocol_version=identity["protocol_version"], protocol_sha256=protocol_sha256,
        expected_pool_manifest_sha256=identity["pool_manifest_sha256"],
        expected_local_locator_sha256=identity["local_locator_sha256"],
    )
    selection = select_prospective_b2(
        pool_manifest=paths.pool, local_locator=paths.locator,
        occurrence_uid=identity["occurrence_uid"], protocol_uid=identity["protocol_uid"],
        protocol_version=identity["protocol_version"], protocol_sha256=protocol_sha256,
        expected_pool_manifest_sha256=identity["pool_manifest_sha256"],
        expected_local_locator_sha256=identity["local_locator_sha256"],
    )
    if tuple((*selection.train, *selection.valid_seen)) != verified_rows or selection.private_receipt() != receipt:
        raise ExpelB2LiveError("B2 private selection does not equal deterministic recomputation")
    public_raw = _regular(paths.public_selection, "B2 public selection").read_bytes()
    try:
        public = json.loads(public_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExpelB2LiveError("B2 public selection is unreadable JSON") from error
    if public != selection.public_projection(private_receipt_sha256=_sha(raw)):
        raise ExpelB2LiveError("B2 public selection does not match private projection")
    return selection, {"private_selection_sha256": _sha(raw), "public_selection_sha256": _sha(public_raw),
                       "selection_digest_sha256": selection.selection_digest}


def _verify_selected_assets(paths: LivePaths, selection: B2Selection) -> dict[str, int]:
    pool_sha, locator_sha = _sha(_regular(paths.pool, "pool").read_bytes()), _sha(_regular(paths.locator, "locator").read_bytes())
    rows = (*selection.train, *selection.valid_seen)
    source_bindings: list[dict[str, str]] = []
    for row in rows:
        observed_pool, observed_locator, binding, game_file = load_local_game_binding(
            pool_manifest=paths.pool, local_locator=paths.locator, asset_root=paths.asset_root, opaque_uid=row.opaque_uid)
        if observed_pool != pool_sha or observed_locator != locator_sha or binding.opaque_uid != row.opaque_uid or not game_file.is_file():
            raise ExpelB2LiveError("B2 selected game source binding drifted")
        LocalSandboxSpec(
            bubblewrap=paths.bubblewrap, python=paths.python,
            python_runtime_root=paths.python_runtime_root, repository=paths.repo,
            upstream=paths.upstream, venv=paths.venv, asset_root=paths.asset_root,
            game_file=game_file, pool_manifest_sha256=pool_sha,
            local_locator_sha256=locator_sha, game_binding=binding,
            episode_uid=row.opaque_uid, max_steps=20,
        ).validate()
        source_bindings.append({"opaque_uid": binding.opaque_uid, "file_sha256": binding.file_sha256})
    return {"selected_file_count": len(rows), "valid_unseen_selected_file_count": 0,
            "selected_source_bindings_sha256": _sha(canonical_json_bytes(source_bindings))}


def _transport_observation(transport: ExpelB2Transport | None) -> dict[str, object] | None:
    """Retain reserved posts if the sequence fails before it writes a receipt."""
    if transport is None:
        return None
    try:
        counts = transport.request_counts
        expected = {"action_tokenize", "reflection_tokenize", "action_completion", "reflection_completion"}
        if set(counts) != expected or any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("invalid request counters")
        events = [event.canonical() for event in transport.events]
    except Exception as error:
        return {"status": "TRANSPORT_CREATED_COUNTERS_UNREADABLE", "error_type": type(error).__name__}
    usage: dict[str, object] = {}
    for phase, fields in (("tokenize", ("input_tokens",)), ("completion", ("input_tokens", "output_tokens"))):
        matching = [event for event in events if event["phase"] == phase]
        usage[phase] = {field: {"observed_total": sum(event[field] for event in matching if type(event.get(field)) is int),
                                "unknown_request_count": sum(type(event.get(field)) is not int for event in matching)} for field in fields}
    return {"status": "TRANSPORT_COUNTERS_OBSERVED", "request_counts": counts, "request_events": events, "usage": usage}


def _issued_from_counts(counts: Mapping[str, object]) -> dict[str, int]:
    required = ("action_tokenize", "reflection_tokenize", "action_completion", "reflection_completion")
    if any(type(counts.get(key)) is not int or int(counts[key]) < 0 for key in required):
        raise ExpelB2LiveError("B2 transport request counters are invalid")
    tokenize = int(counts["action_tokenize"]) + int(counts["reflection_tokenize"])
    completion = int(counts["action_completion"]) + int(counts["reflection_completion"])
    return {"issued_tokenize_post_count": tokenize, "issued_completion_post_count": completion,
            "issued_http_post_count": tokenize + completion}


def _private_error_text(error: Exception) -> str:
    """Keep a bounded local diagnostic without promoting it to the public receipt."""
    return str(error).replace("\x00", " ")[:512]


def _persist_teardown(output: Path, lease: Any | None, known: dict[str, str]) -> dict[str, str]:
    """B0's helper retains raw startup/final bytes; retain textual teardown too."""
    known = _persist_lease_evidence(output, lease, known)
    teardown = getattr(lease, "teardown", None) if lease is not None else None
    if isinstance(teardown, dict):
        for name, value in teardown.items():
            if not isinstance(name, str) or not isinstance(value, str):
                continue
            raw, key = value.encode("utf-8"), "teardown:" + name
            if key not in known:
                digest, blob = _sha(raw), output / "content" / _sha(raw)
                if blob.exists():
                    if blob.is_symlink() or blob.read_bytes() != raw:
                        raise ExpelB2LiveError("lease teardown evidence drifted")
                else:
                    _exclusive(blob, raw)
                known[key] = digest
    return known


def _public(private: Mapping[str, object], *, status: str, binding: Mapping[str, str], selection: Mapping[str, str]) -> dict[str, object]:
    inner = private.get("inner_public_receipt")
    # Preserve both split rows.  An outer lease/attestation failure suppresses
    # rates even when the inner sequence happened to reach its own terminal.
    sequence = dict(inner) if isinstance(inner, dict) else {}
    transport = private.get("transport_observation")
    if not sequence and isinstance(transport, dict):
        sequence = {"status": transport.get("status"), "request_counts": transport.get("request_counts"),
                    "usage": transport.get("usage"), "splits": {},
                    "rate_status": "UNAVAILABLE_SEQUENCE_PREFIX_NOT_SEALED"}
    if status != COMPLETE_STATUS and isinstance(sequence.get("splits"), dict):
        splits: dict[str, object] = {}
        for name, row in sequence["splits"].items():
            splits[name] = {**row, "success_rate": None} if isinstance(row, dict) else row
        sequence = {key: sequence.get(key) for key in (
            "status", "request_counts", "usage", "retained_rule_count",
            "frozen_state_sha256", "wall_microseconds", "valid_unseen_selected_count",
            "comparison",
        )}
        sequence["splits"] = splits
        sequence["rate_status"] = "UNAVAILABLE_OUTER_HOST_ATTESTATION_NOT_COMPLETE"
    value: dict[str, object] = {"schema_version": LIVE_SCHEMA, "status": status,
        "claim_ceiling": "EXPLORATORY_B2_COMPARATOR_ONLY_G0_NOT_PASSED_NOT_G1",
        "execution": {"commit": binding.get("commit"), "tree": binding.get("tree"), "protocol_sha256": binding.get("_protocol")},
        "selection_commitments": dict(selection), "sequence": sequence,
        "private_receipt_sha256": _sha(canonical_json_bytes(dict(private)) + b"\n")}
    rendered = canonical_json_bytes(value).decode("utf-8").lower()
    if any(token in rendered for token in _FORBIDDEN_PUBLIC):
        raise ExpelB2LiveError("B2 public projection leaks private material")
    value["public_projection_sha256"] = _sha(canonical_json_bytes(value))
    return value


def run_live(paths: LivePaths, *, lease_factory: Callable[[ExpelB2DgxLeaseSpec], Any] = ExpelB2DgxLease,
             sequence_runner: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = run_b2_sequence) -> tuple[dict[str, object], dict[str, object]]:
    """Execute only a pre-existing B2 selection and retain every terminal prefix."""
    output, cache = _roots()
    private_path, public_path, marker_path = output / "b2.private.json", output / "b2.public.json", output / "b2.start.json"
    binding: dict[str, str] = {}
    selection_commitments: dict[str, str] = {}
    prelease_stage = "BINDINGS"
    try:
        protocol, binding = _verify_bindings(paths); binding["_protocol"] = _sha(paths.protocol.read_bytes())
        prelease_stage = "PROTOCOL"
        _verify_protocol(paths, protocol)
        prelease_stage = "B0_EVIDENCE"
        runtime_qualification = _verify_b0_evidence(paths, binding, protocol)
        prelease_stage = "RUNTIME_ENVIRONMENT"
        runtime_environment = _verify_runtime_environment(paths, protocol, runtime_qualification)
        prelease_stage = "SELECTION"
        selection, selection_commitments = _verify_selection(paths, protocol, binding["_protocol"])
        prelease_stage = "SELECTED_ASSETS"
        selected_assets = _verify_selected_assets(paths, selection)
        prelease_stage = "HOST_PATHS"
        for field in ("pool", "locator", "sudo", "bubblewrap"):
            _regular(getattr(paths, field), field)
        for field in ("asset_root", "model_snapshot", "hf_hub"):
            _directory(getattr(paths, field), field)
        dgx_sandbox_identity(sudo=paths.sudo, bubblewrap=paths.bubblewrap)
        prelease_stage = "START_MARKER"
        _exclusive(marker_path, {"schema_version": LIVE_SCHEMA + "-start-marker", "terminal": "PRE_LEASE_PRE_ENV_PRE_MODEL_BINDING_SEALED",
            "execution_source_sha256": binding, "selection": selection_commitments, "selected_assets": selected_assets,
            "runtime_environment": runtime_environment, "pool_manifest_sha256": _sha(paths.pool.read_bytes()), "local_locator_sha256": _sha(paths.locator.read_bytes())})
    except Exception as error:
        private = {"schema_version": LIVE_SCHEMA, "status": VOID_STATUS, "error_type": type(error).__name__, "error": _private_error_text(error), "failing_stage": prelease_stage, "terminal": "PRELEASE_BINDING_FAILURE"}
        public = _public(private, status=VOID_STATUS, binding=binding, selection=selection_commitments)
        _sealed(private_path, private); _sealed(public_path, public)
        return private, public
    lease: Any | None = None; inner_private: dict[str, Any] | None = None; inner_public: dict[str, Any] | None = None
    transport: ExpelB2Transport | None = None; transport_observation: dict[str, object] | None = None
    issued_counts: dict[str, object] = {"issued_tokenize_post_count": 0, "issued_completion_post_count": 0, "issued_http_post_count": 0}; lease_blobs: dict[str, str] = {}
    try:
        hf_cache, compile_cache = cache / "hf", cache / "compile"
        if hf_cache.exists() or compile_cache.exists():
            raise ExpelB2LiveError("fresh B2 cache locations already exist")
        spec = ExpelB2DgxLeaseSpec(repo_root=paths.repo, protocol_path=paths.protocol, protocol_sha256=binding["_protocol"],
            declared_source_paths=tuple(paths.repo / key for key in binding if key not in {"commit", "tree", "_protocol"}), lock_path=paths.lock,
            container_name=paths.container_name, model_snapshot=paths.model_snapshot, hf_cache=hf_cache, compile_cache=compile_cache, endpoint="http://127.0.0.1:18080")
        lease = lease_factory(spec)
        with lease as active:
            def transport_factory(sink: Callable[..., None]) -> ExpelB2Transport:
                nonlocal transport
                backend = OpenAICompatibleBackend(OpenAIBackendConfig(endpoint="http://127.0.0.1:18080", model=str(MODEL_RUNTIME["served_model"]), timeout_seconds=120.0))
                transport = ExpelB2Transport(backend, event_sink=sink)
                return transport
            def sandbox_factory(row: Any, game_binding: Any, game_file: Path, pool_sha: str, locator_sha: str) -> LocalSandboxSpec:
                return LocalSandboxSpec(paths.bubblewrap, paths.python, paths.python_runtime_root, paths.repo, paths.upstream, paths.venv, paths.asset_root, game_file, pool_sha, locator_sha, game_binding, row.opaque_uid, max_steps=20)
            sequence_root = output / "sequence"
            sequence_root.mkdir(mode=0o700)
            inner_private, inner_public = sequence_runner(selection=selection, output_root=sequence_root, pool_manifest=paths.pool, local_locator=paths.locator, asset_root=paths.asset_root,
                transport_factory=transport_factory, sandbox_spec_factory=sandbox_factory, runtime_launcher=lambda sandbox: DgxB0AlfworldTextRuntime(sandbox, sudo=paths.sudo).launch())
            counts = inner_private.get("request_counts") if isinstance(inner_private, dict) else None
            if not isinstance(counts, dict): raise ExpelB2LiveError("B2 sequence request counters are invalid")
            issued_counts = _issued_from_counts(counts)
            active.attest(int(issued_counts["issued_tokenize_post_count"]), int(issued_counts["issued_completion_post_count"]))
        lease_blobs = _persist_teardown(output, lease, lease_blobs)
        if not isinstance(inner_private, dict) or not isinstance(inner_public, dict) or inner_private.get("status") != SEQUENCE_COMPLETE:
            raise ExpelB2LiveError("B2 sequence did not complete before host attestation")
        private = {"schema_version": LIVE_SCHEMA, "status": COMPLETE_STATUS, "start_marker_sha256": _sha(marker_path.read_bytes()), "inner_private_receipt": inner_private, "inner_public_receipt": inner_public, "issued_counts": issued_counts, "lease_blobs": lease_blobs}
        public = _public(private, status=COMPLETE_STATUS, binding=binding, selection=selection_commitments)
    except Exception as error:
        transport_observation = _transport_observation(transport)
        if isinstance(transport_observation, dict) and transport_observation.get("status") == "TRANSPORT_COUNTERS_OBSERVED":
            observed_counts = transport_observation.get("request_counts")
            if isinstance(observed_counts, dict):
                issued_counts = _issued_from_counts(observed_counts)
        elif transport is not None:
            issued_counts = {"issued_tokenize_post_count": None, "issued_completion_post_count": None, "issued_http_post_count": None}
        try: lease_blobs = _persist_teardown(output, lease, lease_blobs)
        except Exception as blob_error: lease_blobs["preservation_error"] = type(blob_error).__name__
        private = {"schema_version": LIVE_SCHEMA, "status": INCONCLUSIVE_STATUS, "error_type": type(error).__name__, "terminal": "LIVE_OR_LEASE_FAILURE_NO_RETRY", "start_marker_sha256": _sha(marker_path.read_bytes()), "inner_private_receipt": inner_private, "inner_public_receipt": inner_public, "transport_observation": transport_observation, "issued_counts": issued_counts, "lease_blobs": lease_blobs}
        public = _public(private, status=INCONCLUSIVE_STATUS, binding=binding, selection=selection_commitments)
    _sealed(private_path, private); _sealed(public_path, public)
    return private, public


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "protocol", "private-selection", "public-selection", "pool", "locator", "asset-root", "upstream", "venv", "python", "python-runtime-root", "sudo", "bubblewrap", "model-snapshot", "hf-hub", "alfworld-source-archive", "lock"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--container", required=True); args = parser.parse_args(argv)
    paths = LivePaths(**{name.replace("-", "_"): getattr(args, name.replace("-", "_")) for name in ("repo", "protocol", "private-selection", "public-selection", "pool", "locator", "asset-root", "upstream", "venv", "python", "python-runtime-root", "sudo", "bubblewrap", "model-snapshot", "hf-hub", "alfworld-source-archive", "lock")}, container_name=args.container)
    private, _ = run_live(paths)
    return 0 if private["status"] == COMPLETE_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
