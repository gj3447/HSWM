from dataclasses import asdict
from hashlib import sha256
import inspect
import json

import numpy as np
import pytest

import composition as comp
import h3_b3_prepare as prep
import qkv_b1_probe as probe
import relation_eval as reval


def _graph() -> comp.CompositionGraphV1:
    return comp.make_graph(
        ("p0", "p1", "p2"),
        (
            comp.EvidenceArcV1(0, 1, "s0", 0, 5, "Alpha", "alpha"),
            comp.EvidenceArcV1(1, 2, "s1", 0, 4, "Beta", "beta"),
        ),
    )


def _vectors() -> tuple[np.ndarray, np.ndarray]:
    keys = np.eye(3, dtype=np.float64)
    query = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    return keys, query


def test_gamma_zero_and_missing_values_are_bit_identical_static_floors():
    keys, query = _vectors()
    static = keys @ query
    gamma_zero, receipt_zero = probe.score_qkv_b1(
        query, keys, _graph(),
        probe.QKVB1PolicyV1(seed_k=1, hops=2, gamma=0.0),
        value_vectors=keys,
    )
    no_values, receipt_no_values = probe.score_qkv_b1(
        query, keys, _graph(),
        probe.QKVB1PolicyV1(seed_k=1, hops=2, gamma=1.0),
        value_vectors=None,
    )
    assert gamma_zero.tobytes() == static.tobytes()
    assert no_values.tobytes() == static.tobytes()
    assert receipt_zero.layers == ()
    assert receipt_no_values.layers == ()
    assert not receipt_zero.applied and not receipt_no_values.applied
    assert receipt_zero.trip_reason == "gamma=0 static floor"
    assert receipt_no_values.trip_reason == "no value vectors"


def test_k1_and_k2_follow_outgoing_evidence_and_emit_deterministic_receipts():
    keys, query = _vectors()
    k1 = probe.QKVB1PolicyV1(seed_k=1, hops=1, gamma=1.0)
    k2 = probe.QKVB1PolicyV1(seed_k=1, hops=2, gamma=1.0)
    score1, receipt1 = probe.score_qkv_b1(
        query, keys, _graph(), k1, value_vectors=keys,
    )
    score2, receipt2 = probe.score_qkv_b1(
        query, keys, _graph(), k2, value_vectors=keys,
    )
    score2_again, receipt2_again = probe.score_qkv_b1(
        query, keys, _graph(), k2, value_vectors=keys,
    )

    assert len(receipt1.layers) == 1
    assert len(receipt2.layers) == 2
    assert receipt2.layers[0].arcs[0].selector_exact == "Alpha"
    assert receipt2.layers[1].arcs[0].selector_exact == "Beta"
    assert receipt2.layers[0].reached_targets == (1,)
    assert receipt2.layers[1].reached_targets == (2,)
    assert score1.tobytes() != score2.tobytes()
    np.testing.assert_array_equal(score2, score2_again)
    assert receipt2 == receipt2_again
    assert receipt2.receipt_sha256 == receipt2_again.receipt_sha256


def test_later_layer_trip_discards_every_partial_update_query_atomically():
    keys, query = _vectors()
    one_edge = comp.make_graph(
        ("p0", "p1", "p2"),
        (comp.EvidenceArcV1(0, 1, "s0", 0, 5, "Alpha", "alpha"),),
    )
    static = keys @ query
    final, receipt = probe.score_qkv_b1(
        query, keys, one_edge,
        probe.QKVB1PolicyV1(seed_k=1, hops=2, gamma=1.0),
        value_vectors=keys,
    )

    assert final.tobytes() == static.tobytes()
    assert receipt.layers == ()
    assert not receipt.applied
    assert receipt.trip_reason == "depth 2: no outgoing evidence arc"


def test_scorer_surface_and_receipt_are_evaluator_label_free():
    parameters = set(inspect.signature(probe.score_qkv_b1).parameters)
    assert not parameters & reval.FORBIDDEN_COMPILER_KEYS
    keys, query = _vectors()
    _, receipt = probe.score_qkv_b1(
        query, keys, _graph(),
        probe.QKVB1PolicyV1(seed_k=1, hops=2, gamma=0.2),
        value_vectors=keys,
    )
    assert receipt.evaluator_labels_seen == 0
    assert reval.find_evaluation_label_paths(asdict(receipt)) == ()


def _write_development_fixture(tmp_path):
    dataset = "musique"
    raw_paragraphs = (
        ("Alpha", "Beta appears here."),
        ("Beta", "Beta is the target paragraph."),
    )
    paragraphs = [
        {
            "source_id": prep.paragraph_source_id(dataset, title, text),
            "title": title,
            "text": text,
        }
        for title, text in raw_paragraphs
    ]
    paragraphs.sort(key=lambda item: item["source_id"])
    source_ids = [item["source_id"] for item in paragraphs]
    segment = {
        "dataset": dataset,
        "split": "development",
        "paragraphs": paragraphs,
        "evaluation_rows": [
            {
                "dataset": dataset,
                "split": "development",
                "qid": "q-exact",
                "question": "Find Beta",
                "paragraph_source_ids": source_ids,
                "gold_source_ids": [prep.paragraph_source_id(
                    dataset, "Beta", "Beta is the target paragraph.",
                )],
                "hop": 2,
            },
            {
                "dataset": dataset,
                "split": "development",
                "qid": "q-mismatch",
                "question": "Normalized question",
                "paragraph_source_ids": source_ids,
                "gold_source_ids": [prep.paragraph_source_id(
                    dataset, "Beta", "Beta is the target paragraph.",
                )],
                "hop": 2,
            },
        ],
    }
    segment_path = tmp_path / "musique_development_v4_segment.json"
    segment_path.write_text(json.dumps(segment), encoding="utf-8")

    records = []
    vector_rows = []
    basis = np.eye(3, dtype=np.float32)
    for index, paragraph in enumerate(paragraphs):
        text = f"{paragraph['title']} :: {paragraph['text']}"
        records.append((
            f"paragraph:{paragraph['source_id']}", "paragraph",
            sha256(text.encode("utf-8")).hexdigest(),
        ))
        vector_rows.append(basis[index])
    records.extend((
        (
            "query:musique:q-exact", "query",
            sha256("Find Beta".encode("utf-8")).hexdigest(),
        ),
        (
            "query:musique:q-mismatch", "query",
            sha256("Normalized question ".encode("utf-8")).hexdigest(),
        ),
        (
            "query:unused:extra", "query",
            sha256("unused".encode("utf-8")).hexdigest(),
        ),
    ))
    vector_rows.extend((basis[0], basis[1], basis[2]))
    embedding_path = tmp_path / "development_embeddings.npz"
    np.savez_compressed(
        embedding_path,
        ids=np.asarray([item[0] for item in records]),
        kinds=np.asarray([item[1] for item in records]),
        text_sha256=np.asarray([item[2] for item in records]),
        vectors=np.stack(vector_rows),
    )
    return segment_path, embedding_path


def test_development_loader_joins_by_id_hash_and_drops_mismatched_query(tmp_path):
    segment_path, embedding_path = _write_development_fixture(tmp_path)
    datasets = probe.load_development_datasets([segment_path], embedding_path)
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset.dataset == "musique"
    assert len(dataset.queries) == 1
    assert dataset.queries[0].qid == "q-exact"
    assert dataset.dropped_query_ids == ("q-mismatch",)
    assert dataset.unused_embedding_records == 1
    assert len(dataset.graph.arcs) >= 1
    assert all(arc.selector_exact for arc in dataset.graph.arcs)

    report = probe.run_development_probe(
        datasets,
        (
            probe.QKVB1PolicyV1(seed_k=1, hops=1, gamma=0.2),
            probe.QKVB1PolicyV1(seed_k=1, hops=2, gamma=0.2),
        ),
    )
    assert report["schema_version"] == probe.DEVELOPMENT_REPORT_SCHEMA_VERSION
    assert report["datasets"][0]["n_queries"] == 1
    assert report["datasets"][0]["builder"]["evaluation_labels_seen"] == 0
    assert len(report["datasets"][0]["arms"]) == 2


def test_loader_rejects_fresh_path_before_opening_it(tmp_path):
    with pytest.raises(probe.QKVB1IntegrityError, match="fresh paths"):
        probe.load_development_datasets(
            [tmp_path / "never-open-fresh-segment.json"],
            tmp_path / "also-does-not-exist.npz",
        )
    assert "fresh" not in inspect.signature(
        probe.load_development_datasets,
    ).parameters


def test_loader_rejects_non_development_split(tmp_path):
    segment_path, embedding_path = _write_development_fixture(tmp_path)
    payload = json.loads(segment_path.read_text(encoding="utf-8"))
    payload["split"] = "fresh"
    for row in payload["evaluation_rows"]:
        row["split"] = "fresh"
    neutral_path = tmp_path / "neutral_segment.json"
    neutral_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(probe.QKVB1IntegrityError, match="split=development"):
        probe.load_development_datasets([neutral_path], embedding_path)
