"""Fail-closed teeth for the H3-B3 manifest and two-phase state machine."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import inspect
import json
from types import SimpleNamespace

import pytest

import h3_b3_falsifier as h3
import h3_artifact_lifecycle as lifecycle
from world_ir import canonical_json


def _digest(path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _base_manifest(tmp_path):
    protocol = tmp_path / "protocol.md"
    protocol.write_text("frozen protocol\n", encoding="utf-8")
    preflight = tmp_path / "preflight.json"
    preflight.write_text("{}\n", encoding="utf-8")
    code_sha256 = {
        name: h3._file_sha256(path)
        for name, path in h3.FROZEN_CODE_MODULE_PATHS.items()
    }

    extraction_deployments = {}
    for stage in h3.STAGES:
        path = tmp_path / f"{stage}-extraction-deployment.json"
        path.write_text(f"{stage}\n", encoding="utf-8")
        extraction_deployments[stage] = {
            "path": path.name, "sha256": _digest(path),
        }

    sidecars = {}
    holdouts = {}
    for dataset in h3.DATASETS:
        sidecar = tmp_path / f"{dataset}-sidecar.json"
        sidecar.write_text("{}\n", encoding="utf-8")
        sidecars[dataset] = {
            "path": sidecar.name, "file_sha256": _digest(sidecar),
        }
        holdout = tmp_path / f"{dataset}-fresh-manifest.json"
        holdout.write_text("{}\n", encoding="utf-8")
        holdouts[dataset] = {
            "path": holdout.name,
            "manifest_file_sha256": _digest(holdout),
            "selected_manifest_id": sha256(dataset.encode()).hexdigest(),
        }

    digest = "0" * 64
    stage_artifacts = {}
    for stage in h3.STAGES:
        stage_artifacts[stage] = {
            "segments": {
                dataset: {
                    "path": f"inputs/{dataset}-{stage}.json",
                    "sha256": digest,
                }
                for dataset in h3.DATASETS
            },
            "preimages": {
                "extraction_records": 1,
                "extraction_jsonl_sha256": digest,
                "embedding_records": 2,
                "embedding_jsonl_sha256": digest,
            },
            "output_paths": {
                "extraction_jsonl": f"runs/{stage}/extractions.jsonl",
                "extraction_open_receipt": f"runs/{stage}/extractions.open.json",
                "extraction_close_receipt": f"runs/{stage}/extractions.close.json",
                "embedding_run_directory": f"runs/{stage}/embedding-run",
                "embedding_npz": f"runs/{stage}/embeddings.npz",
                "embedding_receipt": f"runs/{stage}/embeddings.receipt.json",
                "embedding_open_receipt": f"runs/{stage}/embeddings.open.json",
                "embedding_close_receipt": f"runs/{stage}/embeddings.close.json",
            },
            "extraction_deployment_receipt": extraction_deployments[stage],
        }
    stage_artifacts["fresh"].update({
        # This is a future sequential deployment commitment, deliberately
        # path-only at PRE_RUN freeze time.
        "arc_deployment_receipt": {
            "path": "runs/fresh/qwen27-deployment.json",
            "endpoint": "http://127.0.0.1:18000/v1",
            "model": h3.arca.FROZEN_MODEL,
            "model_revision": h3.arca.FROZEN_MODEL_REVISION,
        },
        "arc_paths": {
            dataset: {
                "packet": f"runs/fresh/{dataset}.arc-packet.json",
                "packet_seal": f"runs/fresh/{dataset}.arc-packet-seal.json",
                "ledger": f"runs/fresh/{dataset}.arc-ledger.jsonl",
                "adjudication": f"runs/fresh/{dataset}.arc-adjudication.json",
                "adjudication_close": f"runs/fresh/{dataset}.arc-close.json",
            }
            for dataset in h3.DATASETS
        },
    })

    arc_config = h3.arca.ArcAdjudicatorConfigV1(
        endpoint="http://127.0.0.1:18000/v1",
        deployment_attestation_sha256=digest,
    )
    arc_commitment = asdict(arc_config)
    arc_commitment.pop("deployment_attestation_sha256")
    manifest = {
        "schema_version": h3.MANIFEST_SCHEMA_VERSION,
        "status_at_freeze": "PRE_RUN_FROZEN",
        "protocol": {"path": protocol.name, "sha256": _digest(protocol)},
        "code_sha256": code_sha256,
        "preflight": {
            "path": preflight.name,
            "sha256": _digest(preflight),
            "receipt_id": "fixture-preflight",
        },
        "evaluation_config": h3.FROZEN_EVALUATION_CONFIG,
        "extractor": {
            "model": "qwen3.6-35b-a3b",
            "model_revision": "fixture-revision",
            "prompt_sha256": "1" * 64,
            "config_sha256": "2" * 64,
            "batch_size": 1,
        },
        # Semantic validation is stubbed below; root shape remains exact.
        "embedding": {"fixture": True},
        "stage_artifacts": stage_artifacts,
        "development_sidecars": sidecars,
        "fresh_holdout": holdouts,
        "phase_paths": {
            "development_report": "runs/development-report.json",
            "certificate_transition": "runs/certificate-transition.json",
            "fresh_artifact_seal": "runs/fresh-artifact-seal.json",
            "final_report": "runs/final-report.json",
        },
        "arc_adjudicator": {
            "endpoint": arc_config.endpoint,
            "model": arc_config.model,
            "model_revision": arc_config.model_revision,
            "max_concurrency": arc_config.max_concurrency,
            "timeout_seconds": arc_config.timeout_seconds,
            "max_tokens": arc_config.max_tokens,
            "config_sha256": sha256(
                canonical_json(arc_commitment).encode("utf-8")
            ).hexdigest(),
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, manifest


def _stub_manifest_semantics(monkeypatch, manifest):
    modules = tuple(
        SimpleNamespace(path=path, sha256=value)
        for path, value in manifest["code_sha256"].items()
    )
    monkeypatch.setattr(
        h3.preflight, "load_preflight_receipt",
        lambda _path: SimpleNamespace(
            receipt_id="fixture-preflight",
            implementation_modules=modules,
            implementation_code_root_sha256=lifecycle.authorization_code_root(
                manifest["code_sha256"]
            ),
        ),
    )
    monkeypatch.setattr(
        h3, "_validate_embedding_manifest", lambda _path, value: value,
    )
    monkeypatch.setattr(
        h3, "_validate_deployment_attestation",
        lambda *_args, **_kwargs: {},
    )


def test_manifest_exactly_binds_imported_code_and_rejects_spoofs(
    tmp_path, monkeypatch,
):
    manifest_path, manifest = _base_manifest(tmp_path)
    _stub_manifest_semantics(monkeypatch, manifest)
    assert h3.load_run_manifest(manifest_path)["code_sha256"] == (
        manifest["code_sha256"]
    )
    assert not (tmp_path / "runs/fresh/qwen27-deployment.json").exists()

    original = dict(manifest["code_sha256"])
    for replacement in (
        {key: value for key, value in original.items()
         if key != "h3_arc_adjudicator.py"},
        {**original, "unknown.py": "0" * 64},
        {
            **{key: value for key, value in original.items()
               if key != "h3_b3_falsifier.py"},
            "subdir/h3_b3_falsifier.py": original["h3_b3_falsifier.py"],
        },
    ):
        manifest["code_sha256"] = replacement
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(
            h3.ArtifactIntegrityError, match="exactly bind imported modules",
        ):
            h3.load_run_manifest(manifest_path)

    manifest["code_sha256"] = original
    manifest["unexpected"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(h3.ArtifactIntegrityError, match="keys must be exactly"):
        h3.load_run_manifest(manifest_path)


def test_confirmatory_evaluation_config_is_exactly_frozen(tmp_path, monkeypatch):
    manifest_path, manifest = _base_manifest(tmp_path)
    _stub_manifest_semantics(monkeypatch, manifest)
    assert h3.load_run_manifest(manifest_path)["evaluation_config"] == (
        h3.FROZEN_EVALUATION_CONFIG
    )
    manifest["evaluation_config"] = {
        **h3.FROZEN_EVALUATION_CONFIG, "n_signflips": 100,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(h3.ArtifactIntegrityError, match="preregistration"):
        h3.load_run_manifest(manifest_path)
    with pytest.raises(h3.ArtifactIntegrityError, match="preregistration"):
        h3._require_frozen_evaluation_config(
            h3._evaluation_config_receipt(
                h3.EvaluationConfigV1(split_seed=999),
            )
        )


def test_transition_rejoins_exact_development_policy_and_certificate(
    tmp_path, monkeypatch,
):
    manifest_path, manifest = _base_manifest(tmp_path)
    _stub_manifest_semantics(monkeypatch, manifest)
    artifact_receipt = {"status": "OPENED_CLOSED_AND_DOMAIN_VERIFIED"}
    dataset_reports = []
    for dataset in h3.DATASETS:
        selection = {
            "chosen_policy": asdict(h3.POLICY_GRID[0]),
            "strongest_static": "cosine",
        }
        dataset_reports.append({
            "dataset": dataset,
            "certificate_admitted": True,
            "selection": selection,
            "certificate": {"dataset": dataset, "pass": True},
        })
    development_report = {
        "schema_version": h3.DEVELOPMENT_REPORT_SCHEMA_VERSION,
        "status": "BOTH_CERTIFICATES_PASS",
        "run_manifest_sha256": _digest(manifest_path),
        "evaluation_config": h3.FROZEN_EVALUATION_CONFIG,
        "artifact_receipt": artifact_receipt,
        "datasets": dataset_reports,
        "fresh_status": "NOT_OPENED",
    }
    development_path = tmp_path / manifest["phase_paths"]["development_report"]
    h3._write_json_once(development_path, development_report)
    transition = h3._create_certificate_transition(
        manifest_path=manifest_path,
        manifest=manifest,
        development_report_path=development_path,
        development_artifact_receipt=artifact_receipt,
        dataset_reports=dataset_reports,
    )
    assert transition["certificates"]["musique"]["selected_policy"] == (
        dataset_reports[0]["selection"]["chosen_policy"]
    )

    transition_path = tmp_path / manifest["phase_paths"]["certificate_transition"]
    forged = json.loads(transition_path.read_text(encoding="utf-8"))
    forged["certificates"]["musique"]["selected_policy"]["mu"] = 0.9
    forged["transition_id"] = h3._phase_receipt_id(
        "hswm:h3_b3_certificate_transition:v1:", forged, "transition_id",
    )
    transition_path.write_text(
        canonical_json(forged) + "\n", encoding="utf-8",
    )
    with pytest.raises(
        h3.ArtifactIntegrityError, match="development report mismatch",
    ):
        h3.load_certificate_transition(
            transition_path, manifest_path=manifest_path,
        )


def test_failed_development_certificate_never_loads_fresh_stage(
    tmp_path, monkeypatch,
):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    manifest = {
        "evaluation_config": h3.FROZEN_EVALUATION_CONFIG,
        "development_sidecars": {
            dataset: {"path": f"{dataset}.json", "file_sha256": "0" * 64}
            for dataset in h3.DATASETS
        },
        "phase_paths": {
            "development_report": "development-report.json",
            "certificate_transition": "transition.json",
        },
    }
    calls = []
    worlds = {
        f"{dataset}_development": SimpleNamespace(
            dataset=dataset,
        )
        for dataset in h3.DATASETS
    }

    monkeypatch.setattr(h3, "load_run_manifest", lambda _path: manifest)

    def stage_loader(stage, **_kwargs):
        calls.append(stage)
        if stage != "development":
            raise AssertionError("fresh stage must remain unopened")
        return worlds, SimpleNamespace(), SimpleNamespace(), {"stage": stage}

    monkeypatch.setattr(h3, "_load_stage_artifacts", stage_loader)
    monkeypatch.setattr(h3, "compile_segment", lambda segment, *_args: segment)
    monkeypatch.setattr(
        h3, "development_assignments",
        lambda *_args, **_kwargs: ((0,), (1,), ("c0", "c1"), {}),
    )
    monkeypatch.setattr(
        h3, "select_policy",
        lambda *_args: (
            h3.POLICY_GRID[0], "cosine",
            {
                "chosen_policy": asdict(h3.POLICY_GRID[0]),
                "strongest_static": "cosine",
            },
        ),
    )

    def certificate(world, *_args, **_kwargs):
        admitted = world.dataset == "musique"
        metric = {"passes_threshold_and_ci": admitted}
        return {
            "comparisons": {
                "vs_matched_b3_k1": {"ndcg10": metric, "asr10": metric},
            },
            "safety_gate": {"pass": True},
        }

    monkeypatch.setattr(h3, "evaluate_fixed_policy", certificate)
    monkeypatch.setattr(h3, "_segment_accounting", lambda *_args: {})
    report = h3.run_development_phase(manifest_path=manifest_path)
    assert calls == ["development"]
    assert report["status"] == "CERTIFICATE_REFUSED"
    assert report["certificate_transition"] is None
    assert not (tmp_path / "transition.json").exists()


def test_runner_and_cli_accept_only_manifest_authorized_phase(
    tmp_path, monkeypatch,
):
    parameters = set(inspect.signature(h3.run_falsifier).parameters)
    assert parameters == {"manifest_path", "phase", "config", "arc_transport"}
    captured = {}

    def runner(**kwargs):
        captured.update(kwargs)
        return {"status": "CERTIFICATE_REFUSED", "datasets": []}

    monkeypatch.setattr(h3, "run_falsifier", runner)
    monkeypatch.setattr(
        h3, "load_run_manifest",
        lambda _path: {
            "phase_paths": {"development_report": "development-report.json"},
        },
    )
    assert h3.main([
        "--phase", "development", "--manifest", str(tmp_path / "manifest.json"),
    ]) == 0
    assert captured == {
        "manifest_path": str(tmp_path / "manifest.json"),
        "phase": "development",
    }
    with pytest.raises(SystemExit):
        h3.main([
            "--phase", "fresh", "--manifest", "manifest.json",
            "--arc-adjudication", "musique=attacker.json",
        ])
