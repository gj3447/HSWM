"""Fresh H3/B3 holdout teeth: deterministic selection and zero QA leakage."""
from __future__ import annotations

from hashlib import sha256
import builtins
import json

import pytest

import h3_fresh_manifest as fresh
import relation_eval as reval
from world_ir import canonical_json


def _musique_row(
    qid: str,
    relations: tuple[str, ...],
    *,
    evidence_prefix: str | None = None,
    first_support: tuple[str, str] | None = None,
) -> dict:
    prefix = evidence_prefix or qid
    paragraphs = []
    decomposition = []
    for ordinal, relation in enumerate(relations):
        title = f"{prefix} Title {ordinal}"
        text = f"{prefix} exact evidence {ordinal}."
        if ordinal == 0 and first_support is not None:
            title, text = first_support
        paragraphs.append({
            "idx": ordinal,
            "title": title,
            "paragraph_text": text,
            "is_supporting": True,
        })
        subject = title if ordinal == 0 else f"#{ordinal}"
        decomposition.append({
            "id": ordinal + 1,
            "question": f"{subject} >> {relation}",
            "answer": f"{prefix} Answer {ordinal}",
            "paragraph_support_idx": ordinal,
        })
    return {
        "id": qid,
        "question": f"Question for {qid}?",
        "answer": f"{prefix} Answer {len(relations) - 1}",
        "paragraphs": paragraphs,
        "question_decomposition": decomposition,
        "answerable": True,
    }


def _wiki_row(
    qid: str,
    triples: tuple[tuple[str, str, str], ...],
    *,
    qtype: str = "compositional",
    struct_context: bool = False,
) -> dict:
    titles = []
    sentences = []
    for ordinal, (subject, relation, object_) in enumerate(triples):
        titles.append(subject)
        sentences.append([f"{subject} {relation} {object_}."])
    context = (
        {"title": titles, "sentences": sentences}
        if struct_context else list(zip(titles, sentences, strict=True))
    )
    return {
        "id": qid,
        "question": f"Question for {qid}?",
        "answer": triples[-1][2],
        "type": qtype,
        "evidences": [list(item) for item in triples],
        "supporting_facts": [[title, 0] for title in titles],
        "context": context,
    }


def test_musique_excludes_prior_qid_template_and_exact_evidence_then_selects_by_hash():
    prior = _musique_row("prior", ("director", "birthplace"))
    prior_first = (
        prior["paragraphs"][0]["title"],
        prior["paragraphs"][0]["paragraph_text"],
    )
    same_template = _musique_row("same-template", ("director", "birthplace"))
    same_evidence = _musique_row(
        "same-evidence", ("painter", "country"), first_support=prior_first,
    )
    eligible = [
        _musique_row("eligible-z", ("producer", "nationality")),
        _musique_row("eligible-a", ("composer", "occupation")),
        _musique_row("eligible-three", ("author", "spouse", "country")),
    ]
    rows = [prior, same_template, same_evidence, *eligible]
    manifest = fresh.build_fresh_holdout_manifest(
        "musique", rows, ["prior"], quotas={2: 1, 3: 1},
    )

    expected_hop2 = min(
        ("eligible-z", "eligible-a"),
        key=lambda qid: sha256(
            f"{fresh.SELECTION_SEED}|musique|{qid}".encode()
        ).hexdigest(),
    )
    assert manifest.selected_qids == (expected_hop2, "eligible-three")
    assert manifest.counts.excluded_prior_qid == 1
    assert manifest.counts.excluded_prior_template >= 2  # prior + same-template
    assert manifest.counts.excluded_prior_evidence >= 2  # prior + same-evidence
    assert manifest.counts.eligible_by_hop == ((2, 2), (3, 1))
    assert manifest.audit.all_disjoint
    assert set(manifest.selected_qids).isdisjoint({
        "prior", "same-template", "same-evidence",
    })


def test_2wiki_filters_exact_triple_overlap_and_emits_context_without_labels():
    prior_triples = (("Nia", "father", "Omar"), ("Omar", "born in", "Pune"))
    prior = _wiki_row("prior-w", prior_triples)
    same_template = _wiki_row(
        "template-w", (("Tao", "father", "Sora"), ("Sora", "born in", "Busan")),
    )
    same_triple = _wiki_row(
        "evidence-w", (prior_triples[0], ("Omar", "occupation", "Teacher")),
    )
    eligible2 = _wiki_row(
        "eligible-w2", (("Ada", "spouse", "Bea"), ("Bea", "country", "Italy")),
        struct_context=True,
    )
    eligible2["context"]["title"].append("Distractor")
    eligible2["context"]["sentences"].append(["Distractor mentions nobody."])
    eligible4 = _wiki_row(
        "eligible-w4",
        (("A", "r1", "B"), ("B", "r2", "C"),
         ("C", "r3", "D"), ("D", "r4", "E")),
        qtype="bridge_comparison",
    )
    manifest = fresh.build_fresh_holdout_manifest(
        "2wiki", [prior, same_template, same_triple, eligible2, eligible4],
        ["prior-w"], quotas={2: 1, 4: 1},
    )

    assert manifest.selected_qids == ("eligible-w2", "eligible-w4")
    assert manifest.audit.exact_evidence_disjoint
    payload = fresh.compiler_payload(manifest)
    assert reval.find_evaluation_label_paths(payload) == ()
    assert all(set(item) == {"source_id", "title", "text"}
               for item in payload["paragraphs"])
    assert all(set(item) == {"row_id", "paragraph_source_ids"}
               for item in payload["rows"])
    assert any(paragraph["text"] == "Ada spouse Bea."
               for paragraph in payload["paragraphs"])
    sidecar = fresh.evaluator_payload(manifest)
    assert sidecar["schema_version"] == "hswm-h3-evaluator-sidecar/v2"
    assert sidecar["raw_source_sha256"] == manifest.raw_source_sha256
    assert sidecar["selected_manifest_sha256"] == manifest.selected_manifest_sha256
    assert reval.find_evaluation_label_paths(sidecar)
    assert set(sidecar["bindings"][0]) == {
        "binding_id", "row_id", "raw_row_sha256", "paragraph_source_ids",
        "gold_source_ids", "benchmark_hop", "example",
    }

    binding = next(
        item for item in manifest.evaluator_sidecar
        if item.example.qid == "eligible-w2"
    )
    compiler_row = next(
        item for item in manifest.compiler_rows if item.row_id == binding.row_id
    )
    assert binding.paragraph_source_ids == compiler_row.paragraph_source_ids
    assert len(binding.paragraph_source_ids) == 3
    assert len(binding.gold_source_ids) == 2
    assert set(binding.gold_source_ids) < set(binding.paragraph_source_ids)
    assert binding.raw_row_sha256 == binding.example.raw_row_sha256


def test_raw_support_labels_derive_gold_and_bind_row_identity_without_segment_input():
    row = _musique_row("eligible", ("composer", "country"))
    row["paragraphs"].append({
        "idx": 99,
        "title": "Distractor Title",
        "paragraph_text": "Distractor text.",
        "is_supporting": False,
    })

    compiler_row, paragraphs, binding = fresh.derive_row_label_provenance(
        "musique", row,
    )
    assert compiler_row.paragraph_source_ids == tuple(
        item.source_id for item in paragraphs
    )
    assert binding.row_id == compiler_row.row_id
    assert binding.paragraph_source_ids == compiler_row.paragraph_source_ids
    assert binding.gold_source_ids == tuple(
        item.source_id for item in paragraphs[:2]
    )
    assert paragraphs[2].source_id not in binding.gold_source_ids
    assert binding.raw_row_sha256 == sha256(canonical_json(row).encode()).hexdigest()
    assert binding.raw_row_sha256 == binding.example.raw_row_sha256
    assert binding.binding_id == fresh._evaluator_binding_id(
        dataset="musique", row_id=binding.row_id,
        raw_row_sha256=binding.raw_row_sha256,
        paragraph_source_ids=binding.paragraph_source_ids,
        gold_source_ids=binding.gold_source_ids,
        benchmark_hop=binding.benchmark_hop,
        occurrence_id=binding.example.occurrence_id,
    )


def test_inconsistent_or_favorable_raw_gold_labels_fail_before_manifest_creation():
    prior = _musique_row("prior", ("a", "b"))
    inconsistent = _musique_row("inconsistent", ("c", "d"))
    # A favorable sidecar could try to drop a difficult gold paragraph, but
    # the independent decomposition labels still point to it.
    inconsistent["paragraphs"][1]["is_supporting"] = False
    with pytest.raises(fresh.FreshManifestError, match="support labels disagree"):
        fresh.build_fresh_holdout_manifest(
            "musique", [prior, inconsistent], ["prior"], quotas={2: 1},
        )

    wiki = _wiki_row(
        "wiki", (("Ada", "spouse", "Bea"), ("Bea", "country", "Italy")),
    )
    wiki["supporting_facts"][0][1] = 99
    with pytest.raises(fresh.FreshManifestError, match="out of range"):
        fresh.derive_row_label_provenance("2wiki", wiki)


def test_raw_row_mutation_changes_row_and_binding_ids_even_when_candidates_do_not():
    original = _musique_row("same-qid", ("composer", "country"))
    mutated = json.loads(json.dumps(original))
    mutated["question"] = "A differently worded evaluation question?"

    first_row, first_paragraphs, first_binding = fresh.derive_row_label_provenance(
        "musique", original,
    )
    second_row, second_paragraphs, second_binding = fresh.derive_row_label_provenance(
        "musique", mutated,
    )
    assert first_paragraphs == second_paragraphs
    assert first_binding.gold_source_ids == second_binding.gold_source_ids
    assert first_binding.raw_row_sha256 != second_binding.raw_row_sha256
    assert first_row.row_id != second_row.row_id
    assert first_binding.binding_id != second_binding.binding_id


def test_manifest_is_repeatable_and_raw_order_cannot_change_selection():
    rows = [
        _musique_row("prior", ("r0", "r1")),
        _musique_row("one", ("a0", "a1")),
        _musique_row("two", ("b0", "b1")),
        _musique_row("three", ("c0", "c1")),
    ]
    first = fresh.build_fresh_holdout_manifest(
        "musique", rows, ["prior"], quotas={2: 2},
    )
    again = fresh.build_fresh_holdout_manifest(
        "musique", rows, ["prior"], quotas={2: 2},
    )
    reversed_source = fresh.build_fresh_holdout_manifest(
        "musique", list(reversed(rows)), ["prior"], quotas={2: 2},
    )

    assert first == again
    assert first.selected_manifest_sha256 == again.selected_manifest_sha256
    assert first.selected_qids == reversed_source.selected_qids
    assert first.raw_source_sha256 != reversed_source.raw_source_sha256
    assert first.selected_manifest_sha256 != reversed_source.selected_manifest_sha256


def test_prior_qid_hash_is_sorted_and_missing_prior_fails_closed():
    rows = [
        _musique_row("p-a", ("a", "b")),
        _musique_row("p-z", ("c", "d")),
        _musique_row("eligible", ("e", "f")),
    ]
    manifest = fresh.build_fresh_holdout_manifest(
        "musique", rows, ["p-z", "p-a"], quotas={2: 1},
    )
    expected = sha256(canonical_json(("p-a", "p-z")).encode()).hexdigest()
    assert manifest.prior_qids == ("p-a", "p-z")
    assert manifest.prior_qid_sha256 == expected

    with pytest.raises(fresh.FreshManifestError, match="missing 1 prior B1 qids"):
        fresh.build_fresh_holdout_manifest(
            "musique", rows, ["not-in-source"], quotas={2: 1},
        )


def test_quota_unavailable_fails_before_a_partial_manifest_can_escape():
    rows = [
        _musique_row("prior", ("a", "b")),
        _musique_row("eligible", ("c", "d")),
    ]
    with pytest.raises(fresh.FreshManifestError, match="quota 2 unavailable"):
        fresh.build_fresh_holdout_manifest(
            "musique", rows, ["prior"], quotas={2: 2},
        )


def test_prior_b1_sampler_reproduces_hop_round_robin_and_checks_capacity():
    pool = [
        {"id": "m2-a", "hop": "2hop", "paragraphs": []},
        {"id": "m2-b", "hop": "2hop", "paragraphs": []},
        {"id": "m3-a", "hop": "3hop1", "paragraphs": []},
        {"id": "m3-b", "hop": "3hop2", "paragraphs": []},
    ]
    assert fresh.derive_prior_b1_qids(pool, n_rows=4) == (
        "m2-a", "m3-a", "m2-b", "m3-b",
    )
    with pytest.raises(fresh.FreshManifestError, match="requested 5"):
        fresh.derive_prior_b1_qids(pool, n_rows=5)


def test_json_loader_verifies_declared_canonical_rows_digest(tmp_path):
    rows = [_musique_row("a", ("x", "y"))]
    digest = sha256(canonical_json(tuple(rows)).encode()).hexdigest()
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"rows_sha256": digest, "rows": rows}), encoding="utf-8")
    loaded, file_sha = fresh.load_json_rows(good)
    assert loaded == tuple(rows)
    assert len(file_sha) == 64

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"rows_sha256": "0" * 64, "rows": rows}), encoding="utf-8")
    with pytest.raises(fresh.FreshManifestError, match="declared rows_sha256 mismatch"):
        fresh.load_json_rows(bad)


def test_parquet_dependency_error_is_explicit(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("pyarrow"):
            raise ImportError("blocked in test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(fresh.FreshManifestError, match="requires optional dependency pyarrow"):
        fresh.load_2wiki_parquet(tmp_path / "rows.parquet")


def test_canonical_writer_preserves_bound_manifest_sha(tmp_path):
    rows = [
        _musique_row("prior", ("a", "b")),
        _musique_row("eligible", ("c", "d")),
    ]
    manifest = fresh.build_fresh_holdout_manifest(
        "musique", rows, ["prior"], quotas={2: 1},
    )
    path = tmp_path / "manifest.json"
    fresh.write_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["selected_manifest_sha256"] == manifest.selected_manifest_sha256
    assert path.read_text(encoding="utf-8") == canonical_json(manifest) + "\n"
