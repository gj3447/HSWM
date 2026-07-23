"""Fixture teeth for deterministic, first-write H3 PRE_RUN manifests."""
from __future__ import annotations

from dataclasses import asdict, replace
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
    parent_protocol = tmp_path / "parent-protocol.md"
    parent_protocol.write_text("frozen parent protocol\n", encoding="utf-8")
    refusal = tmp_path / "v3-refusal.md"
    refusal.write_text("frozen V3 refusal\n", encoding="utf-8")
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
        gate_source_code_root_sha256="6" * 64,
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
    frozen_segments = {
        stage: {
            dataset: {
                "path": Path(segments[stage][dataset]).relative_to(tmp_path).as_posix(),
                "sha256": manifest.file_sha256(segments[stage][dataset]),
            }
            for dataset in h3.DATASETS
        }
        for stage in h3.STAGES
    }
    frozen_preimages = {
        stage: h3._preimage_receipt(tuple(
            h3.load_prepared_segment(segments[stage][dataset])
            for dataset in h3.DATASETS
        ))
        for stage in h3.STAGES
    }
    frozen_sidecars = {
        dataset: {
            "path": Path(sidecars[dataset]).relative_to(tmp_path).as_posix(),
            "file_sha256": manifest.file_sha256(sidecars[dataset]),
        }
        for dataset in h3.DATASETS
    }
    frozen_holdouts = {}
    for dataset in h3.DATASETS:
        holdout_value = json.loads(Path(holdouts[dataset]).read_text(encoding="utf-8"))
        frozen_holdouts[dataset] = {
            "path": Path(holdouts[dataset]).relative_to(tmp_path).as_posix(),
            "manifest_file_sha256": manifest.file_sha256(holdouts[dataset]),
            "selected_manifest_id": holdout_value["selected_manifest_sha256"],
        }
    extractor_config = manifest.rex.ExtractorConfigV1(
        endpoint=kwargs["extractor"].endpoint,
        model=kwargs["extractor"].model,
        model_revision=kwargs["extractor"].model_revision,
        max_concurrency=kwargs["extractor"].max_concurrency,
        timeout_seconds=kwargs["extractor"].timeout_seconds,
        max_tokens=kwargs["extractor"].max_tokens,
        max_attempts=kwargs["extractor"].max_attempts,
        batch_size=1,
    )
    monkeypatch.setattr(manifest, "FROZEN_V5_PROTOCOL_BINDING", {
        "path": protocol.relative_to(tmp_path).as_posix(),
        "sha256": manifest.file_sha256(protocol),
    })
    monkeypatch.setattr(manifest, "FROZEN_V5_PARENT_EVIDENCE", (
        {
            "path": parent_protocol.relative_to(tmp_path).as_posix(),
            "sha256": manifest.file_sha256(parent_protocol),
        },
        {
            "path": refusal.relative_to(tmp_path).as_posix(),
            "sha256": manifest.file_sha256(refusal),
        },
    ))
    monkeypatch.setattr(
        manifest, "FROZEN_V5_OUTPUT_PREFIX", kwargs["output_prefix"],
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_PREFLIGHT_PATH",
        preflight_path.relative_to(tmp_path).as_posix(),
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256",
        preflight_receipt.gate_source_code_root_sha256,
    )
    monkeypatch.setattr(manifest, "FROZEN_V5_QWEN35_DEPLOYMENT", {
        "path": qwen35.relative_to(tmp_path).as_posix(),
        "sha256": manifest.file_sha256(qwen35),
    })
    monkeypatch.setattr(
        manifest, "FROZEN_V5_EXTRACTOR_SCHEMA_VERSION", manifest.rex.SCHEMA_VERSION,
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_ATTEMPT_JOURNAL_SCHEMA_VERSION",
        manifest.rex.JOURNAL_SCHEMA_VERSION,
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_ATTEMPT_JOURNAL_EVENTS",
        (manifest.rex.START_EVENT, manifest.rex.FINALIZE_EVENT),
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_EXTRACTOR_EXECUTION", kwargs["extractor"],
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_EXTRACTOR_PROMPT_SHA256",
        manifest.rex.prompt_sha256(),
    )
    monkeypatch.setattr(
        manifest, "FROZEN_V5_EXTRACTOR_CONFIG_SHA256",
        manifest.rex.config_sha256(extractor_config),
    )
    monkeypatch.setattr(manifest, "FROZEN_V5_STAGE_SEGMENTS", frozen_segments)
    monkeypatch.setattr(manifest, "FROZEN_V5_STAGE_PREIMAGES", frozen_preimages)
    monkeypatch.setattr(
        manifest, "FROZEN_V5_DEVELOPMENT_SIDECARS", frozen_sidecars,
    )
    monkeypatch.setattr(manifest, "FROZEN_V5_FRESH_HOLDOUT", frozen_holdouts)
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
    assert first["extractor"] == {
        "endpoint": kwargs["extractor"].endpoint,
        "model": kwargs["extractor"].model,
        "model_revision": kwargs["extractor"].model_revision,
        "max_concurrency": kwargs["extractor"].max_concurrency,
        "timeout_seconds": kwargs["extractor"].timeout_seconds,
        "max_tokens": kwargs["extractor"].max_tokens,
        "max_attempts": kwargs["extractor"].max_attempts,
        "prompt_sha256": manifest.rex.prompt_sha256(),
        "config_sha256": manifest.rex.config_sha256(
            manifest.rex.ExtractorConfigV1(
                endpoint=kwargs["extractor"].endpoint,
                model=kwargs["extractor"].model,
                model_revision=kwargs["extractor"].model_revision,
                max_concurrency=kwargs["extractor"].max_concurrency,
                timeout_seconds=kwargs["extractor"].timeout_seconds,
                max_tokens=kwargs["extractor"].max_tokens,
                max_attempts=kwargs["extractor"].max_attempts,
                batch_size=1,
            )
        ),
        "batch_size": 1,
    }


def test_cli_validates_then_publishes_once(tmp_path, monkeypatch, capsys):
    kwargs = _fixture(tmp_path, monkeypatch)
    # This publication test substitutes a complete synthetic preregistration;
    # the dedicated loader-contract test covers the one-off live V5 constants.
    monkeypatch.setattr(
        h3, "_require_frozen_v5_manifest_contract",
        lambda **_kwargs: None,
    )
    output = tmp_path / manifest.FROZEN_V5_MANIFEST_PATH
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


def test_production_v5_contract_constants_are_exact():
    assert manifest.FROZEN_V5_MANIFEST_PATH == h3.FROZEN_V5_MANIFEST_PATH == (
        "H3_B3_RUN_MANIFEST_V5_2026-07-20.json"
    )
    assert manifest.FROZEN_V5_PROTOCOL_BINDING == {
        "path": "H3_B3_V5_RESTART_PREREG_2026-07-20.md",
        "sha256": "253ffd9e2550b30f6aa3c2d3144d4524a6f6c18ed9849f795553218e03e7eebb",
    }
    assert manifest.FROZEN_V5_EXTRACTOR_EXECUTION == (
        manifest.ExtractorExecutionV1(
            endpoint="http://127.0.0.1:18002/v1",
            model="Qwen/Qwen3.6-35B-A3B-FP8",
            model_revision="95a723d08a9490559dae23d0cff1d9466213d989",
            max_concurrency=2, timeout_seconds=180.0,
            max_tokens=1024, max_attempts=2,
        )
    )
    assert manifest.FROZEN_V5_ATTEMPT_JOURNAL_SCHEMA_VERSION == (
        "hswm-recorded-llm-attempt-journal/v1"
    )
    assert manifest.FROZEN_V5_ATTEMPT_JOURNAL_EVENTS == ("START", "FINALIZE")
    assert manifest.FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256 == (
        "2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5"
    )
    assert manifest.FROZEN_V5_PREFLIGHT_PATH == (
        ".ab_p5_cache/h3_b3/H3_B3_PREFLIGHT_RECEIPT_V5_2026-07-20.json"
    )
    assert manifest.FROZEN_V5_STAGE_PREIMAGES["development"] == {
        "extraction_records": 3_599,
        "extraction_jsonl_sha256": (
            "53d827704e530d91a7847a193735718ea9df36f8fe421feaaa61393f3193d114"
        ),
        "embedding_records": 3_999,
        "embedding_jsonl_sha256": (
            "99e44c8fd5b7d3935ab4299e0510d620643dd82a4e0ee47a389d078d739b44f4"
        ),
    }
    assert manifest.FROZEN_BGE_DIMENSION == h3.FROZEN_BGE_DIMENSION == 1024
    for name in (
        "FROZEN_V5_PROTOCOL_BINDING",
        "FROZEN_V5_PARENT_EVIDENCE",
        "FROZEN_V5_OUTPUT_PREFIX",
        "FROZEN_V5_PREFLIGHT_PATH",
        "FROZEN_V5_QWEN35_DEPLOYMENT",
        "FROZEN_V5_GATE_SOURCE_CODE_ROOT_SHA256",
        "FROZEN_V5_STAGE_SEGMENTS",
        "FROZEN_V5_STAGE_PREIMAGES",
        "FROZEN_V5_DEVELOPMENT_SIDECARS",
        "FROZEN_V5_FRESH_HOLDOUT",
    ):
        assert getattr(manifest, name) == getattr(h3, name)


def test_alternate_manifest_filename_is_rejected(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    with pytest.raises(
        manifest.ManifestBuildError, match="filename differs from frozen V5",
    ):
        manifest._output_manifest_path(tmp_path / "alternate.json")


def test_self_consistent_embedding_dimension_drift_is_rejected(
    tmp_path, monkeypatch,
):
    kwargs = _fixture(tmp_path, monkeypatch)
    value = manifest.build_manifest(**kwargs)
    embedding = value["embedding"]
    embedding["dimension"] = 512
    execution = {
        key: embedding[key] for key in (
            "model", "snapshot", "dimension", "pooling", "max_length",
            "dtype", "batch_size", "producer_code_sha256",
        )
    }
    embedding["config_sha256"] = sha256(
        canonical_json(execution).encode("utf-8")
    ).hexdigest()
    path = tmp_path / manifest.FROZEN_V5_MANIFEST_PATH
    _write_canonical(path, value)
    monkeypatch.setattr(
        h3, "_require_frozen_v5_manifest_contract",
        lambda **_kwargs: None,
    )
    with pytest.raises(
        h3.ArtifactIntegrityError, match="embedding frozen execution contract",
    ):
        h3.load_run_manifest(path)


def test_self_consistent_extractor_attempt_drift_is_rejected(
    tmp_path, monkeypatch,
):
    kwargs = _fixture(tmp_path, monkeypatch)
    kwargs["extractor"] = replace(kwargs["extractor"], max_attempts=3)
    with pytest.raises(
        manifest.ManifestBuildError, match="extractor execution differs",
    ):
        manifest.build_manifest(**kwargs)


@pytest.mark.parametrize("stage", ["development", "fresh"])
def test_self_consistent_segment_drift_is_rejected(
    stage, tmp_path, monkeypatch,
):
    kwargs = _fixture(tmp_path, monkeypatch)
    path = Path(kwargs[f"{stage}_segments"]["musique"])
    segment = h3.load_prepared_segment(path)
    original = segment.paragraphs[0]
    changed_text = original.text + " Gamma was also present."
    changed_source_id = prep.paragraph_source_id(
        segment.dataset, original.title, changed_text,
    )
    changed_paragraph = replace(
        original, source_id=changed_source_id, text=changed_text,
    )
    changed_row = replace(
        segment.evaluation_rows[0],
        paragraph_source_ids=(changed_source_id,),
        gold_source_ids=(changed_source_id,),
    )
    _write_canonical(path, asdict(replace(
        segment,
        paragraphs=(changed_paragraph,),
        evaluation_rows=(changed_row,),
    )))
    with pytest.raises(
        manifest.ManifestBuildError,
        match=rf"{stage} segment bindings differ",
    ):
        manifest.build_manifest(**kwargs)


def test_self_consistent_holdout_drift_is_rejected(tmp_path, monkeypatch):
    kwargs = _fixture(tmp_path, monkeypatch)
    path = Path(kwargs["fresh_manifests"]["musique"])
    value = json.loads(path.read_text(encoding="utf-8"))
    value["raw_source_sha256"] = "9" * 64
    value["selected_manifest_sha256"] = sha256(canonical_json({
        key: child for key, child in value.items()
        if key != "selected_manifest_sha256"
    }).encode("utf-8")).hexdigest()
    _write_canonical(path, value)
    with pytest.raises(
        manifest.ManifestBuildError, match="fresh holdout bindings differ",
    ):
        manifest.build_manifest(**kwargs)


def test_self_consistent_sidecar_drift_is_rejected(tmp_path, monkeypatch):
    kwargs = _fixture(tmp_path, monkeypatch)
    sidecar = Path(kwargs["development_sidecars"]["musique"])
    _write_canonical(sidecar, {"dataset": "musique", "rows": [], "note": "drift"})
    with pytest.raises(
        manifest.ManifestBuildError, match="development sidecar bindings differ",
    ):
        manifest.build_manifest(**kwargs)


def test_alternate_self_consistent_deployment_receipt_is_rejected(
    tmp_path, monkeypatch,
):
    kwargs = _fixture(tmp_path, monkeypatch)
    alternate = tmp_path / "alternate-qwen35.json"
    alternate.write_bytes(Path(kwargs["qwen35_deployment_path"]).read_bytes())
    kwargs["qwen35_deployment_path"] = alternate
    with pytest.raises(
        manifest.ManifestBuildError, match="deployment receipt differs",
    ):
        manifest.build_manifest(**kwargs)


def test_self_resealed_preflight_gate_source_root_is_rejected(
    tmp_path, monkeypatch,
):
    kwargs = _fixture(tmp_path, monkeypatch)
    receipt = h3.preflight.load_preflight_receipt(kwargs["preflight_path"])
    resealed = SimpleNamespace(
        **{
            **vars(receipt),
            "receipt_id": "self-consistent-resealed-preflight",
            "gate_source_code_root_sha256": "7" * 64,
        }
    )
    monkeypatch.setattr(
        h3.preflight, "load_preflight_receipt", lambda _path: resealed,
    )
    with pytest.raises(
        manifest.ManifestBuildError, match="gate-source code root differs",
    ):
        manifest.build_manifest(**kwargs)
