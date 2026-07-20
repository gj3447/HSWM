"""Fixture teeth for deterministic, first-write H3 PRE_RUN manifests."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import bge_m3_embed as bge
import h3_b3_falsifier as h3
import h3_b3_manifest as manifest
import h3_b3_prepare as prep
import h3_fresh_manifest as fresh
from world_ir import canonical_json


def _write_canonical(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _snapshot(tmp_path: Path) -> Path:
    repository = tmp_path / (
        "models--" + bge.FROZEN_MODEL_ID.replace("/", "--")
    )
    snapshot = repository / "snapshots" / bge.FROZEN_MODEL_REVISION
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text(json.dumps({
        "_name_or_path": bge.FROZEN_MODEL_ID,
        "model_type": "xlm-roberta",
        "architectures": ["XLMRobertaModel"],
        "torch_dtype": "bfloat16",
    }), encoding="utf-8")
    (snapshot / "tokenizer_config.json").write_text(json.dumps({
        "name_or_path": bge.FROZEN_MODEL_ID,
        "tokenizer_class": "XLMRobertaTokenizerFast",
        "model_max_length": 8192,
    }), encoding="utf-8")
    (snapshot / "tokenizer.json").write_text("{}", encoding="utf-8")
    (snapshot / "model.safetensors").write_bytes(b"fixture-weights")
    return snapshot


def _segment(dataset: str, stage: str) -> prep.PreparedSegmentV1:
    title = f"{dataset}-{stage}-title"
    text = f"{dataset} {stage} Alpha was related to Beta."
    source_id = prep.paragraph_source_id(dataset, title, text)
    paragraph = fresh.CompilerParagraphV1(source_id, title, text)
    row = prep.EvaluationRowV1(
        dataset=dataset, split=stage, qid=f"{dataset}-{stage}-q1",
        question=f"What is related in {dataset} {stage}?",
        paragraph_source_ids=(source_id,), gold_source_ids=(source_id,), hop=2,
    )
    return prep.PreparedSegmentV1(
        dataset=dataset, split=stage,
        paragraphs=(paragraph,), evaluation_rows=(row,),
    )


def _fresh_manifest(segment: prep.PreparedSegmentV1) -> dict:
    row = segment.evaluation_rows[0]
    paragraph = segment.paragraphs[0]
    example = {
        "occurrence_id": f"occ:{row.qid}",
        "qid": row.qid,
        "dataset": segment.dataset,
        "question": row.question,
        "answer": "Beta",
        "hop": row.hop,
        "steps": [],
        "relation_chain": ["related"],
        "relation_chain_id": "1" * 64,
        "relation_template_id": "2" * 64,
        "evidence_content_ids": [paragraph.source_id],
        "raw_row_sha256": "3" * 64,
    }
    value = {
        "schema_version": fresh.SCHEMA_VERSION,
        "dataset": segment.dataset,
        "selection_seed": fresh.SELECTION_SEED,
        "quotas": [[2, 1]],
        "raw_source_sha256": "4" * 64,
        "source_file_sha256": None,
        "prior_qid_sha256": "5" * 64,
        "selected_manifest_sha256": "",
        "prior_qids": [f"{segment.dataset}-old"],
        "selected_qids": [row.qid],
        "counts": {
            "raw_rows": 2, "prior_rows": 1, "eligible_rows": 1,
            "selected_rows": 1, "excluded_rows_total": 1,
            "excluded_prior_qid": 1, "excluded_prior_template": 0,
            "excluded_prior_evidence": 0, "eligible_by_hop": [[2, 1]],
            "selected_by_hop": [[2, 1]], "compiler_paragraphs": 1,
        },
        "audit": {
            "prior_relation_template_count": 1,
            "prior_evidence_content_id_count": 1,
            "selected_prior_qid_overlap_count": 0,
            "selected_prior_template_overlap_count": 0,
            "selected_prior_evidence_overlap_count": 0,
            "selected_duplicate_qid_count": 0,
            "qid_disjoint": True, "relation_template_disjoint": True,
            "exact_evidence_disjoint": True, "all_disjoint": True,
        },
        "compiler_rows": [{
            "row_id": f"row:{row.qid}",
            "paragraph_source_ids": [paragraph.source_id],
        }],
        "compiler_paragraphs": [asdict(paragraph)],
        "evaluator_sidecar": [{
            "binding_id": f"binding:{row.qid}",
            "row_id": f"row:{row.qid}",
            "raw_row_sha256": "3" * 64,
            "paragraph_source_ids": list(row.paragraph_source_ids),
            "gold_source_ids": list(row.gold_source_ids),
            "benchmark_hop": row.hop,
            "example": example,
        }],
    }
    value["selected_manifest_sha256"] = sha256(canonical_json({
        key: child for key, child in value.items()
        if key != "selected_manifest_sha256"
    }).encode("utf-8")).hexdigest()
    return value


def _fixture(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_path)
    protocol = tmp_path / "protocol.md"
    protocol.write_text("frozen protocol\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight.json"
    _write_canonical(preflight_path, {})
    qwen35 = tmp_path / "qwen35.json"
    _write_canonical(qwen35, {})

    snapshot = _snapshot(tmp_path)
    attestation = bge.attest_model_snapshot(
        snapshot, expected_model=bge.FROZEN_MODEL_ID,
        expected_revision=bge.FROZEN_MODEL_REVISION,
    )
    monkeypatch.setattr(
        bge, "FROZEN_WEIGHT_BLOB_SHA256", attestation["weight_blob_sha256"],
    )
    bge_path = tmp_path / "bge-attestation.json"
    bge.write_model_attestation(bge_path, attestation)

    segments = {stage: {} for stage in h3.STAGES}
    sidecars = {}
    holdouts = {}
    for dataset in h3.DATASETS:
        sidecar = tmp_path / f"{dataset}-sidecar.json"
        _write_canonical(sidecar, {"dataset": dataset, "rows": []})
        sidecars[dataset] = str(sidecar)
        for stage in h3.STAGES:
            value = _segment(dataset, stage)
            path = tmp_path / f"{dataset}-{stage}.json"
            _write_canonical(path, asdict(value))
            segments[stage][dataset] = str(path)
            if stage == "fresh":
                holdout = tmp_path / f"{dataset}-fresh-manifest.json"
                _write_canonical(holdout, _fresh_manifest(value))
                holdouts[dataset] = str(holdout)

    code_sha256 = {
        name: manifest.file_sha256(path)
        for name, path in h3.FROZEN_CODE_MODULE_PATHS.items()
    }
    modules = tuple(
        SimpleNamespace(path=name, sha256=digest)
        for name, digest in code_sha256.items()
    )
    preflight_receipt = SimpleNamespace(
        receipt_id="fixture-preflight",
        implementation_modules=modules,
        implementation_code_root_sha256=h3.lifecycle.authorization_code_root(
            code_sha256
        ),
    )
    monkeypatch.setattr(
        h3.preflight, "load_preflight_receipt", lambda _path: preflight_receipt,
    )
    qwen_receipt = {
        "endpoint": "http://127.0.0.1:18100/v1",
        "served_model": "fixture-qwen35",
        "snapshot": {"resolved_revision": "a" * 40},
    }
    monkeypatch.setattr(
        manifest.deployment, "load_deployment_receipt",
        lambda _path: qwen_receipt,
    )
    monkeypatch.setattr(
        h3, "_validate_deployment_attestation",
        lambda *_args, **_kwargs: qwen_receipt,
    )
    kwargs = {
        "protocol_path": protocol,
        "preflight_path": preflight_path,
        "bge_attestation_path": bge_path,
        "qwen35_deployment_path": qwen35,
        "development_segments": segments["development"],
        "fresh_segments": segments["fresh"],
        "development_sidecars": sidecars,
        "fresh_manifests": holdouts,
        "output_prefix": "runs/h3-proof",
        "extractor": manifest.ExtractorExecutionV1(
            endpoint=qwen_receipt["endpoint"],
            model=qwen_receipt["served_model"],
            model_revision=qwen_receipt["snapshot"]["resolved_revision"],
        ),
        "qwen27_deployment_path": "runs/h3-proof/fresh/qwen27.json",
        "arc": manifest.ArcExecutionV1(
            endpoint="http://127.0.0.1:18000/v1",
        ),
    }
    return kwargs


def test_manifest_build_is_deterministic_and_recomputes_preimages(
    tmp_path, monkeypatch,
):
    kwargs = _fixture(tmp_path, monkeypatch)
    first = manifest.build_manifest(**kwargs)
    second = manifest.build_manifest(**kwargs)
    assert canonical_json(first) == canonical_json(second)
    assert first["stage_artifacts"]["development"]["preimages"] == {
        "extraction_records": 2,
        "extraction_jsonl_sha256": first["stage_artifacts"]["development"][
            "preimages"
        ]["extraction_jsonl_sha256"],
        "embedding_records": 4,
        "embedding_jsonl_sha256": first["stage_artifacts"]["development"][
            "preimages"
        ]["embedding_jsonl_sha256"],
    }
    assert first["stage_artifacts"]["fresh"][
        "arc_deployment_receipt"
    ]["path"] == "runs/h3-proof/fresh/qwen27.json"
    assert not (tmp_path / "runs/h3-proof/fresh/qwen27.json").exists()


def test_cli_validates_then_publishes_once(tmp_path, monkeypatch, capsys):
    kwargs = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "H3_B3_RUN_MANIFEST_FINAL_V2.json"
    args = [
        "--output", str(output),
        "--output-prefix", kwargs["output_prefix"],
        "--protocol", str(kwargs["protocol_path"]),
        "--preflight", str(kwargs["preflight_path"]),
        "--bge-attestation", str(kwargs["bge_attestation_path"]),
        "--qwen35-deployment", str(kwargs["qwen35_deployment_path"]),
    ]
    for dataset in h3.DATASETS:
        args.extend([
            "--development-segment",
            f"{dataset}={kwargs['development_segments'][dataset]}",
            "--fresh-segment", f"{dataset}={kwargs['fresh_segments'][dataset]}",
            "--development-sidecar",
            f"{dataset}={kwargs['development_sidecars'][dataset]}",
            "--fresh-manifest", f"{dataset}={kwargs['fresh_manifests'][dataset]}",
        ])
    args.extend([
        "--extractor-endpoint", kwargs["extractor"].endpoint,
        "--extractor-model", kwargs["extractor"].model,
        "--extractor-model-revision", kwargs["extractor"].model_revision,
        "--qwen27-deployment-path", kwargs["qwen27_deployment_path"],
        "--qwen27-endpoint", kwargs["arc"].endpoint,
    ])
    assert manifest.main(args) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["manifest_sha256"] == sha256(output.read_bytes()).hexdigest()
    assert h3.load_run_manifest(output)["schema_version"] == (
        h3.MANIFEST_SCHEMA_VERSION
    )
    with pytest.raises(FileExistsError, match="first-write-wins"):
        manifest.main(args)


def test_existing_committed_output_blocks_freeze(tmp_path, monkeypatch):
    kwargs = _fixture(tmp_path, monkeypatch)
    collision = tmp_path / "runs/h3-proof/development/extractions.jsonl"
    collision.parent.mkdir(parents=True)
    collision.write_text("cherry-picked\n", encoding="utf-8")
    with pytest.raises(manifest.ManifestBuildError, match="already exists"):
        manifest.build_manifest(**kwargs)


def test_fresh_manifest_segment_mismatch_blocks_freeze(tmp_path, monkeypatch):
    kwargs = _fixture(tmp_path, monkeypatch)
    path = Path(kwargs["fresh_manifests"]["musique"])
    value = json.loads(path.read_text(encoding="utf-8"))
    value["selected_qids"] = ["tampered"]
    value["selected_manifest_sha256"] = sha256(canonical_json({
        key: child for key, child in value.items()
        if key != "selected_manifest_sha256"
    }).encode("utf-8")).hexdigest()
    _write_canonical(path, value)
    with pytest.raises(manifest.ManifestBuildError, match="qid order mismatch"):
        manifest.build_manifest(**kwargs)
