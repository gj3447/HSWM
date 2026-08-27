from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import unicodedata

import pytest

from _research.dnrd import judge as dnrd_judge
from _research.dnrd.execute import (
    ATTEMPT_MARKER_SCOPE,
    BRIDGE_MOUNT_CLOSURE_LAYOUT,
    BRIDGE_MOUNT_CLOSURE_SCHEMA,
    CORE_SOURCE_FILES,
    ExecutionConfig,
    ExecutionDependencies,
    ExecutionRefusal,
    PREREG_CLAIM_BOUNDARY,
    RATIFICATION_TEMPLATE,
    RATIFICATION_TEMPLATE_VERSION,
    RUNTIME_TREE_MANIFEST_SCHEMA,
    SCORER_ARGUMENT_CONTRACT,
    TOKENIZER_PREFLIGHT_PROMPT,
    _DurableJsonlEventLedger,
    _ProductionBridgeMountClosureExporter,
    _attempt_lock,
    _bundle_index,
    _execute,
    _json_object_unformatted,
    _load_source_manifest,
    _plain_file,
    _production_dependencies,
    _runtime_tree_manifest,
    _validate_preregistration,
    _verify_static_pins,
    execute_with_dependencies,
)
from _research.dnrd.live import (
    CHAT_CONFIG,
    MODEL_ID,
    MODEL_MAX_LENGTH,
    MODEL_ROOT,
    VLLM_VERSION,
    HttpResponse,
    OpenAICompatibleDnrdConfig,
    preflight_deployment_and_tokenizer,
)
from _research.dnrd.seed import (
    QUICKNET_CHAIN_HASH,
    QUICKNET_GENESIS_TIME_UNIX,
    QUICKNET_GROUP_HASH,
    QUICKNET_PERIOD_SECONDS,
    QUICKNET_PUBLIC_KEY,
    QUICKNET_SIGNATURE_SCHEME,
    first_eligible_quicknet_round,
    quicknet_round_time_unix,
)
from _research.dnrd.task_family import canonical_json, commitment
from _research.dnrd.runner import (
    ARMS,
    BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA,
    BridgeMountClosureExport,
    MAX_OUTPUT_TOKENS,
    MOUNT_ROLES,
)
from test_hswm_dnrd_runner import EvidenceAnswerer, RecordingBridge, RecordingScorer


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_runtime_manifest(config: ExecutionConfig, value: dict) -> ExecutionConfig:
    digest = _write_json(config.bridge_runtime_tree_manifest_path, value)  # type: ignore[arg-type]
    return replace(config, bridge_runtime_tree_manifest_sha256=digest)


class _FixtureClosureExporter:
    """Test-only callback: real raw mount copying is production-only I/O."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.plans: list[dict] = []

    def export(
        self,
        plan: dict,
        *,
        forbidden_markers: frozenset[str],
    ) -> BridgeMountClosureExport:
        assert forbidden_markers
        frozen = json.loads(canonical_json(plan))
        self.plans.append(frozen)
        closure = self.output_root / "bridge_mount_closure"
        closure.mkdir(mode=0o700)
        mounts = [
            {"stream_id": stream["stream_id"], "arm": arm, **arm_value}
            for stream in frozen["streams"]
            for arm, arm_value in stream["arms"].items()
        ]
        mounts.sort(key=lambda value: (value["stream_id"], value["arm"]))
        unsigned = {
            "schema_version": BRIDGE_MOUNT_CLOSURE_SCHEMA,
            "layout": BRIDGE_MOUNT_CLOSURE_LAYOUT,
            "bridge_state_evidence_sha256": frozen["bridge_state_evidence_sha256"],
            "closure_plan_sha256": commitment(frozen),
            "mounts": mounts,
            "files": [],
        }
        manifest = {**unsigned, "receipt_sha256": commitment(unsigned)}
        target = self.output_root / "bridge_mount_closure.json"
        target.write_bytes(canonical_json(manifest))
        return BridgeMountClosureExport(
            artifact_sha256=_hash(target),
            watermark_detected=False,
        )


class _PublicOnlyFixtureScorer:
    """Test scorer that owns no generated gold and receives only a seal."""

    def __init__(self, source_sha256: str) -> None:
        self.source_sha256 = source_sha256

    def score(self, sealed_response: dict) -> dict:
        ordinal = int(sealed_response["episode_id"].split(":")[3])
        context_index, route_index = divmod(ordinal, 2)
        reward = 1_000_000 if route_index == context_index % 2 else -1_000_000
        digest = commitment({
            "episode_id": sealed_response["episode_id"],
            "selected_route_id": sealed_response["selected_route_id"],
            "response_commitment": sealed_response["response_commitment"],
            "private_manifest_commitment": sealed_response["private_manifest_commitment"],
            "reward": reward,
            "scorer_source_identity": self.source_sha256,
        })
        return {
            "episode_id": sealed_response["episode_id"],
            "selected_route_id": sealed_response["selected_route_id"],
            "reward": reward,
            "outcome_digest": digest,
            "scorer_source_identity": self.source_sha256,
            "scorer_address": "_research/dnrd/scorer.py",
            "role_separation": "DECLARED_ROLE_SEPARATION_NOT_PROVEN",
        }


def _write_json(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))
    return _hash(path)


def _write_immutable(path: Path, body: bytes) -> str:
    """Build a fixture file with the exact durable adapter file mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.chmod(0o400)
    return hashlib.sha256(body).hexdigest()


def _mount_id(index: int) -> str:
    return f"dnrd-mount-v1-00000000-0000-4000-8000-{index:012x}"


def _closure_fixture(state_root: Path, output_root: Path) -> dict:
    """Create the smallest exact-shaped raw adapter tree for copier tests.

    The production exporter intentionally treats these as opaque V2 bytes; the
    bundle verifier, rather than this fixture, replays their canonical atom
    semantics.  Object filenames nevertheless bind their exact bytes here,
    exercising the copy boundary's anti-tamper check.
    """
    state_root.mkdir(mode=0o700)
    state_root.chmod(0o700)
    for name in ("mounts", "registry", "streams", "controls"):
        child = state_root / name
        child.mkdir(mode=0o700)
        child.chmod(0o700)
    output_root.mkdir(mode=0o700)
    output_root.chmod(0o700)
    _write_immutable(
        state_root / "root-config.json",
        canonical_json(
            {
                "schema_version": "hswm-dnrd-routing-diagnostic-process-root-config/v1",
                "frozen_scorer_source_sha256": "a" * 64,
            }
        ),
    )
    streams: list[dict] = []
    next_mount = 0
    for stream_index in range(4):
        stream_id = f"stream-{stream_index}"
        _write_immutable(
            state_root / "streams" / f"{stream_id}.json",
            canonical_json(
                {
                    "schema_version": "hswm-dnrd-routing-diagnostic-stream-reservation/v1",
                    "stream_id": stream_id,
                    "public_stream_sha256": hashlib.sha256(stream_id.encode()).hexdigest(),
                }
            ),
        )
        for arm in ("RAW_EQUAL_BUDGET", "BINDING_DERANGED_NUMERIC_PLACEBO"):
            _write_immutable(
                state_root / "controls" / f"{stream_id}-{arm}.json",
                canonical_json(
                    {
                        "schema_version": "hswm-dnrd-routing-diagnostic-control-reservation/v1",
                        "stream_id": stream_id,
                        "arm": arm,
                        "source_mount_id": _mount_id(0),
                        "source_state_sha256": "b" * 64,
                        "target_payload_sha256": "c" * 64,
                    }
                ),
            )
        arms: dict[str, dict] = {}
        for arm in ARMS:
            mount_id = _mount_id(next_mount)
            next_mount += 1
            mount_root = state_root / "mounts" / mount_id
            mount_root.mkdir(mode=0o700)
            mount_root.chmod(0o700)
            for leaf in ("schema-bindings", "objects", "journal-objects", "journal-slots"):
                leaf_root = mount_root / leaf
                leaf_root.mkdir(mode=0o700)
                leaf_root.chmod(0o700)
            binding = canonical_json({"schema": "hswm:dnrd:v1", "mount": mount_id})
            _write_immutable(
                mount_root / "schema-bindings" / hashlib.sha256(binding).hexdigest(), binding
            )
            object_body = canonical_json({"kind": "object", "mount": mount_id})
            object_digest = hashlib.sha256(object_body).hexdigest()
            _write_immutable(mount_root / "objects" / object_digest, object_body)
            journal_body = canonical_json({"kind": "journal", "mount": mount_id})
            journal_digest = hashlib.sha256(journal_body).hexdigest()
            _write_immutable(mount_root / "journal-objects" / journal_digest, journal_body)
            slot_body = canonical_json({"head": journal_digest, "mount": mount_id})
            _write_immutable(
                mount_root / "journal-slots" / hashlib.sha256(slot_body).hexdigest(),
                slot_body,
            )
            _write_immutable(
                state_root / "registry" / f"{mount_id}.json",
                canonical_json({"mount_id": mount_id, "mount_role": MOUNT_ROLES[arm]}),
            )
            arms[arm] = {
                "mount_id": mount_id,
                "mount_role": MOUNT_ROLES[arm],
                "pre_evaluation_journal_sha256": journal_digest,
                "post_evaluation_journal_sha256": journal_digest,
                "pre_evaluation_routing_payload_sha256": object_digest,
                "post_evaluation_routing_payload_sha256": object_digest,
            }
        streams.append({"stream_id": stream_id, "arms": arms})
    return {
        "schema_version": BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA,
        "bridge_state_evidence_sha256": "d" * 64,
        "streams": streams,
    }


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False, env=env)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _verifier_receipt(
    source_unix: int,
    ratification_unix: int,
    helper: str,
    lock: str,
    bundle: str,
    node_sha256: str,
    node_version: str,
) -> bytes:
    round_number = first_eligible_quicknet_round(source_freeze_unix=source_unix, user_ratification_unix=ratification_unix)
    signature = "ab" * 48
    pulse = {
        "randomness": hashlib.sha256(bytes.fromhex(signature)).hexdigest(),
        "round": round_number,
        "round_time_unix": quicknet_round_time_unix(round_number),
        "signature": signature,
    }
    canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    unsigned = {
        "chain": {
            "beacon_id": "quicknet",
            "genesis_time": QUICKNET_GENESIS_TIME_UNIX,
            "group_hash": QUICKNET_GROUP_HASH,
            "hash": QUICKNET_CHAIN_HASH,
            "period": QUICKNET_PERIOD_SECONDS,
            "public_key": QUICKNET_PUBLIC_KEY,
            "scheme_id": QUICKNET_SIGNATURE_SCHEME,
        },
        "chronology_claim_allowed": False,
        "helper_version": "hswm-swm0w-drand-node-verifier/v1",
        "input_fixture_sha256": None,
        "mode": "online",
        "pulse": pulse,
        "pulse_source_url": f"https://api.drand.sh/{QUICKNET_CHAIN_HASH}/public/{round_number}",
        "schema_version": "hswm-swm0w-drand-verification-receipt/v1",
        "verification": {
            "accepted_beacon_sha256": hashlib.sha256(canonical({key: pulse[key] for key in ("randomness", "round", "signature")})).hexdigest(),
            "accepted_by": "drand-client.fetchBeacon",
            "network_policy": "ONLINE_EXPLICIT",
            "randomness_derivation": "SHA256(raw_signature_bytes)",
            "signature_scheme": "bls-unchained-g1-rfc9380",
        },
        "verified_at_unix": pulse["round_time_unix"],
        "verifier": {
            "git_commit": "6" * 40,
            "git_tag_url": "https://example.invalid/drand",
            "helper_sha256": helper,
            "npm_integrity": "sha512-fixture",
            "npm_shasum": "7" * 40,
            "package": "drand-client",
            "package_json_sha256": "8" * 64,
            "package_lock_sha256": lock,
            "runtime_bundle_sha256": bundle,
            "runtime_engine": "Node.js",
            "runtime_exec_sha256": node_sha256,
            "runtime_trust_status": "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED",
            "runtime_version": node_version,
            "source_tarball": "https://example.invalid/drand.tgz",
            "version": "1.4.2",
        },
    }
    return canonical({**unsigned, "receipt_sha256": hashlib.sha256(canonical(unsigned)).hexdigest()}) + b"\n"


class _PreflightTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, *, method: str, url: str, **_: object) -> HttpResponse:
        self.calls.append((method, url))
        if url.endswith("/v1/models"):
            body = {"data": [{"id": MODEL_ID, "root": MODEL_ROOT, "max_model_len": MODEL_MAX_LENGTH}]}
        elif url.endswith("/version"):
            body = {"version": VLLM_VERSION}
        elif url.endswith("/tokenize"):
            body = {"count": 2, "tokens": [1, 2]}
        else:
            raise AssertionError(url)
        return HttpResponse(200, json.dumps(body).encode())


def _receipt(value: dict) -> tuple[dict, str]:
    unsigned = dict(value)
    unsigned["receipt_sha256"] = commitment(unsigned)
    return unsigned, commitment(unsigned)


def _fixture(
    tmp_path: Path,
    *,
    noncanonical_ci_raw: bool = False,
) -> tuple[ExecutionConfig, ExecutionDependencies, list[list[str]]]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "DNRD Fixture")
    for relative in sorted(CORE_SOURCE_FILES):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"fixture source {relative}\n".encode())
    source_package = {
        "name": "@hswm/effect-runtime",
        "version": "0.0.0",
        "dependencies": {"effect": "fixture"},
        "devDependencies": {"@types/node": "fixture", "typescript": "fixture"},
    }
    (repo / "src/hswm/effect-runtime/package.json").write_bytes(
        canonical_json(source_package)
    )
    selected_package_names = (
        "@standard-schema/spec",
        "@types/node",
        "effect",
        "fast-check",
        "pure-rand",
        "typescript",
        "undici-types",
    )
    (repo / "src/hswm/effect-runtime/package-lock.json").write_bytes(
        canonical_json(
            {
                "name": "@hswm/effect-runtime",
                "lockfileVersion": 3,
                "packages": {
                    "": source_package,
                    **{
                        f"node_modules/{name}": {"name": name, "version": "fixture"}
                        for name in selected_package_names
                    },
                },
            }
        )
    )
    source_manifest_value = {
        "schema_version": "hswm-dnrd-source-freeze-manifest/v1",
        "experiment_id": "HSWM-DNRD-2",
        "source_commit_tree_bound_externally": "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE",
        "files": [
            {"path": relative, "sha256": _hash(repo / relative)}
            for relative in sorted(CORE_SOURCE_FILES)
        ],
    }
    source_manifest = repo / "source_manifest.json"
    source_manifest_sha = _write_json(source_manifest, source_manifest_value)
    _git(repo, "add", ".")
    date_a = {**dict(), "GIT_AUTHOR_DATE": "1970-01-01T00:00:01 +0000", "GIT_COMMITTER_DATE": "1970-01-01T00:00:01 +0000"}
    _git(repo, "commit", "-m", "source A", env={**dict(__import__("os").environ), **date_a})
    source_a = _git(repo, "rev-parse", "HEAD")
    source_tree = _git(repo, "rev-parse", f"{source_a}^{{tree}}")

    pin_root = tmp_path / "pins"
    pin_root.mkdir()
    helper = repo / "_research/dnrd/verify-beacon.mjs"
    lock = repo / "tools/swm0w_drand/package-lock.json"
    bundle = repo / "tools/swm0w_drand/node_modules/drand-client/build/esm/index.mjs"
    (repo / ".git/info/exclude").write_text(
        "tools/swm0w_drand/node_modules/\n", encoding="utf-8"
    )
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"fixture pinned self-contained verifier bundle\n")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    bridge_impl = runtime_root / "bridge.js"
    bridge_impl.write_text("export {};\n", encoding="utf-8")
    typescript_root = runtime_root / "node_modules" / "typescript"
    (typescript_root / "bin").mkdir(parents=True)
    (typescript_root / "lib").mkdir()
    compiler_paths = {
        "package_json_path": "node_modules/typescript/package.json",
        "bin_tsc_path": "node_modules/typescript/bin/tsc",
        "lib_tsc_path": "node_modules/typescript/lib/tsc.js",
        "lib_typescript_path": "node_modules/typescript/lib/typescript.js",
    }
    for relative, body in {
        compiler_paths["package_json_path"]: b'{"name":"typescript","version":"fixture"}\n',
        compiler_paths["bin_tsc_path"]: b"#!/usr/bin/env node\n",
        compiler_paths["lib_tsc_path"]: b"export {};\n",
        compiler_paths["lib_typescript_path"]: b"export {};\n",
    }.items():
        target = runtime_root / relative
        target.write_bytes(body)
    package_dependencies = {
        "@standard-schema/spec": {},
        "@types/node": {"undici-types": "fixture"},
        "effect": {"@standard-schema/spec": "fixture", "fast-check": "fixture"},
        "fast-check": {"pure-rand": "fixture"},
        "pure-rand": {},
        "typescript": {},
        "undici-types": {},
    }
    package_roots: dict[str, Path] = {"typescript": typescript_root}
    for name, dependencies in package_dependencies.items():
        package_root = runtime_root / "node_modules" / name
        package_root.mkdir(parents=True, exist_ok=True)
        package_roots[name] = package_root
        (package_root / "package.json").write_bytes(
            canonical_json(
                {"name": name, "version": "fixture", "dependencies": dependencies}
            )
        )
        if name != "typescript":
            (package_root / "index.js").write_bytes(b"export {};\n")
    external_packages = []
    for name in sorted(package_roots):
        package_root = package_roots[name]
        relative_root = package_root.relative_to(runtime_root).as_posix()
        entrypoint = (
            compiler_paths["lib_typescript_path"]
            if name == "typescript"
            else f"{relative_root}/index.js"
        )
        package_json_path = f"{relative_root}/package.json"
        external_packages.append(
            {
                "name": name,
                "version": "fixture",
                "package_root": relative_root,
                "package_json_path": package_json_path,
                "package_json_sha256": _hash(runtime_root / package_json_path),
                "resolved_entrypoint_path": entrypoint,
                "resolved_entrypoint_sha256": _hash(runtime_root / entrypoint),
                "files": [
                    {
                        "path": path.relative_to(runtime_root).as_posix(),
                        "sha256": _hash(path),
                    }
                    for path in sorted(package_root.rglob("*"))
                    if path.is_file()
                ],
            }
        )
    runtime_manifest = runtime_root / "runtime-tree.json"
    runtime_manifest_value = {
        "schema_version": RUNTIME_TREE_MANIFEST_SCHEMA,
        "root_path": str(runtime_root),
        "entrypoint": "bridge.js",
        "files": [{"path": "bridge.js", "sha256": _hash(bridge_impl)}],
        "external_packages": external_packages,
        "build_provenance": {
            "source_a_commit": source_a,
            "source_a_tree": source_tree,
            "source_manifest_path": "source_manifest.json",
            "source_manifest_sha256": source_manifest_sha,
            "node_executable_sha256": _hash(Path(shutil.which("node") or "").resolve()),
            "node_version": subprocess.run([str(Path(shutil.which("node") or "").resolve()), "--version"], text=True, capture_output=True, check=True).stdout.strip(),
            "dependency_materialization_command": ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            "compilation_command": ["{PINNED_NODE_EXECUTABLE}", "node_modules/typescript/lib/tsc.js", "-p", "tsconfig.dnrd.json"],
            "claim_boundary": "SOURCE_SELECTED_PACKAGE_AND_COMPILER_BYTES_PINNED_BUILD_NOT_INDEPENDENTLY_REEXECUTED",
            "package_roots": ["@types/node", "effect", "typescript"],
            "source_inputs": [
                {"path": relative, "sha256": _hash(repo / relative)}
                for relative in sorted(CORE_SOURCE_FILES)
            ],
            "typescript": {
                **compiler_paths,
                "package_json_sha256": _hash(runtime_root / compiler_paths["package_json_path"]),
                "bin_tsc_sha256": _hash(runtime_root / compiler_paths["bin_tsc_path"]),
                "lib_tsc_sha256": _hash(runtime_root / compiler_paths["lib_tsc_path"]),
                "lib_typescript_sha256": _hash(runtime_root / compiler_paths["lib_typescript_path"]),
            },
        },
    }
    runtime_manifest_sha = _write_json(runtime_manifest, runtime_manifest_value)
    state_root, attempt_root = tmp_path / "state", tmp_path / "attempts"
    state_root.mkdir(mode=0o700)
    attempt_root.mkdir(mode=0o700)
    state_root.chmod(0o700)
    attempt_root.chmod(0o700)
    node = Path(shutil.which("node") or "").resolve()
    assert node.is_file()
    node_version = subprocess.run([str(node), "--version"], text=True, capture_output=True, check=True).stdout.strip()
    python = Path(sys.executable).resolve()
    scorer_source = repo / "_research/dnrd/scorer.py"
    bridge_config = {
        "root_path": str(state_root),
        "frozen_scorer_source_sha256": _hash(scorer_source),
    }

    ci_raw = (
        f'{{ "conclusion" : "success", "head_sha" : "{source_a}", "id" : 7 }}'
        if noncanonical_ci_raw
        else canonical_json({"id": 7, "head_sha": source_a, "conclusion": "success"}).decode()
    )
    ci_unsigned = {
        "schema_version": "hswm-dnrd-source-ci-receipt/v1",
        "provider": "GITHUB_ACTIONS",
        "run_id": 7,
        "head_sha": source_a,
        "conclusion": "success",
        "raw_response_sha256": hashlib.sha256(ci_raw.encode()).hexdigest(),
        "raw_response_utf8": ci_raw,
    }
    ci_receipt, _ = _receipt(ci_unsigned)
    ci_path = pin_root / "source-ci.json"
    ci_sha = _write_json(ci_path, ci_receipt)

    prereg_path = "prereg/dnrd.json"
    prereg = {
        "schema_version": "hswm-durable-numeric-routing-diagnostic-preregistration/v2",
        "experiment_id": "HSWM-DNRD-2",
        "protocol_version": "v2",
        "created_at": "2026-08-27",
        "status": "FROZEN_AWAITING_EXACT_HASH_RATIFICATION",
        "authority": {
            "broad_research_continuation_requested": True,
            "exact_content_hash_user_ratified_at_freeze": False,
            "measurement_authorized_at_freeze": False,
            "measurement_requires_external_exact_hash_ratification_receipt": True,
            "scientific_judgment_emitted": False,
            "external_governance_required": False,
        },
        "canonical_role": PREREG_CLAIM_BOUNDARY["canonical_role"],
        "predecessor_bindings": PREREG_CLAIM_BOUNDARY["predecessor_bindings"],
        "forbidden_rescues": PREREG_CLAIM_BOUNDARY["forbidden_rescues"],
        "scientific_question": PREREG_CLAIM_BOUNDARY["scientific_question"],
        "hypotheses": PREREG_CLAIM_BOUNDARY["hypotheses"],
        "testbed": {
            "family": "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V1",
            "relationship_to_prior_p1": PREREG_CLAIM_BOUNDARY["testbed_claims"]["relationship_to_prior_p1"],
            "development_streams": 4,
            "training_calls_per_stream_maximum": 8,
            "paired_heldout_probes_per_stream": 8,
            "evaluation_arms": 4,
            "evaluation_calls": 128,
            "shared_learning_or_compiler_calls_maximum": 32,
            "client_dispatched_generation_request_ceiling": 160,
            "analysis_unit": PREREG_CLAIM_BOUNDARY["testbed_claims"]["analysis_unit"],
            "model": {
                "served_model_id": MODEL_ID,
                "substitution_allowed": False,
                "temperature": 0,
                "thinking": False,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "deployment_readback_required": True,
                "exact_weight_revision_attested": False,
                "exact_weight_identity_claimed": False,
            },
            "freshness": PREREG_CLAIM_BOUNDARY["testbed_claims"]["freshness"],
        },
        "learning_boundary": PREREG_CLAIM_BOUNDARY["learning_boundary"],
        "arms": PREREG_CLAIM_BOUNDARY["arms"],
        "interventions": PREREG_CLAIM_BOUNDARY["interventions"],
        "parity_and_leakage": {
            "same_served_model_id_and_chat_endpoint": True,
            "equal_client_dispatched_and_logical_requests": True,
            "equal_generation_limits_input_token_parity_not_claimed": True,
            "equal_candidate_evidence_universe": True,
            "all_active_payloads_within_byte_ceiling": True,
            "active_state_byte_ceiling": 16_384,
            "full_raw_numeric_payload_bytes_equal": True,
            "full_deranged_numeric_payload_byte_count_equal": True,
            "arm_labels_hidden_from_model": True,
            "fresh_process_recovery_observed": True,
            "distinct_arm_mount_ids": True,
            "evaluation_read_only_wrt_routing_observed": True,
            "cache_hits_required": 0,
            "gold_open_only_after_response_seal": True,
            "compiler_input_audit": PREREG_CLAIM_BOUNDARY["parity_claims"]["compiler_input_audit"],
            "canary": PREREG_CLAIM_BOUNDARY["parity_claims"]["canary"],
        },
        "diagnostic_readouts": PREREG_CLAIM_BOUNDARY["diagnostic_readouts"],
        "void_conditions": PREREG_CLAIM_BOUNDARY["void_conditions"],
        "single_attempt_policy": PREREG_CLAIM_BOUNDARY["single_attempt_policy"],
        "required_before_measurement": PREREG_CLAIM_BOUNDARY["required_before_measurement"],
        "result_promotion": PREREG_CLAIM_BOUNDARY["result_promotion"],
        "measurement_gate": PREREG_CLAIM_BOUNDARY["measurement_gate"],
        "ratification": {"statement_template_version": RATIFICATION_TEMPLATE_VERSION, "statement_template": RATIFICATION_TEMPLATE},
        "source_a_ci": {"receipt_sha256": ci_sha, "run_id": 7, "head_sha": source_a, "conclusion": "success"},
        "runtime_bindings": {
            "model_endpoint": "http://127.0.0.1:9999",
            "bridge_implementation_sha256": _hash(bridge_impl),
            "bridge_runtime_tree_manifest_sha256": runtime_manifest_sha,
            "bridge_config_sha256": commitment(bridge_config),
            "scorer_implementation_sha256": _hash(scorer_source),
            "node_executable_sha256": _hash(node),
            "node_version": node_version,
            "python_executable_sha256": _hash(python),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "unicode_data_version": unicodedata.unidata_version,
            "verifier_helper_sha256": _hash(helper),
            "verifier_package_lock_sha256": _hash(lock),
            "verifier_runtime_bundle_sha256": _hash(bundle),
            "subprocess_environment": {
                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1", "TZ": "UTC", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin",
            },
        },
    }
    prereg_file = repo / prereg_path
    prereg_sha = _write_json(prereg_file, prereg)
    _git(repo, "add", prereg_path)
    date_b = {"GIT_AUTHOR_DATE": "1970-01-01T00:00:02 +0000", "GIT_COMMITTER_DATE": "1970-01-01T00:00:02 +0000"}
    _git(repo, "commit", "-m", "preregistration B", env={**dict(__import__("os").environ), **date_b})
    prereg_b = _git(repo, "rev-parse", "HEAD")

    ratification_text = RATIFICATION_TEMPLATE.format(preregistration_sha256=prereg_sha)
    rat_unsigned = {
        "schema_version": "hswm-dnrd-ratification-receipt/v2",
        "preregistration_sha256": prereg_sha,
        "statement_sha256": hashlib.sha256(ratification_text.encode()).hexdigest(),
        "ratified_at_unix": 3,
        "attested_by": "fixture",
    }
    rat_receipt, _ = _receipt(rat_unsigned)
    rat_path = pin_root / "ratification.json"
    rat_sha = _write_json(rat_path, rat_receipt)
    output_root = tmp_path / "output"
    config = ExecutionConfig(
        repo, source_a, source_tree, "source_manifest.json", source_manifest_sha,
        prereg_b, prereg_path, prereg_sha, 1, 3, ratification_text,
        hashlib.sha256(ratification_text.encode()).hexdigest(), output_root,
        "http://127.0.0.1:9999", bridge_impl, _hash(bridge_impl),
        (str(node), str(bridge_impl)), bridge_config,
        scorer_source.resolve(), _hash(scorer_source),
        (str(python), *SCORER_ARGUMENT_CONTRACT), (str(node), str(helper)),
        helper, _hash(helper), lock, _hash(lock), bundle, _hash(bundle),
        attempt_registry_root=attempt_root, ratification_receipt_path=rat_path,
        ratification_receipt_sha256=rat_sha, source_ci_receipt_path=ci_path,
        source_ci_receipt_sha256=ci_sha, tokenizer_preflight_prompt=TOKENIZER_PREFLIGHT_PROMPT,
        bridge_runtime_root=runtime_root, bridge_state_root=state_root,
        bridge_runtime_tree_manifest_path=runtime_manifest,
        bridge_runtime_tree_manifest_sha256=runtime_manifest_sha,
        node_executable_path=node, node_executable_sha256=_hash(node), node_version=node_version,
        python_executable_path=python, python_executable_sha256=_hash(python),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        unicode_data_version=unicodedata.unidata_version, scorer_import_root=repo,
    )
    calls: list[list[str]] = []
    answerer = EvidenceAnswerer(model=MODEL_ID, endpoint=config.model_endpoint)
    transport = _PreflightTransport()

    def verifier(command: list[str]) -> bytes:
        calls.append(list(command))
        return _verifier_receipt(
            1, 3, _hash(helper), _hash(lock), _hash(bundle), _hash(node), node_version
        )

    def preflight(_: ExecutionConfig) -> dict:
        return preflight_deployment_and_tokenizer(OpenAICompatibleDnrdConfig(config.model_endpoint), transport, tokenizer_prompt=TOKENIZER_PREFLIGHT_PROMPT)

    dependencies = ExecutionDependencies(answerer, RecordingBridge(), _PublicOnlyFixtureScorer(_hash(scorer_source)), verifier, preflight, model_event_ledger=lambda: tuple(answerer.events), closure_exporter=_FixtureClosureExporter(output_root))
    return config, dependencies, calls


def test_execute_writes_self_contained_no_verdict_bundle(tmp_path: Path) -> None:
    config, dependencies, calls = _fixture(tmp_path)
    result = execute_with_dependencies(config, dependencies)
    assert len(calls) == 1
    assert calls[0] == [
        *config.verifier_command,
        "online",
        "--expected-round",
        str(first_eligible_quicknet_round(source_freeze_unix=1, user_ratification_unix=3)),
    ]
    assert result.runner_result.candidate is not None
    artifacts = {
        "source_manifest.json", "preregistration.json", "source_ci_receipt.json",
        "ratification_receipt.json", "git_chronology_evidence.json", "public_manifest.json",
        "pulse_verifier_receipt.json", "pulse_binding.json", "deployment_receipt.json",
        "runtime_receipt.json", "bridge_runtime_tree_manifest.json", "attempt_lock_receipt.json",
        "config_readback.json", "runner_events.jsonl", "model_events.jsonl",
        "bridge_state_evidence.json", "candidate.json", "bundle_index.json",
        "bridge_mount_closure.json", "verifier_runtime_bundle.mjs",
    }
    assert all((result.output_dir / name).is_file() for name in artifacts)
    assert (result.output_dir / "source_closure" / "_research/dnrd/runner.py").is_file()
    assert (result.output_dir / "bridge_runtime_closure" / "bridge.js").is_file()
    assert (result.output_dir / "private" / "private_manifest.json").is_file()
    candidate = json.loads((result.output_dir / "candidate.json").read_text())
    chronology = result.output_dir / "git_chronology_evidence.json"
    assert candidate["bindings"]["git_chronology_evidence_sha256"] == _hash(chronology)
    assert candidate["bindings"]["bridge_mount_closure_sha256"] == _hash(
        result.output_dir / "bridge_mount_closure.json"
    )
    marker = json.loads((result.output_dir / "attempt_lock_receipt.json").read_text())
    assert marker["enforcement_scope"] == ATTEMPT_MARKER_SCOPE
    assert len((result.output_dir / "model_events.jsonl").read_text().splitlines()) == 320
    assert "raw_response_utf8" in (result.output_dir / "model_events.jsonl").read_text()
    index = json.loads((result.output_dir / "bundle_index.json").read_text())
    assert index["schema_version"] == "hswm-dnrd-evidence-bundle-index/v1"
    assert "candidate.json" in {entry["path"] for entry in index["artifacts"]}
    assert "private/private_manifest.json" in {entry["path"] for entry in index["artifacts"]}
    assert dnrd_judge._validate_bundle_index(result.output_dir)["candidate.json"] == _hash(
        result.output_dir / "candidate.json"
    )
    assert stat.S_IMODE(result.output_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((result.output_dir / "private" / "private_manifest.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((result.output_dir / "source_closure").stat().st_mode) == 0o500
    assert stat.S_IMODE((result.output_dir / "bridge_runtime_closure").stat().st_mode) == 0o500
    assert stat.S_IMODE(
        (result.output_dir / "source_closure/_research/dnrd/scorer.py").stat().st_mode
    ) == 0o400
    runtime = json.loads((result.output_dir / "runtime_receipt.json").read_text())
    assert runtime["schema_version"] == "hswm-dnrd-runtime-receipt/v3"
    assert runtime["bridge_execution_root"] == "bridge_runtime_closure"
    assert runtime["scorer_execution_root"] == "source_closure"
    assert runtime["bridge_command"][1].startswith("{OUTPUT_ROOT}/bridge_runtime_closure/")
    assert runtime["verifier_command"] == list(config.verifier_command)
    assert runtime["verifier_argument_contract"] == [
        "online", "--expected-round", "{FIRST_ELIGIBLE_ROUND}"
    ]
    assert runtime["verifier_subprocess_environment"] == runtime["subprocess_environment"]
    assert runtime["verifier_timeout_seconds"] == 60
    assert runtime["verifier_helper_sha256"] == config.verifier_helper_sha256
    assert runtime["verifier_package_lock_sha256"] == config.verifier_package_lock_sha256
    assert runtime["verifier_runtime_bundle_sha256"] == config.verifier_runtime_bundle_sha256
    assert runtime["verifier_runtime_bundle_evidence_path"] == "verifier_runtime_bundle.mjs"
    assert runtime["execution_adapter_boundary"] == (
        "TEST_ONLY_INJECTED_DEPENDENCIES_NOT_ADMISSIBLE_SCIENTIFIC_EVIDENCE"
    )
    assert stat.S_IMODE(
        (result.output_dir / "verifier_runtime_bundle.mjs").stat().st_mode
    ) == 0o400
    assert (result.output_dir / "verifier_runtime_bundle.mjs").read_bytes() == (
        config.verifier_runtime_bundle_path.read_bytes()
    )
    chronology_value = json.loads(chronology.read_text())
    source_value = json.loads((result.output_dir / "source_manifest.json").read_text())
    assert [row["path"] for row in chronology_value["source"]["file_blobs"]] == [
        row["path"] for row in source_value["files"]
    ]
    preregistration_bytes = (result.output_dir / "preregistration.json").read_bytes()
    candidate_value = json.loads((result.output_dir / "candidate.json").read_text())
    config_readback = json.loads((result.output_dir / "config_readback.json").read_text())
    attempt_receipt = json.loads(
        (result.output_dir / "attempt_lock_receipt.json").read_text()
    )
    dnrd_judge._validate_config_readback(config_readback, candidate_value, runtime)
    with pytest.raises(dnrd_judge.BundleRefusal, match="production hash-bound"):
        dnrd_judge._validate_runtime_and_attempt(
            runtime, attempt_receipt, candidate_value
        )
    source_path_runtime = json.loads(json.dumps(runtime))
    source_path_runtime["bridge_command"][1] = config_readback["bridge_command"][1]
    with pytest.raises(dnrd_judge.BundleRefusal, match="copied execution paths"):
        dnrd_judge._validate_config_readback(
            config_readback, candidate_value, source_path_runtime
        )
    verifier_path_runtime = json.loads(json.dumps(runtime))
    verifier_path_runtime["verifier_command"][1] = "/tmp/unpinned-verifier.mjs"
    with pytest.raises(dnrd_judge.BundleRefusal, match="copied execution paths"):
        dnrd_judge._validate_config_readback(
            config_readback, candidate_value, verifier_path_runtime
        )
    verifier_env_runtime = json.loads(json.dumps(runtime))
    verifier_env_runtime["verifier_subprocess_environment"]["NODE_OPTIONS"] = "--import=attacker"
    with pytest.raises(dnrd_judge.BundleRefusal, match="copied execution paths"):
        dnrd_judge._validate_config_readback(
            config_readback, candidate_value, verifier_env_runtime
        )
    jointly_poisoned_env_runtime = json.loads(json.dumps(runtime))
    jointly_poisoned_env_runtime["subprocess_environment"]["NODE_OPTIONS"] = (
        "--import=attacker"
    )
    jointly_poisoned_env_runtime["verifier_subprocess_environment"]["NODE_OPTIONS"] = (
        "--import=attacker"
    )
    with pytest.raises(dnrd_judge.BundleRefusal, match="copied execution paths"):
        dnrd_judge._validate_config_readback(
            config_readback, candidate_value, jointly_poisoned_env_runtime
        )
    for field in ("node_version", "python_version", "unicode_data_version"):
        drifted_config = json.loads(json.dumps(config_readback))
        drifted_config[field] = "forged-runtime-version"
        with pytest.raises(dnrd_judge.BundleRefusal, match="chronology/runtime pins"):
            dnrd_judge._validate_config_readback(
                drifted_config, candidate_value, runtime
            )

    pulse_value = json.loads((result.output_dir / "pulse_binding.json").read_text())
    verifier_value = json.loads(
        (result.output_dir / "pulse_verifier_receipt.json").read_text()
    )
    verifier_value["verifier"]["runtime_exec_sha256"] = "0" * 64
    verifier_unsigned = {
        key: value for key, value in verifier_value.items() if key != "receipt_sha256"
    }
    verifier_value["receipt_sha256"] = commitment(verifier_unsigned)
    tampered_verifier_bytes = canonical_json(verifier_value) + b"\n"
    pulse_value["projection"]["verification_receipt_sha256"] = hashlib.sha256(
        tampered_verifier_bytes
    ).hexdigest()
    pulse_unsigned = {
        key: value for key, value in pulse_value.items() if key != "receipt_sha256"
    }
    pulse_value["receipt_sha256"] = commitment(pulse_unsigned)
    tampered_candidate = json.loads(json.dumps(candidate_value))
    tampered_candidate["bindings"]["pulse_receipt_sha256"] = pulse_value[
        "receipt_sha256"
    ]
    ratification_value = json.loads(
        (result.output_dir / "ratification_receipt.json").read_text()
    )
    preregistration_value = json.loads(preregistration_bytes)
    with pytest.raises(dnrd_judge.BundleRefusal, match="verifier provenance"):
        dnrd_judge._validate_pulse(
            pulse_value,
            tampered_verifier_bytes,
            tampered_candidate,
            ratification_value,
            preregistration_value,
        )
    dnrd_judge._validate_git_chronology(
        result.output_dir,
        chronology_value,
        candidate_value,
        source_value,
        (result.output_dir / "source_manifest.json").read_bytes(),
        preregistration_bytes,
    )
    tampered_chronology = json.loads(json.dumps(chronology_value))
    tampered_chronology["source"]["file_blobs"][0]["blob_oid"] = "0" * 40
    unsigned_chronology = dict(tampered_chronology)
    del unsigned_chronology["receipt_sha256"]
    tampered_chronology["receipt_sha256"] = commitment(unsigned_chronology)
    with pytest.raises(dnrd_judge.BundleRefusal, match="Source-A bytes"):
        dnrd_judge._validate_git_chronology(
            result.output_dir,
            tampered_chronology,
            candidate_value,
            source_value,
            (result.output_dir / "source_manifest.json").read_bytes(),
            preregistration_bytes,
        )
    assert "import judge" not in Path("_research/dnrd/execute.py").read_text()


def test_bundle_index_sorts_serialized_posix_paths_at_file_directory_prefix_collision(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "evidence"
    output_root.mkdir()
    (output_root / "assert.d.ts").write_text("file\n", encoding="utf-8")
    prefixed_directory = output_root / "assert"
    prefixed_directory.mkdir()
    (prefixed_directory / "strict.d.ts").write_text("nested\n", encoding="utf-8")

    index = _bundle_index(output_root)

    assert [entry["path"] for entry in index["artifacts"]] == [
        "assert.d.ts",
        "assert/strict.d.ts",
    ]


def test_execute_module_without_runtime_config_prints_usage_and_exits_two() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "_research.dnrd.execute"],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "usage:" in completed.stderr
    assert "RUNTIME_CONFIG.json" in completed.stderr


def test_injected_executor_has_no_production_admissibility_switch() -> None:
    parameters = inspect.signature(_execute).parameters
    assert tuple(parameters) == ("config", "dependencies")
    assert "require_official_runtime_identity" not in parameters


def test_production_adapters_target_output_copied_execution_closures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    monkeypatch.setenv(config.model_api_key_environment, "fixture-secret")
    dependencies = _production_dependencies(config)
    bridge = dependencies.bridge
    scorer = dependencies.scorer
    assert Path(bridge._implementation_path) == (  # type: ignore[attr-defined]
        config.output_root / "bridge_runtime_closure/bridge.js"
    )
    assert Path(bridge._working_directory) == (  # type: ignore[attr-defined]
        config.output_root / "bridge_runtime_closure"
    )
    assert Path(scorer._implementation_path) == (  # type: ignore[attr-defined]
        config.output_root / "source_closure/_research/dnrd/scorer.py"
    )
    assert Path(scorer._working_directory) == (  # type: ignore[attr-defined]
        config.output_root / "source_closure"
    )
    assert tuple(scorer._command) == config.scorer_command  # type: ignore[attr-defined]
    assert tuple(scorer._command[1:4]) == ("-I", "-S", "-c")  # type: ignore[attr-defined]


def test_static_pins_refuse_free_verifier_command_or_path_topology(
    tmp_path: Path,
) -> None:
    config, _, _ = _fixture(tmp_path)
    with pytest.raises(ExecutionRefusal, match="command binding"):
        _verify_static_pins(replace(config, verifier_command=("fixture-verifier",)))

    alternate_helper = tmp_path / "alternate-helper.mjs"
    alternate_helper.write_bytes(config.verifier_helper_path.read_bytes())
    with pytest.raises(ExecutionRefusal, match="topology"):
        _verify_static_pins(
            replace(
                config,
                verifier_helper_path=alternate_helper,
                verifier_command=(str(config.node_executable_path), str(alternate_helper)),
            )
        )

    with pytest.raises(ExecutionRefusal, match="response-form probe"):
        _verify_static_pins(replace(config, tokenizer_preflight_prompt="arbitrary probe"))


@pytest.mark.parametrize(
    "source",
    [
        b'import { forged } from "./mutable.mjs";\n',
        b'export { forged } from "./mutable.mjs";\n',
        b'const forged = await import("./mutable.mjs");\n',
    ],
)
def test_static_pins_refuse_verifier_bundle_external_esm_dependencies(
    tmp_path: Path, source: bytes
) -> None:
    config, _, _ = _fixture(tmp_path)
    config.verifier_runtime_bundle_path.write_bytes(source)
    config = replace(
        config,
        verifier_runtime_bundle_sha256=_hash(config.verifier_runtime_bundle_path),
    )
    with pytest.raises(ExecutionRefusal, match="external ESM dependency"):
        _verify_static_pins(config)


def test_production_static_pins_refuse_nonofficial_test_bundle(tmp_path: Path) -> None:
    config, _, _ = _fixture(tmp_path)
    with pytest.raises(ExecutionRefusal, match="official artifact"):
        _verify_static_pins(config, require_official_runtime_identity=True)


def test_production_verifier_uses_exact_abi_clean_environment_and_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    monkeypatch.setenv(config.model_api_key_environment, "fixture-secret")
    dependencies = _production_dependencies(config)
    observed: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = b"fixture-receipt\n"

    def fake_run(command, **kwargs):
        observed["command"] = list(command)
        observed.update(kwargs)
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    command = [
        *config.verifier_command,
        "online",
        "--expected-round",
        "123",
    ]
    assert dependencies.verifier_runner(command) == b"fixture-receipt\n"
    assert observed["command"] == command
    assert observed["cwd"] == config.verifier_helper_path.parent
    assert observed["timeout"] == 60
    environment = observed["env"]
    assert isinstance(environment, dict)
    assert config.model_api_key_environment not in environment
    assert "NODE_OPTIONS" not in environment
    assert environment["PATH"] == "/usr/bin:/bin"

    with pytest.raises(ExecutionRefusal, match="invocation drifted"):
        dependencies.verifier_runner(
            [*config.verifier_command, "--mode", "online", "--round", "123"]
        )


def test_dnrd_verifier_imports_the_exact_bundle_without_package_export_routing() -> None:
    source = Path("_research/dnrd/verify-beacon.mjs").read_text(encoding="utf-8")
    assert '"node_modules", "drand-client", "build", "esm", "index.mjs"' in source
    assert "validateRuntimeBundleSource(bundleBytes);" in source
    assert "await import(pathToFileURL(bundlePath).href)" in source
    assert source.index("validateRuntimeBundleSource(bundleBytes);") < source.index(
        "await import(pathToFileURL(bundlePath).href)"
    )
    assert 'from "drand-client"' not in source
    assert 'from "../../tools/swm0w_drand/node_modules/drand-client' not in source


@pytest.mark.parametrize(
    "field_path",
    [
        ("canonical_role",),
        ("predecessor_bindings",),
        ("forbidden_rescues",),
        ("scientific_question",),
        ("hypotheses",),
        ("testbed", "relationship_to_prior_p1"),
        ("testbed", "analysis_unit"),
        ("testbed", "freshness"),
        ("learning_boundary",),
        ("arms", "RAW_EQUAL_BUDGET"),
        ("interventions",),
        ("parity_and_leakage", "compiler_input_audit"),
        ("parity_and_leakage", "canary"),
        ("diagnostic_readouts",),
        ("void_conditions",),
        ("single_attempt_policy",),
        ("required_before_measurement",),
        ("result_promotion",),
        ("measurement_gate",),
    ],
)
def test_executor_refuses_any_broadened_preregistration_scientific_claim(
    tmp_path: Path, field_path: tuple[str, ...]
) -> None:
    config, _, _ = _fixture(tmp_path)
    prereg_path = config.repo_root / config.prereg_path
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    target = prereg
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = "CLAIM_LLM_LEARNING_EFFICACY_AND_UNSEEN_GENERALIZATION"
    prereg_sha256 = _write_json(prereg_path, prereg)
    config = replace(config, prereg_sha256=prereg_sha256)
    assert config.source_ci_receipt_path is not None
    source_ci = json.loads(config.source_ci_receipt_path.read_text(encoding="utf-8"))
    with pytest.raises(
        ExecutionRefusal,
        match="scientific claim boundary|RAW arm overclaims",
    ):
        _validate_preregistration(config, source_ci_receipt=source_ci)


def test_executor_refuses_claim_text_hidden_in_preregistration_created_at(
    tmp_path: Path,
) -> None:
    config, _, _ = _fixture(tmp_path)
    prereg_path = config.repo_root / config.prereg_path
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    prereg["created_at"] = (
        "2026-08-27; CLAIM_LLM_LEARNING_EFFICACY_AND_UNSEEN_GENERALIZATION"
    )
    prereg_sha256 = _write_json(prereg_path, prereg)
    config = replace(config, prereg_sha256=prereg_sha256)
    assert config.source_ci_receipt_path is not None
    source_ci = json.loads(config.source_ci_receipt_path.read_text(encoding="utf-8"))
    with pytest.raises(ExecutionRefusal, match="exact ISO-8601 date"):
        _validate_preregistration(config, source_ci_receipt=source_ci)


def test_production_mount_closure_export_is_exact_bounded_and_content_addressed(
    tmp_path: Path,
) -> None:
    state_root, output_root = tmp_path / "state", tmp_path / "output"
    plan = _closure_fixture(state_root, output_root)

    export = _ProductionBridgeMountClosureExporter(state_root, output_root).export(
        plan,
        forbidden_markers=frozenset({"dnrd-training-provenance:" + "a" * 32}),
    )

    manifest_path = output_root / "bridge_mount_closure.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert export.artifact_sha256 == hashlib.sha256(manifest_bytes).hexdigest()
    assert export.watermark_detected is False
    assert manifest["schema_version"] == BRIDGE_MOUNT_CLOSURE_SCHEMA
    assert manifest["layout"] == BRIDGE_MOUNT_CLOSURE_LAYOUT
    assert manifest["closure_plan_sha256"] == commitment(plan)
    assert len(manifest["mounts"]) == 16
    assert len({row["mount_id"] for row in manifest["mounts"]}) == 16
    assert manifest["files"] == sorted(manifest["files"], key=lambda row: row["path"])
    assert manifest["receipt_sha256"] == commitment(
        {key: value for key, value in manifest.items() if key != "receipt_sha256"}
    )
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o400
    assert stat.S_IMODE((output_root / "bridge_mount_closure").stat().st_mode) == 0o700
    for row in manifest["files"]:
        copied = output_root / "bridge_mount_closure" / row["path"]
        assert copied.is_file()
        assert stat.S_IMODE(copied.stat().st_mode) == 0o400
        assert row["mode"] == 0o400
        assert row["bytes"] == len(copied.read_bytes())
        assert row["sha256"] == _hash(copied)


def test_production_mount_closure_observes_canary_in_any_retained_raw_byte(
    tmp_path: Path,
) -> None:
    state_root, output_root = tmp_path / "state", tmp_path / "output"
    plan = _closure_fixture(state_root, output_root)
    canary = "dnrd-training-provenance:" + "a" * 32
    root_config = state_root / "root-config.json"
    root_config.chmod(0o600)
    _write_immutable(
        root_config,
        canonical_json(
            {
                "schema_version": "hswm-dnrd-routing-diagnostic-process-root-config/v1",
                "frozen_scorer_source_sha256": "a" * 64,
                "injected_unreferenced_marker": canary,
            }
        ),
    )

    export = _ProductionBridgeMountClosureExporter(state_root, output_root).export(
        plan,
        forbidden_markers=frozenset({canary}),
    )

    assert export.watermark_detected is True


def test_production_mount_closure_refuses_extra_or_tampered_raw_files(
    tmp_path: Path,
) -> None:
    state_root, output_root = tmp_path / "state-extra", tmp_path / "output-extra"
    plan = _closure_fixture(state_root, output_root)
    unexpected = state_root / "unplanned"
    unexpected.mkdir(mode=0o700)
    unexpected.chmod(0o700)
    with pytest.raises(ExecutionRefusal, match="unexpected mount-closure entries"):
        _ProductionBridgeMountClosureExporter(state_root, output_root).export(
            plan,
            forbidden_markers=frozenset({"dnrd-training-provenance:" + "a" * 32}),
        )
    assert not (output_root / "bridge_mount_closure").exists()
    assert not (output_root / "bridge_mount_closure.json").exists()

    state_root, output_root = tmp_path / "state-tampered", tmp_path / "output-tampered"
    plan = _closure_fixture(state_root, output_root)
    first_mount = plan["streams"][0]["arms"]["FULL"]["mount_id"]
    object_path = next((state_root / "mounts" / first_mount / "objects").iterdir())
    object_path.rename(object_path.with_name("0" * 64))
    with pytest.raises(ExecutionRefusal, match="filename does not bind exact bytes"):
        _ProductionBridgeMountClosureExporter(state_root, output_root).export(
            plan,
            forbidden_markers=frozenset({"dnrd-training-provenance:" + "a" * 32}),
        )
    assert not (output_root / "bridge_mount_closure").exists()
    assert not (output_root / "bridge_mount_closure.json").exists()


def test_source_freeze_lists_exact_transitive_ts_runtime_closure() -> None:
    """The source freeze must grow when a DNRD TS relative import grows."""
    repository = Path(__file__).resolve().parents[1]
    runtime = repository / "src/hswm/effect-runtime/src"
    build_config = json.loads(
        (runtime.parent / "tsconfig.dnrd.json").read_text(encoding="utf-8")
    )
    assert build_config["files"] == [
        "src/canonical-atom-v2-routing-diagnostic-process.ts"
    ]
    assert build_config["include"] == []
    assert build_config["compilerOptions"]["plugins"] == []
    seeds = {Path(path).name for path in build_config["files"]}
    discovered: set[str] = set()
    pending = list(seeds)
    pattern = re.compile(r"from\s+['\"](\./[^'\"]+)['\"]")
    while pending:
        name = pending.pop()
        if name in discovered:
            continue
        discovered.add(name)
        body = (runtime / name).read_text(encoding="utf-8")
        for imported in pattern.findall(body):
            target = (runtime / name).parent / imported
            resolved = target.with_suffix(".ts") if target.suffix == ".js" else target
            relative = resolved.resolve().relative_to(runtime.resolve()).as_posix()
            assert relative.endswith(".ts") and (runtime / relative).is_file()
            pending.append(relative)
    frozen = {
        Path(path).name
        for path in CORE_SOURCE_FILES
        if path.startswith("src/hswm/effect-runtime/src/")
    }
    assert discovered == frozen


def test_checked_in_dnrd2_source_manifest_is_canonical_and_exact() -> None:
    """The real Source-A manifest must satisfy the production byte contract."""
    repository = Path(__file__).resolve().parents[1]
    manifest_path = (
        repository
        / "manifests/HSWM_DNRD_2_SOURCE_FREEZE_MANIFEST_2026-08-27.json"
    )
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    assert raw == canonical_json(manifest)
    assert set(manifest) == {
        "schema_version",
        "experiment_id",
        "source_commit_tree_bound_externally",
        "files",
    }
    assert manifest["schema_version"] == "hswm-dnrd-source-freeze-manifest/v1"
    assert manifest["experiment_id"] == "HSWM-DNRD-2"
    assert (
        manifest["source_commit_tree_bound_externally"]
        == "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"
    )
    rows = manifest["files"]
    assert [row["path"] for row in rows] == sorted(CORE_SOURCE_FILES)
    assert {row["path"] for row in rows} == CORE_SOURCE_FILES
    for row in rows:
        assert set(row) == {"path", "sha256"}
        assert _hash(repository / row["path"]) == row["sha256"]


def test_source_manifest_refuses_any_path_outside_the_exact_frozen_closure(
    tmp_path: Path,
) -> None:
    config, _, _ = _fixture(tmp_path)
    extra = config.repo_root / "unrelated-extra.txt"
    extra.write_bytes(b"not a DNRD source input\n")
    source_manifest = config.repo_root / config.source_manifest_path
    value = json.loads(source_manifest.read_text(encoding="utf-8"))
    value["files"].append({"path": "unrelated-extra.txt", "sha256": _hash(extra)})
    value["files"].sort(key=lambda row: row["path"])
    source_manifest_sha256 = _write_json(source_manifest, value)
    config = replace(config, source_manifest_sha256=source_manifest_sha256)

    with pytest.raises(ExecutionRefusal, match="exact DNRD source closure"):
        _load_source_manifest(config)


def test_runtime_tree_refuses_tampered_or_extra_deep_package_file(tmp_path: Path) -> None:
    config, _, _ = _fixture(tmp_path)
    assert config.bridge_runtime_root is not None
    deep = config.bridge_runtime_root / "node_modules/effect/index.js"
    deep.write_text("export const tampered = true;\n", encoding="utf-8")
    with pytest.raises(ExecutionRefusal, match="file hash drifted"):
        _runtime_tree_manifest(config)

    config, _, _ = _fixture(tmp_path / "extra")
    assert config.bridge_runtime_root is not None
    (config.bridge_runtime_root / "node_modules/effect/unlisted.js").write_text("export {};\n", encoding="utf-8")
    with pytest.raises(ExecutionRefusal, match="file closure is not exact"):
        _runtime_tree_manifest(config)


def test_runtime_tree_refuses_omitted_package_file_and_build_input(tmp_path: Path) -> None:
    config, _, _ = _fixture(tmp_path)
    assert config.bridge_runtime_tree_manifest_path is not None
    manifest = json.loads(config.bridge_runtime_tree_manifest_path.read_text(encoding="utf-8"))
    effect = next(
        package for package in manifest["external_packages"]
        if package["name"] == "effect"
    )
    effect["files"] = [
        row for row in effect["files"]
        if row["path"] != "node_modules/effect/index.js"
    ]
    config = _rewrite_runtime_manifest(config, manifest)
    with pytest.raises(ExecutionRefusal, match="entrypoint is absent|file closure is not exact"):
        _runtime_tree_manifest(config)

    config, _, _ = _fixture(tmp_path / "inputs")
    assert config.bridge_runtime_tree_manifest_path is not None
    manifest = json.loads(config.bridge_runtime_tree_manifest_path.read_text(encoding="utf-8"))
    manifest["build_provenance"]["source_inputs"] = manifest["build_provenance"]["source_inputs"][1:]
    config = _rewrite_runtime_manifest(config, manifest)
    with pytest.raises(ExecutionRefusal, match="build inputs"):
        _runtime_tree_manifest(config)


def test_runtime_tree_requires_recursive_declared_package_dependency_rows(tmp_path: Path) -> None:
    config, _, _ = _fixture(tmp_path)
    assert config.bridge_runtime_root is not None
    assert config.bridge_runtime_tree_manifest_path is not None
    package_json = config.bridge_runtime_root / "node_modules/effect/package.json"
    package_json.write_bytes(b'{"dependencies":{"nested":"1"},"name":"effect","version":"fixture"}\n')
    manifest = json.loads(config.bridge_runtime_tree_manifest_path.read_text(encoding="utf-8"))
    package = next(
        row for row in manifest["external_packages"] if row["name"] == "effect"
    )
    package["package_json_sha256"] = _hash(package_json)
    for row in package["files"]:
        if row["path"] == "node_modules/effect/package.json":
            row["sha256"] = _hash(package_json)
    config = _rewrite_runtime_manifest(config, manifest)
    with pytest.raises(ExecutionRefusal, match="dependencies are not recursively pinned"):
        _runtime_tree_manifest(config)

def test_execute_preserves_and_reparses_noncanonical_raw_ci_body(tmp_path: Path) -> None:
    config, dependencies, _ = _fixture(tmp_path, noncanonical_ci_raw=True)
    result = execute_with_dependencies(config, dependencies)
    receipt = json.loads((result.output_dir / "source_ci_receipt.json").read_text())
    assert receipt["raw_response_utf8"].startswith('{ "conclusion"')


def test_external_raw_json_rejects_duplicate_keys_and_nonfinite_constants() -> None:
    assert _json_object_unformatted('{ "id" : 7 }', "fixture") == {"id": 7}
    with pytest.raises(ExecutionRefusal, match="repeats JSON key"):
        _json_object_unformatted('{"id":7,"id":8}', "fixture")
    with pytest.raises(ExecutionRefusal, match="non-finite JSON"):
        _json_object_unformatted('{"id":NaN}', "fixture")


def test_execute_refuses_repeat_marker_and_bad_exact_ratification(tmp_path: Path) -> None:
    config, dependencies, _ = _fixture(tmp_path)
    execute_with_dependencies(config, dependencies)
    second = replace(config, output_root=tmp_path / "output-second")
    with pytest.raises(ExecutionRefusal, match="durable attempt lock"):
        execute_with_dependencies(second, dependencies)
    bad, bad_dependencies, _ = _fixture(tmp_path / "bad")
    with pytest.raises(ExecutionRefusal, match="exact preregistration-bound statement"):
        execute_with_dependencies(
            replace(
                bad,
                ratification_text="arbitrary",
                ratification_text_sha256=hashlib.sha256(b"arbitrary").hexdigest(),
            ),
            bad_dependencies,
        )


def test_attempt_marker_fsyncs_its_registry_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    original_fsync = os.fsync
    fsynced_kinds: list[str] = []

    def recording_fsync(descriptor: int) -> None:
        mode = os.fstat(descriptor).st_mode
        fsynced_kinds.append("directory" if stat.S_ISDIR(mode) else "file")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    _attempt_lock(
        config,
        pulse_receipt_sha256="a" * 64,
        runtime_receipt_sha256="b" * 64,
    )

    assert fsynced_kinds == ["file", "directory"]


def test_live_model_event_ledger_is_fsynced_before_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    output.chmod(0o700)
    ledger = _DurableJsonlEventLedger(output / "model_events.jsonl")
    original_fsync = os.fsync
    fsynced_kinds: list[str] = []

    def recording_fsync(descriptor: int) -> None:
        mode = os.fstat(descriptor).st_mode
        fsynced_kinds.append("directory" if stat.S_ISDIR(mode) else "file")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    ledger({"ordinal": 1, "event": "OBSERVED"})
    ledger({"ordinal": 1, "event": "ACCEPTED"})

    _plain_file(ledger.path, "durable fixture ledger", mode=0o600)
    assert ledger.path.read_bytes() == canonical_json(
        {"ordinal": 1, "event": "OBSERVED"}
    ) + b"\n" + canonical_json({"ordinal": 1, "event": "ACCEPTED"}) + b"\n"
    assert ledger.snapshot() == (
        {"ordinal": 1, "event": "OBSERVED"},
        {"ordinal": 1, "event": "ACCEPTED"},
    )
    assert fsynced_kinds == ["file", "directory", "file"]
