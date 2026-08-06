#!/usr/bin/env python3
"""Build the gold-blind execution lock for the r8 c801 development run.

Generation-bound fork of ``prom9_f1_r8_lock`` for the C-recontract cohorts:
the selection input is the ~240 MB cohort-selection/v6 receipt (dedicated
large stable-read ceiling), replay goes through
``replay_selection_receipt_v6`` (which also verifies and lifts the pinned
predecessor selection), the run identity is the ratified
``f1-2wiki-development-r8-c801``, and the token-envelope derivation is
verified by full deterministic REBUILD via
``build_token_envelope_artifacts_v6`` instead of the v4 verify path.  The
artifact-graph validation and the lock construction itself are the untouched
v4 machinery.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.hswm_token_meter import QwenBpeMeter
from prom_search_hswm.hswm_result_spool import load_model_deployment_binding
from prom_search_hswm.prom9_f1_prior_exposure import (
    _read_private_bytes,
    _strict_object,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_c801_exposure import (
    C800_RUN_ID,
    C801_DEVELOPMENT_RUN_ID,
    merge_c801_exposure_boundaries,
    verify_f1_r8_successor_exposure_set_v2,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    load_private_receipt,
    r8_c801_dependency_paths,
    r8_environment_labels,
    verify_r8_c801_preimage_bundle,
)
from prom_search_hswm.prom9_f1_r8_envelope_v6 import (
    _read_bound_selection_json,
    build_token_envelope_artifacts_v6,
)
from prom_search_hswm.prom9_f1_r8_power import (
    _selected_entries_unverified,
)
from prom_search_hswm.prom9_f1_r8_runner import (
    EXECUTION_LOCK_SCHEMA,
    build_development_execution_lock,
    capture_judge_hashes,
    read_stable_bytes,
    read_stable_json,
)
from prom_search_hswm.prom9_f1_r8_selection_v6 import (
    SELECTION_SCHEMA_V6,
    replay_selection_receipt_v6,
)
from prom_search_hswm.prom9_f1_r8_source import (
    build_public_artifacts,
    candidate_universe_sha256,
    verify_evaluator_seal,
    verify_public_source_receipt,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class LockRefusal(RuntimeError):
    """A public pre-call artifact or frozen dependency graph drifted."""


def _read(path: Path, label: str) -> dict[str, object]:
    return _strict_object(_read_private_bytes(path), label)


def _read_with_sha(path: Path, label: str) -> tuple[dict[str, object], str]:
    try:
        return read_stable_json(path, label)
    except Exception as error:
        raise LockRefusal(f"cannot capture stable {label}") from error


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise LockRefusal(f"{label} self-hash drifted")
    return declared


def _stable_file_sha256(path: Path, label: str) -> str:
    try:
        _raw, digest = read_stable_bytes(path, label)
    except Exception as error:
        raise LockRefusal(f"cannot capture stable {label}") from error
    return digest


def _predecessor_execution_lock_authority(
    path: Path, successor_v2: Mapping[str, object]
) -> dict[str, object]:
    try:
        raw, raw_sha = read_stable_bytes(path, "c800 predecessor execution lock")
        value = _strict_object(raw, "c800 predecessor execution lock")
    except Exception as error:
        raise LockRefusal("cannot capture c800 predecessor execution lock") from error
    lock_sha = _self_hash(
        value, "lock_sha256", "c800 predecessor execution lock"
    )
    if (
        value.get("schema_version") != EXECUTION_LOCK_SCHEMA
        or value.get("purpose") != "DEVELOPMENT_POWER_PILOT"
        or value.get("mode") != "development"
        or value.get("run_id") != C800_RUN_ID
        or value.get("preregistration_artifact_sha256") is not None
    ):
        raise LockRefusal("c800 predecessor execution-lock authority drifted")
    incident = successor_v2.get("c800_incident")
    artifacts = (
        incident.get("artifact_bindings") if isinstance(incident, Mapping) else None
    )
    binding = (
        artifacts.get("execution_lock") if isinstance(artifacts, Mapping) else None
    )
    declared = (
        binding.get("declared_hashes") if isinstance(binding, Mapping) else None
    )
    if (
        not isinstance(binding, Mapping)
        or not isinstance(declared, Mapping)
        or binding.get("schema_version") != EXECUTION_LOCK_SCHEMA
        or binding.get("size_bytes") != len(raw)
        or binding.get("raw_sha256") != raw_sha
        or binding.get("canonical_sha256") != canonical_sha256(value)
        or declared.get("lock_sha256") != lock_sha
    ):
        raise LockRefusal(
            "c800 predecessor execution lock differs from quarantined authority"
        )
    return value


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

    # The v4 accessor re-verifies the v3/v4 selection schemas and refuses v6;
    # the caller has already fully replayed the v6 receipt, so read the
    # development block with the unverified accessor.
    public_rows = _selected_entries_unverified(development)
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
    parser.add_argument("--predecessor-selection-receipt", type=Path, required=True)
    parser.add_argument("--predecessor-execution-lock", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--evaluator-receipt", type=Path, required=True)
    parser.add_argument("--db-genesis-receipt", type=Path, required=True)
    parser.add_argument("--environment-dependency-bundle", type=Path, required=True)
    parser.add_argument(
        "--token-envelope-derivation-receipt", type=Path, required=True
    )
    parser.add_argument("--historical-manifest", type=Path, required=True)
    parser.add_argument("--token-meter-validation-receipt", type=Path, required=True)
    parser.add_argument("--projected-outputs-receipt", type=Path, required=True)
    parser.add_argument("--token-meter-source-suite", type=Path, required=True)
    parser.add_argument("--prior-exposure-receipt", type=Path, required=True)
    parser.add_argument(
        "--aborted-attempt-exposure-receipt", type=Path, required=True
    )
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--judge-core", type=Path, required=True)
    parser.add_argument("--result-contract", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--model-catalog", type=Path, required=True)
    parser.add_argument(
        "--model-weight-receipt", type=Path, required=True
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
        selection, _selection_file_sha = _read_bound_selection_json(
            args.selection_receipt, "v6 cohort selection receipt"
        )
        predecessor, _predecessor_file_sha = _read_bound_selection_json(
            args.predecessor_selection_receipt, "predecessor selection receipt"
        )
        public_source = _read(args.source_receipt, "public source receipt")
        evaluator = _read(args.evaluator_receipt, "evaluator seal")
        genesis = _read(args.db_genesis_receipt, "DB genesis receipt")
        prior = _read(args.prior_exposure_receipt, "prior-exposure receipt")
        aborted_exposure, _aborted_exposure_file_sha = _read_with_sha(
            args.aborted_attempt_exposure_receipt,
            "aborted-attempt exposure receipt",
        )
        derivation_receipt, _derivation_file_sha = _read_with_sha(
            args.token_envelope_derivation_receipt,
            "token-envelope derivation receipt",
        )
        historical, _historical_file_sha = _read_with_sha(
            args.historical_manifest, "historical manifest"
        )
        validation, _validation_file_sha = _read_with_sha(
            args.token_meter_validation_receipt,
            "token-meter validation receipt",
        )
        projected, _projected_file_sha = _read_with_sha(
            args.projected_outputs_receipt, "projected-output receipt"
        )
        source_suite, _source_suite_file_sha = _read_with_sha(
            args.token_meter_source_suite, "token-meter source suite"
        )
        protocol, _protocol_file_sha = _read_with_sha(
            args.protocol, "PROM-9 protocol"
        )
        bundle = load_private_receipt(
            args.environment_dependency_bundle, verify_live=True
        )

        prior_sha = verify_prior_exposure_receipt(prior)
        if (
            selection.get("schema_version") != SELECTION_SCHEMA_V6
            or manifest.get("run_id") != C801_DEVELOPMENT_RUN_ID
        ):
            raise LockRefusal(
                "c801 development lock requires the v6 selection and the "
                "ratified c801 run identity"
            )
        aborted_exposure_sha = verify_f1_r8_successor_exposure_set_v2(
            aborted_exposure
        )
        predecessor_lock = _predecessor_execution_lock_authority(
            args.predecessor_execution_lock, aborted_exposure
        )
        exposure_boundary = merge_c801_exposure_boundaries(
            prior, aborted_exposure
        )
        selection_sha = replay_selection_receipt_v6(
            selection,
            prior_receipt=prior,
            successor_exposure_set=aborted_exposure,
            predecessor_selection=predecessor,
        )
        if (
            selection.get("prior_exposure_receipt_sha256") != prior_sha
            or selection.get("aborted_attempt_exposure_receipt_sha256")
            != aborted_exposure_sha
        ):
            raise LockRefusal("selection is not bound to the exposure boundary")
        derivation_sha = _self_hash(
            derivation_receipt,
            "receipt_sha256",
            "token-envelope derivation receipt",
        )
        meter = QwenBpeMeter(
            args.tokenizer_dir / "vocab.json",
            args.tokenizer_dir / "merges.txt",
            args.tokenizer_dir / "tokenizer_config.json",
        )
        # Deterministic full rebuild replaces the v4 verify path: the c801
        # derivation must reproduce byte-identically from the same inputs,
        # and the manifest must embed exactly the rebuilt envelope.
        rebuilt_envelope = build_token_envelope_artifacts_v6(
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            source_suite=source_suite,
            meter=meter,
            protocol_path=args.protocol,
            model=str(manifest.get("model")),
            model_revision=str(manifest.get("model_revision")),
        )
        if (
            rebuilt_envelope["derivation_receipt"] != dict(derivation_receipt)
            or manifest.get("token_envelope")
            != rebuilt_envelope["token_envelope"]
        ):
            raise LockRefusal("token-envelope derivation replay drifted")
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

        expected_paths = r8_c801_dependency_paths(
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
        verified_bundle = verify_r8_c801_preimage_bundle(
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

        judge_core_file_sha, judge_core_sha = capture_judge_hashes(
            args.judge_core,
            "judge core",
        )
        if (
            judge_core_sha != predecessor_lock.get("judge_core_sha256")
            or judge_core_file_sha
            != predecessor_lock.get("judge_core_file_sha256")
        ):
            raise LockRefusal("judge authority differs from c800 predecessor lock")
        result_contract_sha = _stable_file_sha256(
            args.result_contract, "result contract"
        )

        lock = build_development_execution_lock(
            manifest,
            protocol_path=args.protocol,
            protocol=protocol,
            selection_receipt_sha256=selection_sha,
            prior_exposure_receipt_sha256=prior_sha,
            aborted_attempt_exposure_receipt_sha256=aborted_exposure_sha,
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
            token_envelope_derivation_receipt_sha256=derivation_sha,
            deployment_binding=deployment_binding,
            forbidden_prior_item_ids=exposure_boundary["item_ids"],
            forbidden_prior_source_entity_ids=exposure_boundary[
                "source_entity_ids"
            ],
            forbidden_prior_component_ids=exposure_boundary["component_ids"],
            execution_policy={
                "endpoint": args.endpoint,
                "max_workers": args.max_workers,
                "timeout_seconds": args.timeout_seconds,
                "max_delivery_attempts": args.max_delivery_attempts,
                "spool_token_env": args.spool_token_env,
            },
        )
        write_private_once(args.output, lock)
    except Exception as error:
        print(
            json.dumps(
                {"status": "REFUSED", "reason": str(error)}, sort_keys=True
            ),
            file=sys.stderr,
        )
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
