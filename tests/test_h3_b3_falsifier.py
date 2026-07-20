"""Artifact-boundary teeth for the H3-B3 confirmatory falsifier."""
from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import json
from types import SimpleNamespace

import numpy as np
import pytest

import h3_b3_falsifier as h3
import h3_b3_prepare as prep
import h3_arc_adjudicator as arc
import claim_builder as cb
import recorded_llm_extractor as rex
import relation_eval as reval
from title_anchor_builder import ParagraphInputV1
from world_ir import sha256_text


def _segment() -> prep.PreparedSegmentV1:
    title = "Alpha"
    text = "Alpha was composed by Beta in Paris."
    source_id = prep.paragraph_source_id("musique", title, text)
    paragraph = prep.fresh.CompilerParagraphV1(
        source_id=source_id, title=title, text=text,
    )
    row = prep.EvaluationRowV1(
        dataset="musique", split="development", qid="q1",
        question="Where was the composer of Alpha born?",
        paragraph_source_ids=(paragraph.source_id,),
        gold_source_ids=(paragraph.source_id,), hop=2,
    )
    return prep.PreparedSegmentV1(
        dataset="musique", split="development",
        paragraphs=(paragraph,), evaluation_rows=(row,),
    )


def _write_segment(tmp_path, segment: prep.PreparedSegmentV1):
    path = tmp_path / "segment.json"
    path.write_text(json.dumps(asdict(segment)), encoding="utf-8")
    return path


def _write_embeddings(tmp_path, segment: prep.PreparedSegmentV1):
    records = prep.embedding_records((segment,))
    ids = np.asarray([item["id"] for item in records])
    kinds = np.asarray([item["kind"] for item in records])
    hashes = np.asarray([
        sha256(item["text"].encode("utf-8")).hexdigest() for item in records
    ])
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    assert len(records) == 2
    path = tmp_path / "vectors.npz"
    np.savez_compressed(
        path, ids=ids, kinds=kinds, text_sha256=hashes, vectors=vectors,
    )
    return path


def _record():
    source_id = _segment().paragraphs[0].source_id
    paragraph = ParagraphInputV1(
        source_id, "Alpha", "Alpha was composed by Beta in Paris.",
    )
    config = rex.ExtractorConfigV1(
        endpoint="http://example.invalid/v1", model="fixture-model",
        model_revision="fixture-revision",
    )
    content = json.dumps({
        "claims": [{
            "subject": "Alpha", "predicate": "was composed by",
            "arguments": [{"role": "composer", "exact": "Beta"}],
        }],
    })
    response = json.dumps({
        "model": "fixture-model",
        "choices": [{
            "message": {"content": content}, "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
    })
    record = rex.extract_paragraph(paragraph, config, lambda request: response)
    assert record.frozen_extraction is not None
    return record, config


def _shared_build():
    paragraphs = (
        ParagraphInputV1(
            "src:green", "Green", "Green was formed by Steve Hillage."
        ),
        ParagraphInputV1(
            "src:miquette", "Miquette Giraudy",
            "Steve Hillage collaborated with Miquette Giraudy.",
        ),
    )
    payloads = (
        {
            "subject": {"start": 0, "end": 5, "exact": "Green"},
            "predicate": {"start": 6, "end": 19, "exact": "was formed by"},
            "arguments": [{"role": "founder", "start": 20, "end": 33,
                           "exact": "Steve Hillage"}],
        },
        {
            "subject": {"start": 0, "end": 13, "exact": "Steve Hillage"},
            "predicate": {"start": 14, "end": 31,
                          "exact": "collaborated with"},
            "arguments": [{"role": "collaborator", "start": 32, "end": 48,
                           "exact": "Miquette Giraudy"}],
        },
    )
    extractions = tuple(
        cb.freeze_extraction(
            paragraph.source_id,
            json.dumps({"schema_version": cb.EXTRACTION_SCHEMA_VERSION,
                        "claims": [payload]}, separators=(",", ":")),
            producer="fixture", model_revision="fixture-revision",
            prompt_sha256=sha256_text("prompt"),
            config_sha256=sha256_text("config"),
        )
        for paragraph, payload in zip(paragraphs, payloads, strict=True)
    )
    return cb.compile_claim_graph(paragraphs, extractions)


def _multi_document_homonym_build():
    specs = (
        (
            "arg:same", "Band One", "Band One was formed by Alex Jordan.",
            "Band One", "was formed by", "Alex Jordan", "founder",
        ),
        (
            "arg:different-1", "Country Report",
            "Country Report was authored by Alex Jordan.",
            "Country Report", "was authored by", "Alex Jordan", "author",
        ),
        (
            "arg:different-2", "Chemistry Note",
            "Chemistry Note was reviewed by Alex Jordan.",
            "Chemistry Note", "was reviewed by", "Alex Jordan", "reviewer",
        ),
        (
            "subject:same", "Alex Jordan",
            "Alex Jordan collaborated with Band One.",
            "Alex Jordan", "collaborated with", "Band One", "collaborator",
        ),
    )
    paragraphs = []
    extractions = []
    for source_id, title, text, subject, predicate, argument, role in specs:
        paragraph = ParagraphInputV1(source_id, title, text)
        paragraphs.append(paragraph)

        def span(exact):
            start = text.index(exact)
            return {"start": start, "end": start + len(exact), "exact": exact}

        payload = {
            "subject": span(subject), "predicate": span(predicate),
            "arguments": [{"role": role, **span(argument)}],
        }
        extractions.append(cb.freeze_extraction(
            source_id,
            json.dumps({
                "schema_version": cb.EXTRACTION_SCHEMA_VERSION,
                "claims": [payload],
            }, separators=(",", ":")),
            producer="fixture", model_revision="fixture-revision",
            prompt_sha256=sha256_text("prompt"),
            config_sha256=sha256_text("config"),
        ))
    return cb.compile_claim_graph(tuple(paragraphs), tuple(extractions))


def test_prepared_segment_is_hash_bound_and_schema_strict(tmp_path):
    segment = _segment()
    path = _write_segment(tmp_path, segment)
    digest = h3._file_sha256(path)

    assert h3.load_prepared_segment(path, expected_sha256=digest) == segment
    with pytest.raises(h3.ArtifactIntegrityError, match="hash mismatch"):
        h3.load_prepared_segment(path, expected_sha256="0" * 64)

    value = json.loads(path.read_text())
    value["question"] = "compiler leakage"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(h3.ArtifactIntegrityError, match="keys must be exactly"):
        h3.load_prepared_segment(path)


def test_embedding_join_uses_stable_id_and_exact_text_hash(tmp_path):
    segment = _segment()
    path = _write_embeddings(tmp_path, segment)

    artifact = h3.load_embedding_artifact(path, (segment,))
    assert set(artifact.vector_by_id) == {
        f"paragraph:{segment.paragraphs[0].source_id}", "query:musique:q1",
    }

    archive = np.load(path)
    bad_hashes = archive["text_sha256"].copy()
    bad_hashes[0] = "0" * 64
    np.savez_compressed(
        path, ids=archive["ids"], kinds=archive["kinds"],
        text_sha256=bad_hashes, vectors=archive["vectors"],
    )
    with pytest.raises(h3.ArtifactIntegrityError, match="preimage mismatch"):
        h3.load_embedding_artifact(path, (segment,))


def test_recorded_extraction_is_complete_identity_checked_and_accounted(tmp_path):
    segment = _segment()
    record, config = _record()
    path = tmp_path / "records.jsonl"
    path.write_text(rex._record_to_json(record) + "\n", encoding="utf-8")

    artifact = h3.load_extraction_artifact(
        path, (segment,), expected_model_revision=config.model_revision,
        expected_prompt_sha256=record.prompt_sha256,
        expected_config_sha256=record.config_sha256,
    )
    assert tuple(artifact.frozen_by_source) == (segment.paragraphs[0].source_id,)
    assert artifact.accounting["endpoint_calls"] == 1
    assert artifact.accounting["total_tokens"] == 15

    batch_two = replace(record, record_id="", batch_size=2)
    batch_two = replace(batch_two, record_id=rex._record_id(batch_two))
    path.write_text(rex._record_to_json(batch_two) + "\n", encoding="utf-8")
    with pytest.raises(h3.ArtifactIntegrityError, match="batch_size"):
        h3.load_extraction_artifact(path, (segment,))

    path.write_text("", encoding="utf-8")
    with pytest.raises(h3.ArtifactIntegrityError, match="incomplete"):
        h3.load_extraction_artifact(path, (segment,))


def test_loader_accepts_deterministic_error_then_success_as_two_attempts(tmp_path):
    segment = _segment()
    success, config = _record()
    paragraph = ParagraphInputV1(
        segment.paragraphs[0].source_id,
        segment.paragraphs[0].title,
        segment.paragraphs[0].text,
    )

    def fail_transport(_request):
        raise TimeoutError("synthetic retryable failure")

    failed = rex.extract_paragraph(paragraph, config, fail_transport)
    assert failed.batch_request_id == success.batch_request_id
    assert failed.raw_response_sha256 != success.raw_response_sha256
    assert failed.frozen_extraction is None
    path = tmp_path / "retry.jsonl"
    cache = rex.JSONLExtractionCache(path)
    failed = cache.append_attempt((failed,))[0]
    success = cache.append_attempt((success,))[0]
    assert (failed.attempt_ordinal, success.attempt_ordinal) == (1, 2)
    assert failed.attempt_id != success.attempt_id

    artifact = h3.load_extraction_artifact(
        path, (segment,), expected_model_revision=config.model_revision,
        expected_prompt_sha256=success.prompt_sha256,
        expected_config_sha256=success.config_sha256,
    )

    assert artifact.accounting["retry_sources"] == 1
    assert artifact.accounting["endpoint_calls"] == 2
    assert artifact.accounting["unique_batch_request_ids"] == 1
    assert tuple(artifact.frozen_by_source) == (paragraph.source_id,)


def test_cluster_inference_resamples_and_signflips_whole_components():
    result = h3.cluster_inference(
        np.asarray([0.1, 0.1, 0.2, 0.2]), ("a", "a", "b", "b"),
        n_bootstrap=500, n_signflips=1000, seed=7,
    )
    assert result["n_queries"] == 4
    assert result["n_components"] == 2
    assert result["mean_delta"] == 0.15
    assert result["ci95"][0] > 0
    assert 0 <= result["p_cluster_signflip_one_sided"] <= 1


def _second_edge_fixture(n_queries, decoy_ids=("decoy",)):
    rows = tuple(
        SimpleNamespace(qid=f"q{index}", question=f"question {index}")
        for index in range(n_queries)
    )
    k1 = SimpleNamespace(score_sha256="matched-k1")
    path = SimpleNamespace(steps=(
        SimpleNamespace(arc_id="first-edge"),
        SimpleNamespace(arc_id="second-edge"),
    ))
    receipts = (
        SimpleNamespace(promoted_paths=(path,), k1_ablation=k1),
        *(SimpleNamespace(promoted_paths=(), k1_ablation=k1)
          for _ in range(n_queries - 1)),
    )
    compiled = SimpleNamespace(
        segment=SimpleNamespace(evaluation_rows=rows),
        b3_graph=SimpleNamespace(arcs=tuple(
            SimpleNamespace(arc_id=arc_id)
            for arc_id in ("second-edge", *decoy_ids)
        )),
        cosine=np.zeros((n_queries, 1), dtype=np.float64),
        gold_ordinals=tuple(
            np.asarray([0], dtype=np.int64) for _ in range(n_queries)
        ),
    )
    real = np.zeros((n_queries, 1), dtype=np.float64)
    real[0, 0] = 1.0
    return compiled, receipts, real


def _mean_only_cluster_inference(delta, components, **_kwargs):
    mean = round(float(np.mean(delta)), 6)
    return {
        "n_queries": len(delta), "n_components": len(set(components)),
        "mean_delta": mean, "ci95": [mean, mean],
    }


def test_second_edge_estimand_keeps_99_unaffected_queries_as_exact_zero(monkeypatch):
    compiled, receipts, real = _second_edge_fixture(100)
    observed_arrays = []

    monkeypatch.setattr(
        h3.typed, "target_shuffle_null_control",
        lambda graph, _arc_ids, seed: graph,
    )
    monkeypatch.setattr(
        h3, "_rewired_duplicate_typed_endpoints", lambda *_args: 0,
    )
    monkeypatch.setattr(h3, "_graph_duplicate_typed_endpoints", lambda *_args: 0)
    monkeypatch.setattr(
        h3.typed, "compose_typed_scores",
        lambda *_args: (
            np.asarray([0.0]), np.asarray([0.0]),
            SimpleNamespace(k1_ablation=SimpleNamespace(
                score_sha256="matched-k1"
            )),
        ),
    )
    monkeypatch.setattr(
        h3, "_query_metrics",
        lambda scores, _gold, seed: {
            metric: float(scores[0])
            for metric in ("ndcg10", "asr10", "support_recall10")
        },
    )

    def capture_inference(delta, components, **kwargs):
        observed_arrays.append((delta.copy(), tuple(components)))
        return _mean_only_cluster_inference(delta, components, **kwargs)

    monkeypatch.setattr(h3, "cluster_inference", capture_inference)
    components = tuple(f"component-{index}" for index in range(100))
    result = h3._second_edge_query_diagnostic(
        compiled, h3.POLICY_GRID[0], real, receipts, tuple(range(100)),
        components, h3.EvaluationConfigV1(n_bootstrap=100, n_signflips=100),
    )

    assert result["observed_queries"] == 1
    assert result["unchanged_no_second_edge_queries"] == 99
    assert result["valid_queries"] == result["total_queries"] == 100
    assert result["estimand_complete"]
    assert result["mean_real_minus_null"]["ndcg10"] == 0.01
    assert len(observed_arrays) == 3
    for values, seen_components in observed_arrays:
        assert values.tolist() == [1.0, *([0.0] * 99)]
        assert seen_components == components
    assert sum(
        row["status"] == "UNCHANGED_NO_SECOND_EDGE"
        for row in result["queries"]
    ) == 99


def test_second_edge_decoy_search_skips_k1_change_then_accepts_preserving(monkeypatch):
    decoy_ids = ("decoy-a", "decoy-b")
    compiled, receipts, real = _second_edge_fixture(1, decoy_ids)
    qid = compiled.segment.evaluation_rows[0].qid
    ordered = sorted(
        decoy_ids,
        key=lambda arc_id: (
            sha256(f"second-edge|{qid}|{arc_id}".encode()).hexdigest(),
            arc_id,
        ),
    )
    attempts = []

    def shuffle(_graph, arc_ids, *, seed):
        assert seed == 0
        attempts.append(arc_ids[-1])
        return SimpleNamespace(decoy_arc_id=arc_ids[-1])

    def compose(_question, _static, graph, _policy):
        digest = (
            "changed-k1" if graph.decoy_arc_id == ordered[0] else "matched-k1"
        )
        return (
            np.asarray([0.0]), np.asarray([0.0]),
            SimpleNamespace(k1_ablation=SimpleNamespace(score_sha256=digest)),
        )

    monkeypatch.setattr(h3.typed, "target_shuffle_null_control", shuffle)
    monkeypatch.setattr(
        h3, "_rewired_duplicate_typed_endpoints", lambda *_args: 0,
    )
    monkeypatch.setattr(h3, "_graph_duplicate_typed_endpoints", lambda *_args: 0)
    monkeypatch.setattr(h3.typed, "compose_typed_scores", compose)
    monkeypatch.setattr(
        h3, "_query_metrics",
        lambda scores, _gold, seed: {
            metric: float(scores[0])
            for metric in ("ndcg10", "asr10", "support_recall10")
        },
    )
    monkeypatch.setattr(h3, "cluster_inference", _mean_only_cluster_inference)
    args = (
        compiled, h3.POLICY_GRID[0], real, receipts, (0,), ("component",),
        h3.EvaluationConfigV1(n_bootstrap=100, n_signflips=100),
    )

    result = h3._second_edge_query_diagnostic(*args)

    assert attempts == ordered
    assert result["invalid_queries"] == 0
    assert result["queries"][0]["decoy_arc_id"] == ordered[1]
    assert result["queries"][0]["attempted_decoys"] == 2
    assert result["queries"][0]["k1_rejected_decoys"] == 1

    attempts.clear()
    monkeypatch.setattr(
        h3.typed, "compose_typed_scores",
        lambda *_args: (
            np.asarray([0.0]), np.asarray([0.0]),
            SimpleNamespace(k1_ablation=SimpleNamespace(
                score_sha256="always-changed"
            )),
        ),
    )
    invalid = h3._second_edge_query_diagnostic(*args)
    assert attempts == ordered
    assert invalid["status"] == "NULL_INVALID"
    assert invalid["invalid_queries"] == 1
    assert not invalid["estimand_complete"]
    assert not invalid["passes_both_primary"]


def test_second_edge_decoy_rejects_duplicate_typed_endpoint(monkeypatch):
    decoy_ids = ("decoy-a", "decoy-b")
    compiled, receipts, real = _second_edge_fixture(1, decoy_ids)
    qid = compiled.segment.evaluation_rows[0].qid
    ordered = sorted(
        decoy_ids,
        key=lambda arc_id: (
            sha256(f"second-edge|{qid}|{arc_id}".encode()).hexdigest(), arc_id,
        ),
    )
    composed = []

    def shuffle(_graph, arc_ids, *, seed):
        return SimpleNamespace(decoy_arc_id=arc_ids[-1])

    def duplicate(graph, _selected):
        return int(graph.decoy_arc_id == ordered[0])

    def compose(_question, _static, graph, _policy):
        composed.append(graph.decoy_arc_id)
        return (
            np.asarray([0.0]), np.asarray([0.0]),
            SimpleNamespace(k1_ablation=SimpleNamespace(
                score_sha256="matched-k1"
            )),
        )

    monkeypatch.setattr(h3.typed, "target_shuffle_null_control", shuffle)
    monkeypatch.setattr(h3, "_rewired_duplicate_typed_endpoints", duplicate)
    monkeypatch.setattr(h3, "_graph_duplicate_typed_endpoints", lambda *_args: 0)
    monkeypatch.setattr(h3.typed, "compose_typed_scores", compose)
    monkeypatch.setattr(
        h3, "_query_metrics",
        lambda scores, _gold, seed: {
            metric: float(scores[0])
            for metric in ("ndcg10", "asr10", "support_recall10")
        },
    )
    monkeypatch.setattr(h3, "cluster_inference", _mean_only_cluster_inference)
    args = (
        compiled, h3.POLICY_GRID[0], real, receipts, (0,), ("component",),
        h3.EvaluationConfigV1(n_bootstrap=100, n_signflips=100),
    )

    result = h3._second_edge_query_diagnostic(*args)
    assert composed == [ordered[1]]
    assert result["queries"][0]["decoy_arc_id"] == ordered[1]
    assert result["queries"][0]["duplicate_rejected_decoys"] == 1

    monkeypatch.setattr(
        h3, "_rewired_duplicate_typed_endpoints", lambda *_args: 1,
    )
    invalid = h3._second_edge_query_diagnostic(*args)
    assert invalid["status"] == "NULL_INVALID"
    assert invalid["queries"][0]["duplicate_rejected_decoys"] == 2


def test_second_edge_decoy_rejects_collision_between_two_rewired_arcs(monkeypatch):
    compiled, receipts, real = _second_edge_fixture(1, ("decoy",))
    monkeypatch.setattr(
        h3.typed, "target_shuffle_null_control",
        lambda _graph, arc_ids, *, seed: SimpleNamespace(
            arcs=(), rewired=True, decoy_arc_id=arc_ids[-1],
        ),
    )
    monkeypatch.setattr(
        h3, "_rewired_duplicate_typed_endpoints", lambda *_args: 0,
    )
    monkeypatch.setattr(
        h3, "_graph_duplicate_typed_endpoints",
        lambda graph: int(bool(getattr(graph, "rewired", False))),
    )
    monkeypatch.setattr(
        h3.typed, "compose_typed_scores",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("duplicate candidate must not be scored")
        ),
    )
    monkeypatch.setattr(h3, "cluster_inference", _mean_only_cluster_inference)
    result = h3._second_edge_query_diagnostic(
        compiled, h3.POLICY_GRID[0], real, receipts, (0,), ("component",),
        h3.EvaluationConfigV1(n_bootstrap=100, n_signflips=100),
    )
    assert result["status"] == "NULL_INVALID"
    assert result["queries"][0]["duplicate_rejected_decoys"] == 1


def _wiki_row(qid, person, parent, place, *, rel2="place of birth", context=None):
    return {
        "_id": qid,
        "question": f"Where was the father of {person} born?",
        "answer": place,
        "type": "compositional",
        "evidences": [[person, "father", parent], [parent, rel2, place]],
        "supporting_facts": [[person, 0], [parent, 0]],
        "context": [
            [person, [f"{person}'s father was {parent}."]],
            [parent, [context or f"{parent} was born in {place}."]],
        ],
    }


def test_development_assignments_require_hash_bound_relation_evidence_components(tmp_path):
    rows = [
        _wiki_row("a", "Nia", "Omar", "Pune", context="Shared exact evidence."),
        _wiki_row("b", "Tao", "Sora", "Busan", context="Shared exact evidence."),
        _wiki_row("c", "Ivo", "Omar", "Pune", rel2="country",
                  context="Shared exact evidence."),
        _wiki_row("d", "Uma", "Pax", "Rome", rel2="occupation"),
        _wiki_row("e", "Eli", "Zed", "Bern", rel2="educated at"),
    ]
    evaluation_rows = tuple(
        h3._raw_evaluation_row("2wiki", "development", row) for row in rows
    )
    segment = prep.PreparedSegmentV1(
        dataset="2wiki", split="development", paragraphs=(),
        evaluation_rows=evaluation_rows,
    )
    payload = {
        "dataset": "2wiki", "rows": rows,
        "rows_sha256": sha256(
            reval.canonical_json(tuple(rows)).encode("utf-8")
        ).hexdigest(),
    }
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    digest = h3._file_sha256(path)

    val, test, components, receipt = h3.development_assignments(
        SimpleNamespace(segment=segment), path, split_seed=19,
        expected_file_sha256=digest,
    )
    assert val and test
    assert components[0] == components[1] == components[2]
    assert receipt["grouping"] == (
        "union(relation_template_id, exact_evidence_content_id)"
    )
    with pytest.raises(h3.ArtifactIntegrityError, match="file hash mismatch"):
        h3.development_assignments(
            SimpleNamespace(segment=segment), path, split_seed=19,
            expected_file_sha256="0" * 64,
        )

    favorable = replace(
        evaluation_rows[0],
        gold_source_ids=(evaluation_rows[0].gold_source_ids[0],),
    )
    tampered = replace(
        segment, evaluation_rows=(favorable, *evaluation_rows[1:]),
    )
    with pytest.raises(h3.ArtifactIntegrityError, match="provenance mismatch"):
        h3.development_assignments(
            SimpleNamespace(segment=tampered), path, split_seed=19,
            expected_file_sha256=digest,
        )


def test_preimage_receipt_binds_counts_and_canonical_jsonl_hashes():
    segment = _segment()
    observed = h3._preimage_receipt((segment,))
    assert h3._verify_preimage_receipt(observed, (segment,)) == observed
    bad = dict(observed)
    bad["embedding_records"] += 1
    with pytest.raises(h3.ArtifactIntegrityError, match="count/hash mismatch"):
        h3._verify_preimage_receipt(bad, (segment,))


def test_typed_matrix_refuses_nonstatic_safety_fallback(monkeypatch):
    static = np.asarray([[0.25]], dtype=np.float64)
    receipt = SimpleNamespace(
        reached_targets=0, trip_reason="fanout_gate", fanout_gate_trips=1,
        join_hub_gate_trips=0, h3_composition_status="REFUSE",
    )
    monkeypatch.setattr(
        h3.typed, "compose_typed_scores",
        lambda *_args, **_kwargs: (static[0] + 0.1, np.zeros(1), receipt),
    )
    compiled = SimpleNamespace(
        segment=_segment(), cosine=static, b3_graph=object(),
    )
    with pytest.raises(h3.HarnessInvariantError, match="bit-identical static"):
        h3._typed_matrix(compiled, h3.POLICY_GRID[0])


def test_fresh_manifest_components_union_relation_and_evidence_and_bind_question(tmp_path):
    base = _segment()
    other_title = "Decoy"
    other_text = "Decoy contains irrelevant evidence."
    other = prep.fresh.CompilerParagraphV1(
        source_id=prep.paragraph_source_id("musique", other_title, other_text),
        title=other_title, text=other_text,
    )
    candidates = (base.paragraphs[0].source_id, other.source_id)
    rows = tuple(replace(
        base.evaluation_rows[0], split="fresh", qid=f"q{index}",
        question=f"question {index}", paragraph_source_ids=candidates,
        gold_source_ids=(base.paragraphs[0].source_id,),
    ) for index in range(3))
    segment = replace(
        base, split="fresh", paragraphs=(base.paragraphs[0], other),
        evaluation_rows=rows,
    )
    manifest_id = "f" * 64
    binding_rows = []
    compiler_rows = []
    for index, row in enumerate(rows):
        raw_sha256 = f"{index + 1:064x}"
        occurrence_id = f"occurrence-{index}"
        row_id = prep.fresh._compiler_row_id("musique", row.qid, raw_sha256)
        compiler_rows.append({
            "row_id": row_id, "paragraph_source_ids": list(candidates),
        })
        binding_rows.append({
            "binding_id": prep.fresh._evaluator_binding_id(
                dataset="musique", row_id=row_id,
                raw_row_sha256=raw_sha256,
                paragraph_source_ids=row.paragraph_source_ids,
                gold_source_ids=row.gold_source_ids,
                benchmark_hop=row.hop, occurrence_id=occurrence_id,
            ),
            "row_id": row_id, "raw_row_sha256": raw_sha256,
            "paragraph_source_ids": list(row.paragraph_source_ids),
            "gold_source_ids": list(row.gold_source_ids),
            "benchmark_hop": row.hop,
            "example": {
                "occurrence_id": occurrence_id, "qid": row.qid,
                "dataset": "musique", "question": row.question,
                "raw_row_sha256": raw_sha256,
                "relation_template_id": (
                    "template-shared" if index < 2 else "template-3"
                ),
                "evidence_content_ids": [
                    "evidence-1" if index == 0 else f"evidence-{index}"
                ],
            },
        })
    value = {
        "schema_version": prep.fresh.SCHEMA_VERSION,
        "dataset": "musique", "selected_manifest_sha256": manifest_id,
        "selected_qids": [row.qid for row in rows],
        "audit": {"all_disjoint": True},
        "compiler_paragraphs": [asdict(item) for item in segment.paragraphs],
        "compiler_rows": compiler_rows,
        "evaluator_sidecar": binding_rows,
    }
    path = tmp_path / "fresh.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    components, receipt = h3.fresh_manifest_components(
        SimpleNamespace(segment=segment), path,
        expected_file_sha256=h3._file_sha256(path),
        expected_manifest_id=manifest_id,
    )
    assert components[0] == components[1]
    assert components[2] != components[0]
    assert receipt["n_components"] == 2

    value["evaluator_sidecar"][0]["example"]["question"] = "tampered"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(h3.ArtifactIntegrityError, match="provenance binding"):
        h3.fresh_manifest_components(
            SimpleNamespace(segment=segment), path,
            expected_file_sha256=h3._file_sha256(path),
            expected_manifest_id=manifest_id,
        )

    value["evaluator_sidecar"][0]["example"]["question"] = rows[0].question
    path.write_text(json.dumps(value), encoding="utf-8")
    favorable = replace(rows[0], gold_source_ids=(other.source_id,))
    tampered = replace(segment, evaluation_rows=(favorable, *rows[1:]))
    with pytest.raises(h3.ArtifactIntegrityError, match="provenance binding"):
        h3.fresh_manifest_components(
            SimpleNamespace(segment=tampered), path,
            expected_file_sha256=h3._file_sha256(path),
            expected_manifest_id=manifest_id,
        )


def test_arc_precision_packet_is_deterministic_and_contains_only_local_evidence():
    build = _shared_build()
    first = h3.build_arc_precision_audit_packet(build, dataset="musique")
    second = h3.build_arc_precision_audit_packet(build, dataset="musique")

    assert first == second
    assert first["n_sampled"] == 1
    assert first["evaluation_labels_included"] is False
    item = first["items"][0]
    assert item["left_context"]["selector_exact"] == "Steve Hillage"
    assert item["right_context"]["selector_exact"] == "Steve Hillage"
    serialized = json.dumps(first).casefold()
    for forbidden in ('"question"', '"answer"', '"gold"', '"hop"'):
        assert forbidden not in serialized


def test_shared_join_identity_sampling_keeps_every_emitted_homonym_pair():
    packet = h3.build_arc_precision_audit_packet(
        _multi_document_homonym_build(), dataset="musique",
    )
    jordan_items = [
        item for item in packet["items"]
        if item["normalized_surface"] == "alex jordan"
    ]
    pairs = {
        frozenset((
            item["left_context"]["source_id"],
            item["right_context"]["source_id"],
        ))
        for item in jordan_items
    }
    assert pairs == {
        frozenset(("arg:same", "subject:same")),
        frozenset(("arg:different-1", "subject:same")),
        frozenset(("arg:different-2", "subject:same")),
    }
    assert packet["sampling_unit"] == (
        "unique emitted shared-join source pair"
    )
    assert packet["n_available_audit_units"] >= len(pairs)


def test_arc_precision_gate_refuses_missing_judgment_and_uses_wilson_lower_bound(tmp_path):
    from tests.test_h3_arc_adjudicator import _config, _packet, _response

    packet = _packet(100)
    assert not h3.score_arc_precision_audit(packet, None)["admitted"]
    adjudication = arc.run_arc_adjudication(
        packet, _config(), cache_path=tmp_path / "all-same.jsonl",
        transport=lambda _request: _response('{"decision":"SAME"}'),
    ).adjudication
    result = h3.score_arc_precision_audit(packet, adjudication)
    assert result["precision"] == 1.0
    assert result["wilson95"][0] >= 0.90
    assert result["admitted"]
    assert result["adjudication_receipt"]["model_revision"] == (
        h3.ARC_AUDIT_MODEL_REVISION
    )

    calls = 0

    def five_unclear(_request):
        nonlocal calls
        calls += 1
        decision = "UNCLEAR" if calls <= 5 else "SAME"
        return _response(json.dumps({"decision": decision}, separators=(",", ":")))

    mixed = arc.run_arc_adjudication(
        packet, _config(), cache_path=tmp_path / "mixed.jsonl",
        transport=five_unclear,
    ).adjudication
    failed = h3.score_arc_precision_audit(packet, mixed)
    assert failed["unclear_counted_incorrect"] == 5
    assert not failed["admitted"]
