#!/usr/bin/env python3
"""Synthetic and algebraic tests for B2.1.  These are not benchmark evidence."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from prom_b2_crossfield_merge import (
    attach_embeddings,
    build_field,
    collect_texts,
    compose,
    merge,
    paragraphs_from_rows,
    rank_paragraphs,
    seam_arcs_between,
)
from prom_b21_learned_router import (
    ARMS,
    Query,
    assert_split_disjoint,
    choose_component_count,
    compile_scorepack,
    compare_b2_rankings,
    conformal_advantage_radius,
    directory_manifest,
    field_label,
    fit_shared_ridge,
    frozen_b2_reference,
    gold_components,
    normalize_rows,
    observable_features,
    opaque_entity,
    privatize_text,
    read_scorepack,
    recall_for,
    route_or_abstain,
    stable_pid,
    swap_fields,
    validate_scorepack,
    write_scorepack,
)


def hash_embed(texts: list[str]) -> np.ndarray:
    out = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec = np.asarray([b - 127.5 for b in digest], dtype=np.float64)
        out.append(vec / np.linalg.norm(vec))
    return np.vstack(out)


def titles_by_field(n: int = 100) -> tuple[list[str], list[str]]:
    a, b = [], []
    for i in range(n):
        title = f"T{i}"
        (a if field_label(title, "legacy") == "A" else b).append(title)
    return a, b


TA, TB = titles_by_field()


def row(rid: str, question: str, pairs: list[tuple[str, str]], support: list[str]) -> dict:
    return {"id": rid, "question": question, "answer": "AnswerName",
            "supporting_facts": {"title": support, "sent_id": [0] * len(support)},
            "context": {"title": [x[0] for x in pairs],
                        "sentences": [[x[1]] for x in pairs]}}


@pytest.fixture
def raw_rows() -> list[dict]:
    return [
        row("cross-1", "Where did Zorblax establish Blergstad?",
            [(TA[0], "Zorblax visited Mereworth."),
             (TB[0], "Zorblax established Blergstad."),
             (TA[1], "Quuxone wrote nothing."),
             (TB[1], "Quuxtwo sailed elsewhere.")], [TA[0], TB[0]]),
        row("in-a", "What did Frobnak paint?",
            [(TA[2], "Frobnak painted Vexampolis."),
             (TA[3], "Frobnak lived in Vexampolis."),
             (TB[2], "Someone Else hummed.")], [TA[2], TA[3]]),
        row("in-b", "Where did Norplex travel?",
            [(TB[3], "Norplex traveled to Deltora."),
             (TB[4], "Norplex left Deltora later."),
             (TA[4], "Unrelated Person waited.")], [TB[3], TB[4]]),
    ]


def test_musique_adapter_uses_supporting_paragraph_not_ambiguous_title():
    raw = {"rows": [{"id": "m1", "question": "Who won?", "answer": "Beta",
                     "paragraphs": [
                         {"idx": 0, "title": "Same", "paragraph_text": "Alpha lost.",
                          "is_supporting": False},
                         {"idx": 1, "title": "Same", "paragraph_text": "Beta won.",
                          "is_supporting": True}]}]}
    queries, pool = normalize_rows(raw, "musique")
    wanted = stable_pid("Same", "Beta won.")
    unwanted = stable_pid("Same", "Alpha lost.")
    assert queries[0].gold == (wanted,)
    assert wanted in pool and unwanted in pool


def test_salted_partition_is_deterministic_and_registered():
    assert field_label("Alpha", "legacy") == field_label("Alpha", "legacy")
    assert {field_label(f"Title {i}", "b21-field-v1") for i in range(50)} == {"A", "B"}
    with pytest.raises(ValueError, match="unregistered salt"):
        queries = [Query("q", "Alpha?", (), ())]
        compile_scorepack(queries, {}, hash_embed, dataset="2wiki", salt="oops")


def test_vectorized_score_compiler_matches_frozen_b2(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    pack = compile_scorepack(queries, pool, hash_embed, dataset="2wiki",
                             salt="legacy", top_k=20)

    legacy_pool = paragraphs_from_rows(raw_rows)
    fa, fb = build_field(legacy_pool, "A"), build_field(legacy_pool, "B")
    fm = merge(fa, fb, new_seam=seam_arcs_between(fa, fb))
    fn = compose([fa, fb])
    texts = collect_texts([fa, fb, fm, fn], [q.question for q in queries])
    table = dict(zip(texts, hash_embed(texts).tolist()))
    for field in (fa, fb, fm, fn):
        attach_embeddings(field, table)
    fields = {"a": fa, "b": fb, "merged": fm, "no_seam": fn}
    for qi, query in enumerate(queries):
        for arm, field in fields.items():
            expected = rank_paragraphs(field, table[query.question], top_k=20)
            got = pack["records"][qi]["arms"][arm]
            assert got["ids"] == [x[0] for x in expected]
            assert np.allclose(got["scores"], [x[1] for x in expected], atol=1e-12)
    exact = compare_b2_rankings(pack, frozen_b2_reference(raw_rows, hash_embed))
    assert exact["pass"] and exact["mismatched_ranked_id_lists"] == 0


def test_feature_schema_excludes_gold_private_and_ids(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    record = compile_scorepack(queries, pool, hash_embed, dataset="2wiki",
                               salt="legacy")["records"][0]
    _, names = observable_features(record, "a", 3)
    forbidden = ("qid", "gold", "answer", "class", "type", "support")
    assert not any(any(token in name for token in forbidden) for name in names)
    # Changing all target/private metadata leaves inference features bit-identical.
    changed = dict(record)
    changed.update({"qid": "secret", "gold": ["not-real"], "class": "in_field"})
    assert np.array_equal(observable_features(record, "a", 3)[0],
                          observable_features(changed, "a", 3)[0])


def test_field_swap_equivariance_is_structural(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    pack = compile_scorepack(queries, pool, hash_embed, dataset="2wiki", salt="legacy")
    record = pack["records"][0]
    swapped = swap_fields(record)
    assert np.allclose(observable_features(record, "a", 3)[0],
                       observable_features(swapped, "b", 3)[0])
    assert np.allclose(observable_features(record, "b", 3)[0],
                       observable_features(swapped, "a", 3)[0])
    assert np.allclose(observable_features(record, "merged", 3)[0],
                       observable_features(swapped, "merged", 3)[0])
    model = fit_shared_ridge(pack["records"], [0, 1], 3)
    radius = conformal_advantage_radius(model, pack["records"], [2], 3)
    route = route_or_abstain(model, record, 3, radius)
    swapped_route = route_or_abstain(model, swapped, 3, radius)
    mapping = {"A": "B", "B": "A", "ABSTAIN": "ABSTAIN"}
    assert swapped_route["action"] == mapping[route["action"]]


def test_abstain_executes_merged_never_oracle(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    records = compile_scorepack(queries, pool, hash_embed, dataset="2wiki",
                                salt="legacy")["records"]
    model = fit_shared_ridge(records, [0, 1], 3)
    route = route_or_abstain(model, records[2], 3, radius=1e9)
    assert route["action"] == "ABSTAIN"
    assert route["executed_action"] == "merged"
    assert recall_for(records[2], route["executed_action"], 3) == recall_for(records[2], "merged", 3)


def test_conformal_radius_and_shuffled_target_are_deterministic(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    records = compile_scorepack(queries, pool, hash_embed, dataset="2wiki",
                                salt="legacy")["records"]
    normal = fit_shared_ridge(records, [0, 1], 3)
    shuffled1 = fit_shared_ridge(records, [0, 1], 3, target_permutation=[1, 0])
    shuffled2 = fit_shared_ridge(records, [0, 1], 3, target_permutation=[1, 0])
    assert np.array_equal(shuffled1.coef, shuffled2.coef)
    assert not np.allclose(normal.coef, shuffled1.coef)
    radius = conformal_advantage_radius(normal, records, [2], 3)
    assert math.isfinite(radius)


def test_gold_component_leakage_is_rejected(raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    records = compile_scorepack(queries, pool, hash_embed, dataset="2wiki",
                                salt="legacy")["records"]
    records[1]["gold"] = list(records[0]["gold"])
    with pytest.raises(AssertionError, match="gold paragraph overlap"):
        assert_split_disjoint(records, [0], [1], [2])


def test_private_entity_surface_preserves_identity_and_removes_name():
    text = "Alice Smith met Alice Smith in London."
    private = privatize_text(text, {"alice smith", "london"})
    assert "Alice Smith" not in private and "London" not in private
    assert private.count(opaque_entity("alice smith")) == 2
    assert opaque_entity("alice smith") == opaque_entity("Alice Smith")


def test_scorepack_receipt_is_deterministic(tmp_path: Path, raw_rows):
    queries, pool = normalize_rows(raw_rows, "2wiki")
    pack = compile_scorepack(queries, pool, hash_embed, dataset="2wiki", salt="legacy")
    p1, p2 = tmp_path / "one.json.gz", tmp_path / "two.json.gz"
    m1, m2 = write_scorepack(p1, pack), write_scorepack(p2, pack)
    assert m1["sha256"] == m2["sha256"]
    assert read_scorepack(p1) == pack


def test_component_sampling_and_cluster_units_are_not_query_iid():
    records = []
    for i in range(12):
        # First six queries form one repeated-document component; the others are independent.
        gold = ["shared"] if i < 6 else [f"p{i}"]
        records.append({"qid_sha256": hashlib.sha256(str(i).encode()).hexdigest(), "gold": gold})
    assert sorted(map(len, gold_components(records, range(12))), reverse=True)[0] == 6
    chosen, remaining = choose_component_count(records, range(12), 3, 7332)
    assert not ({p for i in chosen for p in records[i]["gold"]}
                & {p for i in remaining for p in records[i]["gold"]})


def test_model_manifest_and_scorepack_reuse_fail_closed(tmp_path: Path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text('{"model":"frozen"}\n', encoding="utf-8")
    first = directory_manifest(model_dir)
    second = directory_manifest(model_dir)
    assert first["sha256"] == second["sha256"] and first["n_files"] == 1
    provenance = {"script_sha256": "s", "dataset_sha256": "d"}
    pack = {"schema": "hswm-b21-scorepack/v1", "dataset": "2wiki", "salt": "legacy",
            "condition": "base", "top_k": 20, "model": "all-MiniLM-L6-v2",
            "cohort": "full_closed_corpus", "provenance": provenance}
    validate_scorepack(pack, dataset="2wiki", salt="legacy", condition="base",
                       cohort="full_closed_corpus", provenance=provenance)
    with pytest.raises(RuntimeError, match="salt mismatch"):
        validate_scorepack(pack, dataset="2wiki", salt="b21-field-v1", condition="base",
                           cohort="full_closed_corpus", provenance=provenance)
