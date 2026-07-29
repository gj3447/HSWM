#!/usr/bin/env python3
"""Build a gold-blind, self-hashed execution lock for the r8 development pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.hswm_result_spool import load_model_deployment_binding
from prom_search_hswm.prom9_f1_prior_exposure import (
    _read_private_bytes,
    _strict_object,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    R8_DEPENDENCY_NAMES,
    load_private_receipt,
    r8_dependency_paths,
    r8_environment_labels,
    verify_r8_preimage_bundle,
)
from prom_search_hswm.prom9_f1_r8_power import (
    _load_judge_core,
    replay_selection_receipt,
    selected_entries,
)
from prom_search_hswm.prom9_f1_r8_runner import build_development_execution_lock
from prom_search_hswm.prom9_f1_r8_source import (
    build_public_artifacts,
    candidate_universe_sha256,
    verify_evaluator_seal,
    verify_public_source_receipt,
)


REQUIRED_DEPENDENCY_FILES = R8_DEPENDENCY_NAMES
REQUIRED_ENVIRONMENT_LABELS = (
    "spool_endpoint", "model_upstream_endpoint",
    "model_deployment_receipt_sha256", "model", "model_revision", "run_id",
    "hswm_commit", "symposium_commit",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class LockRefusal(RuntimeError):
    """A public pre-call artifact or frozen dependency graph drifted."""


def _read(path: Path, label: str) -> dict[str, object]:
    return _strict_object(_read_private_bytes(path), label)


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise LockRefusal(f"{label} self-hash drifted")
    return declared


def _stable_file_sha256(path: Path, label: str) -> str:
    target = Path(path)
    try:
        before = target.lstat()
    except OSError as error:
        raise LockRefusal(f"{label} is unavailable") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise LockRefusal(f"{label} must be a regular non-symlink file")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    after = target.lstat()
    if (
        before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
    ) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise LockRefusal(f"{label} changed while hashing")
    return digest


def _validate_artifact_graph(
    *,
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
    selection_sha: str,
    public_source: Mapping[str, object],
    evaluator: Mapping[str, object],
) -> tuple[str, str, str, str, str]:
    source_sha = verify_public_source_receipt(public_source)
    evaluator_sha = verify_evaluator_seal(evaluator)
    run_id = manifest.get("run_id")
    raw_items = manifest.get("items")
    development = selection.get("development")
    source_rows = public_source.get("rows")
    if (
        not isinstance(run_id, str)
        or not run_id
        or manifest.get("mode") != "development"
        or manifest.get("preregistration_artifact_sha256") is not None
        or not isinstance(raw_items, list)
        or not isinstance(development, Mapping)
        or not isinstance(source_rows, list)
    ):
        raise LockRefusal("development public artifact arrays or mode drifted")

    public_rows = selected_entries(selection, "development")
    rebuilt = build_public_artifacts(
        public_rows,
        public_selection_receipt_sha256=selection_sha,
        dataset=str(public_source.get("dataset")),
        config=str(public_source.get("config")),
        split=str(public_source.get("split")),
        run_id=run_id,
        mode="development",
        model=str(manifest.get("model")),
        model_revision=str(manifest.get("model_revision")),
        token_envelope=manifest.get("token_envelope", {}),
        preregistration_artifact_sha256=None,
    )
    if rebuilt["manifest"] != dict(manifest) or rebuilt["source_receipt"] != dict(
        public_source
    ):
        raise LockRefusal("public selection does not reproduce manifest/source")

    manifest_by_id: dict[str, Mapping[str, object]] = {}
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise LockRefusal("development manifest item is malformed")
        item_id = raw.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in manifest_by_id:
            raise LockRefusal("development manifest item IDs repeat")
        manifest_by_id[item_id] = raw
    selected_ids = development.get("item_ids")
    if (
        not isinstance(selected_ids, list)
        or len(set(selected_ids)) != len(selected_ids)
        or set(selected_ids) != set(manifest_by_id)
        or public_source.get("public_selection_receipt_sha256") != selection_sha
        or public_source.get("redacted_rows") != public_rows
    ):
        raise LockRefusal("selection/source/manifest identities differ")

    source_by_id: dict[str, Mapping[str, object]] = {}
    for raw in source_rows:
        if not isinstance(raw, Mapping):
            raise LockRefusal("public source row is malformed")
        item_id = raw.get("item_id")
        if not isinstance(item_id, str) or item_id in source_by_id:
            raise LockRefusal("public source item IDs repeat")
        source_by_id[item_id] = raw
    if set(source_by_id) != set(manifest_by_id):
        raise LockRefusal("public source and manifest identities differ")

    expected_components: dict[str, dict[str, set[str]]] = {}
    for item_id, item in manifest_by_id.items():
        candidates = item.get("candidates")
        component_id = item.get("component_id")
        if (
            not isinstance(candidates, list)
            or not candidates
            or any(not isinstance(candidate, Mapping) for candidate in candidates)
            or not isinstance(component_id, str)
        ):
            raise LockRefusal("development manifest provenance is malformed")
        entities = sorted({str(candidate.get("source_entity_id")) for candidate in candidates})
        row = source_by_id[item_id]
        if (
            row.get("source_entity_ids") != entities
            or row.get("candidate_universe_sha256")
            != candidate_universe_sha256(candidates)
        ):
            raise LockRefusal("public source differs from manifest provenance")
        component = expected_components.setdefault(
            component_id, {"item_ids": set(), "source_entity_ids": set()}
        )
        component["item_ids"].add(item_id)
        component["source_entity_ids"].update(entities)

    schedule = development.get("component_schedule")
    if not isinstance(schedule, list) or len(schedule) != len(expected_components):
        raise LockRefusal("development component schedule differs from manifest")
    seen_components: set[str] = set()
    for raw in schedule:
        if not isinstance(raw, Mapping):
            raise LockRefusal("development component schedule is malformed")
        component_id = str(raw.get("component_id"))
        expected = expected_components.get(component_id)
        if expected is None or component_id in seen_components:
            raise LockRefusal("development component identity repeats or drifted")
        seen_components.add(component_id)
        if (
            set(raw.get("item_ids", [])) != expected["item_ids"]
            or set(raw.get("source_entity_ids", [])) != expected["source_entity_ids"]
            or raw.get("cluster_size") != len(expected["item_ids"])
        ):
            raise LockRefusal("development component preimage differs from manifest")

    cohort_root = canonical_sha256(sorted(manifest_by_id))
    gold_sha = evaluator.get("gold_sha256")
    gold_source_sha = evaluator.get("gold_source_receipt_sha256")
    if (
        evaluator.get("run_id") != run_id
        or evaluator.get("cohort_root_sha256") != cohort_root
        or evaluator.get("raw_source_sha256") != public_source.get("raw_source_sha256")
        or evaluator.get("public_selection_receipt_sha256") != selection_sha
        or evaluator.get("public_source_receipt_sha256") != source_sha
        or not isinstance(gold_sha, str)
        or _SHA256.fullmatch(gold_sha) is None
        or not isinstance(gold_source_sha, str)
        or _SHA256.fullmatch(gold_source_sha) is None
        or evaluator.get("answers_inspected_by_operator") is not False
    ):
        raise LockRefusal("evaluator/public artifact binding drifted")
    return run_id, source_sha, evaluator_sha, gold_source_sha, gold_sha


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--evaluator-receipt", type=Path, required=True)
    parser.add_argument("--db-genesis-receipt", type=Path, required=True)
    parser.add_argument("--environment-dependency-bundle", type=Path, required=True)
    parser.add_argument("--prior-exposure-receipt", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--judge-core", type=Path, required=True)
    parser.add_argument("--result-contract", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--model-catalog", type=Path, required=True)
    parser.add_argument(
        "--model-deployment-receipt",
        dest="model_weight_receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--python-lock", type=Path, required=True)
    parser.add_argument("--symposium-repo-root", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--upstream-endpoint", required=True)
    parser.add_argument("--max-workers", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--max-delivery-attempts", type=int, required=True)
    parser.add_argument("--spool-token-env", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = _read(args.manifest, "development manifest")
        selection = _read(args.selection_receipt, "public cohort selection receipt")
        public_source = _read(args.source_receipt, "public source receipt")
        evaluator = _read(args.evaluator_receipt, "evaluator seal")
        genesis = _read(args.db_genesis_receipt, "DB genesis receipt")
        prior = _read(args.prior_exposure_receipt, "prior-exposure receipt")
        bundle = load_private_receipt(
            args.environment_dependency_bundle, verify_live=True
        )

        prior_sha = verify_prior_exposure_receipt(prior)
        selection_sha = replay_selection_receipt(selection, prior_receipt=prior)
        if selection.get("prior_exposure_receipt_sha256") != prior_sha:
            raise LockRefusal("selection is not bound to prior exposure")
        run_id, source_sha, evaluator_sha, gold_source_sha, gold_sha = (
            _validate_artifact_graph(
                manifest=manifest,
                selection=selection,
                selection_sha=selection_sha,
                public_source=public_source,
                evaluator=evaluator,
            )
        )
        genesis_sha = _self_hash(genesis, "genesis_sha256", "DB genesis receipt")
        if (
            genesis.get("run_id") != run_id
            or genesis.get("schema_version")
            != "hswm-prom9-f1-r8-transport-genesis/v1"
        ):
            raise LockRefusal("DB genesis identity drifted")

        environment = bundle.get("environment_receipt")
        dependencies = bundle.get("dependency_receipt")
        if not isinstance(environment, Mapping) or not isinstance(dependencies, Mapping):
            raise LockRefusal("environment/dependency bundle entries are absent")
        labels = environment.get("labels")
        if not isinstance(labels, Mapping):
            raise LockRefusal("environment labels are absent")
        hswm_commit = labels.get("hswm_commit")
        symposium_commit = labels.get("symposium_commit")
        model = manifest.get("model")
        model_revision = manifest.get("model_revision")
        if (
            not isinstance(hswm_commit, str)
            or _COMMIT.fullmatch(hswm_commit) is None
            or not isinstance(symposium_commit, str)
            or _COMMIT.fullmatch(symposium_commit) is None
            or not isinstance(model, str)
            or not isinstance(model_revision, str)
        ):
            raise LockRefusal("runtime identity is malformed")
        deployment_binding = load_model_deployment_binding(
            args.model_weight_receipt,
            upstream_endpoint=args.upstream_endpoint,
            served_model=model,
            model_revision=model_revision,
            verify_live_process=True,
        )

        expected_paths = r8_dependency_paths(
            protocol_path=args.protocol,
            judge_core_path=args.judge_core,
            result_contract_path=args.result_contract,
            tokenizer_dir=args.tokenizer_dir,
            model_catalog_path=args.model_catalog,
            model_weight_receipt_path=args.model_weight_receipt,
            python_lock_path=args.python_lock,
        )
        expected_labels = r8_environment_labels(
            spool_endpoint=args.endpoint,
            model_upstream_endpoint=deployment_binding.upstream_endpoint,
            model_deployment_receipt_sha256=(
                deployment_binding.deployment_receipt_sha256
            ),
            model=model,
            model_revision=model_revision,
            run_id=run_id,
            hswm_commit=hswm_commit,
            symposium_commit=symposium_commit,
        )
        verified_bundle = verify_r8_preimage_bundle(
            bundle,
            expected_paths=expected_paths,
            expected_labels=expected_labels,
            repo_root=Path(__file__).resolve().parents[1],
            symposium_repo_root=args.symposium_repo_root,
            verify_live=True,
        )
        environment_sha = verified_bundle["environment_receipt_sha256"]
        dependency_sha = verified_bundle["dependency_receipt_sha256"]
        compatibility_root = verified_bundle["compatibility_root_sha256"]
        bundle_sha = verified_bundle["bundle_sha256"]

        judge_core_file_sha = _stable_file_sha256(args.judge_core, "judge core")
        result_contract_sha = _stable_file_sha256(
            args.result_contract, "result contract"
        )
        judge = _load_judge_core(args.judge_core)
        judge_core_sha = str(judge.judge_core_sha256(args.judge_core))
        if _stable_file_sha256(args.judge_core, "judge core") != judge_core_file_sha:
            raise LockRefusal("judge core changed while freezing the execution lock")

        aggregate = prior.get("aggregate")
        if not isinstance(aggregate, Mapping):
            raise LockRefusal("prior exposure aggregate is absent")
        lock = build_development_execution_lock(
            manifest,
            protocol_path=args.protocol,
            selection_receipt_sha256=selection_sha,
            prior_exposure_receipt_sha256=prior_sha,
            public_source_receipt_sha256=source_sha,
            gold_source_receipt_sha256=gold_source_sha,
            gold_sha256=gold_sha,
            evaluator_receipt_sha256=evaluator_sha,
            db_genesis_receipt_sha256=genesis_sha,
            environment_receipt_sha256=environment_sha,
            dependency_receipt_sha256=dependency_sha,
            environment_dependency_compatibility_root_sha256=compatibility_root,
            environment_dependency_bundle_sha256=bundle_sha,
            hswm_commit=hswm_commit,
            result_contract_sha256=result_contract_sha,
            judge_core_sha256=judge_core_sha,
            judge_core_file_sha256=judge_core_file_sha,
            deployment_binding=deployment_binding,
            forbidden_prior_item_ids=sorted(aggregate.get("prior_item_ids", [])),
            forbidden_prior_source_entity_ids=sorted(
                aggregate.get("prior_source_entity_ids", [])
            ),
            forbidden_prior_component_ids=sorted(
                aggregate.get("prior_component_ids", [])
            ),
            execution_policy={
                "endpoint": args.endpoint,
                "max_workers": args.max_workers,
                "timeout_seconds": args.timeout_seconds,
                "max_delivery_attempts": args.max_delivery_attempts,
                "spool_token_env": args.spool_token_env,
            },
        )
        write_private_once(args.output, lock)
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "DEVELOPMENT_EXECUTION_LOCK_FROZEN",
                "run_id": lock["run_id"],
                "lock_sha256": lock["lock_sha256"],
                "expected_items": lock["gates"]["expected_items"],
                "expected_calls": lock["gates"]["expected_calls"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LockRefusal",
    "REQUIRED_DEPENDENCY_FILES",
    "REQUIRED_ENVIRONMENT_LABELS",
    "main",
]
