"""H3 evaluation teeth: real labels stay evaluator-only and split leakage-free."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

import relation_eval as reval


def _musique_row(qid: str, entity: str, bridge: str, answer: str,
                 first_question: str = "Who directed {entity}?",
                 second_question: str = "Where was #1 born?") -> dict:
    paragraphs = [
        {"idx": 0, "title": entity,
         "paragraph_text": f"{entity} was directed by {bridge}.", "is_supporting": True},
        {"idx": 1, "title": bridge,
         "paragraph_text": f"{bridge} was born in {answer}.", "is_supporting": True},
    ]
    return {
        "id": qid,
        "question": f"Where was the director of {entity} born?",
        "answer": answer,
        "paragraphs": paragraphs,
        "question_decomposition": [
            {"id": 1, "question": first_question.format(entity=entity),
             "answer": bridge, "paragraph_support_idx": 0},
            {"id": 2, "question": second_question,
             "answer": answer, "paragraph_support_idx": 1},
        ],
    }


def _wiki_row(qid: str, person: str, parent: str, place: str,
              rel2: str = "place of birth", shared_context: str | None = None) -> dict:
    parent_sentence = shared_context or f"{parent} was born in {place}."
    return {
        "_id": qid,
        "question": f"Where was the father of {person} born?",
        "answer": place,
        "type": "compositional",
        "evidences": [[person, "father", parent], [parent, rel2, place]],
        "supporting_facts": [[person, 0], [parent, 0]],
        "context": [
            [person, [f"{person}'s father was {parent}."]],
            [parent, [parent_sentence]],
        ],
    }


def test_musique_recovers_dependency_chain_but_redacts_entities_from_template():
    row = _musique_row("2hop__a", "Cobalt Film", "Ari Noor", "Lima")
    example = reval.normalize_musique_row(row)

    assert example.dataset == "musique"
    assert example.hop == 2
    assert example.steps[1].dependencies == ("1",)
    assert example.relation_chain == (
        "who directed <entity>?",
        "where was <dep> born?",
    )
    serialized_template = " ".join(example.relation_chain)
    assert "cobalt" not in serialized_template
    assert "ari noor" not in serialized_template
    assert "lima" not in serialized_template
    assert len(example.evidence_content_ids) == 2


def test_musique_accepts_hf_struct_of_lists_and_embedded_support_paragraphs():
    row = {
        "id": "2hop__hf",
        "question": "Where was the director born?",
        "answer": "Oslo",
        "question_decomposition": {
            "id": [1, 2],
            "question": ["Who directed North Light?", "Where was #1 born?"],
            "answer": ["Rae Kim", "Oslo"],
            "paragraph_support_idx": [0, 1],
            "support_paragraph": [
                {"idx": 0, "title": "North Light",
                 "paragraph_text": "North Light was directed by Rae Kim.",
                 "is_supporting": True},
                {"idx": 1, "title": "Rae Kim",
                 "paragraph_text": "Rae Kim was born in Oslo.",
                 "is_supporting": True},
            ],
        },
    }
    example = reval.normalize_musique_row(row)
    assert example.hop == 2
    assert example.steps[0].evidence_content_ids
    assert example.steps[1].dependencies == ("1",)


def test_musique_native_notation_uses_positional_refs_not_raw_step_ids():
    row = {
        "id": "2hop__native",
        "question": "Who is the spouse of the Green performer?",
        "answer": "Miquette Giraudy",
        "paragraphs": [
            {"idx": 10, "title": "Green", "paragraph_text": "Green performer text."},
            {"idx": 5, "title": "Steve Hillage", "paragraph_text": "Spouse text."},
        ],
        "question_decomposition": [
            {"id": 460946, "question": "Green >> performer",
             "answer": "Steve Hillage", "paragraph_support_idx": 10},
            {"id": 294723, "question": "#1 >> spouse",
             "answer": "Miquette Giraudy", "paragraph_support_idx": 5},
        ],
    }
    example = reval.normalize_musique_row(row)
    assert example.steps[1].dependencies == ("460946",)
    assert example.relation_chain == (
        "<entity> >> performer",
        "<dep> >> spouse",
    )


def test_2wiki_recovers_ordered_relations_and_entity_invariant_template():
    a = reval.normalize_2wiki_row(_wiki_row("wa", "Nia", "Omar", "Pune"))
    b = reval.normalize_2wiki_row(_wiki_row("wb", "Tao", "Sora", "Busan"))

    assert a.relation_chain == ("father", "place of birth")
    assert [step.dependencies for step in a.steps] == [(), ("0",)]
    assert a.relation_template_id == b.relation_template_id
    assert a.relation_chain_id == b.relation_chain_id
    assert a.steps[0].relation_template == "v0-[father]->v1"
    assert a.steps[1].relation_template == "v1-[place of birth]->v2"
    assert len(a.evidence_content_ids) == 4  # two triples + two supporting paragraphs


def test_2wiki_accepts_hf_evidence_and_context_columns():
    row = _wiki_row("hf", "Nia", "Omar", "Pune")
    row["evidences"] = {
        "fact": ["Nia", "Omar"],
        "relation": ["father", "place of birth"],
        "entity": ["Omar", "Pune"],
    }
    row["context"] = {
        "title": ["Nia", "Omar"],
        "sentences": [["Nia's father was Omar."], ["Omar was born in Pune."]],
    }
    row["supporting_facts"] = {"title": ["Nia", "Omar"], "sent_id": [0, 0]}
    example = reval.normalize_2wiki_row(row)
    assert example.relation_chain == ("father", "place of birth")
    assert example.hop == 2


def test_union_split_is_template_and_evidence_disjoint_transitively_and_deterministic():
    # A/B share a relation template. B/C use different templates but share an
    # exact supporting paragraph, so A/B/C must become one transitive component.
    rows = [
        _wiki_row("a", "Nia", "Omar", "Pune", shared_context="Shared exact evidence."),
        _wiki_row("b", "Tao", "Sora", "Busan", shared_context="Shared exact evidence."),
        _wiki_row("c", "Ivo", "Omar", "Pune", rel2="country",
                  shared_context="Shared exact evidence."),
        _wiki_row("d", "Uma", "Pax", "Rome", rel2="occupation"),
        _wiki_row("e", "Eli", "Zed", "Bern", rel2="educated at"),
    ]
    examples = tuple(reval.normalize_2wiki_row(row) for row in rows)
    one = reval.split_relation_examples(examples, seed=19)
    two = reval.split_relation_examples(tuple(reversed(examples)), seed=19)
    by_id_one = {item.occurrence_id: (item.split, item.component_id) for item in one}
    by_id_two = {item.occurrence_id: (item.split, item.component_id) for item in two}
    assert by_id_one == by_id_two

    abc = [by_id_one[examples[index].occurrence_id] for index in range(3)]
    assert len(set(abc)) == 1
    assert {item.split for item in one} == {"val", "test"}

    split_by_occurrence = {item.occurrence_id: item.split for item in one}
    templates: dict[str, set[str]] = {}
    evidences: dict[str, set[str]] = {}
    for example in examples:
        split = split_by_occurrence[example.occurrence_id]
        templates.setdefault(example.relation_template_id, set()).add(split)
        for evidence_id in example.evidence_content_ids:
            evidences.setdefault(evidence_id, set()).add(split)
    assert all(len(splits) == 1 for splits in templates.values())
    assert all(len(splits) == 1 for splits in evidences.values())


def test_evidence_overlap_is_exact_not_whitespace_normalized():
    a = reval.normalize_2wiki_row(
        _wiki_row("exact-a", "Nia", "Omar", "Pune", shared_context="Same text."))
    b = reval.normalize_2wiki_row(
        _wiki_row("exact-b", "Ivo", "Omar", "Pune", rel2="country",
                  shared_context="Same  text."))
    assert set(a.evidence_content_ids).isdisjoint(set(b.evidence_content_ids))


def test_suite_binds_raw_snapshot_and_is_self_consistent():
    rows = [
        _musique_row("m1", "Blue Film", "Ada Roe", "Paris"),
        _musique_row("m2", "Red Film", "Bea Poe", "Rome",
                      first_question="Who produced {entity}?"),
    ]
    suite = reval.build_relation_evaluation_suite("musique", rows, seed=7)
    assert suite.schema_version == reval.SCHEMA_VERSION
    assert len(suite.raw_snapshot_sha256) == 64
    assert suite.suite_id.startswith("hswm:relation_eval_suite:v1:")
    assert len(suite.assignments) == len(suite.examples) == 2
    assert all(suite.split_for(example.occurrence_id) in {"val", "test"}
               for example in suite.examples)


@dataclass(frozen=True)
class _AccidentalCompilerEnvelope:
    sources: tuple[dict, ...]
    question_decomposition: tuple[dict, ...]


def test_compiler_payload_guard_reports_nested_mapping_and_dataclass_paths():
    mapping_payload = {
        "sources": [{"content": "safe"}],
        "observations": {"items": [{"question": "leak", "answer": "leak"}]},
    }
    assert reval.find_evaluation_label_paths(mapping_payload) == (
        "observations.items[0].answer",
        "observations.items[0].question",
    )
    with pytest.raises(reval.EvaluationLabelLeakageError) as caught:
        reval.assert_compiler_payload_clean(mapping_payload)
    assert caught.value.paths == reval.find_evaluation_label_paths(mapping_payload)

    envelope = _AccidentalCompilerEnvelope(({"content": "safe"},), ({"id": 1},))
    with pytest.raises(reval.EvaluationLabelLeakageError) as caught_dataclass:
        reval.assert_compiler_payload_clean(envelope)
    assert caught_dataclass.value.paths == ("question_decomposition",)


def test_compiler_payload_guard_accepts_evidence_only_records():
    reval.assert_compiler_payload_clean({
        "sources": [{"locator": "fixture://a", "content": "A met B."}],
        "observations": [{"surface": "A", "producer": "fixture"}],
    })


@pytest.mark.parametrize(
    "forbidden_key",
    ("question", "answer", "is_supporting", "hop", "evidences",
     "question_decomposition"),
)
def test_every_required_qa_only_key_is_rejected(forbidden_key):
    with pytest.raises(reval.EvaluationLabelLeakageError) as caught:
        reval.assert_compiler_payload_clean({"nested": [{forbidden_key: "leak"}]})
    assert caught.value.paths == (f"nested[0].{forbidden_key}",)


@pytest.mark.parametrize(
    "bad_row,needle",
    [
        ({"id": "m", "question": "q", "answer": "a",
          "question_decomposition": []}, "must not be empty"),
        ({"_id": "w", "question": "q", "answer": "a",
          "evidences": [["s", "r"]]}, "3-item"),
    ],
)
def test_malformed_labels_fail_closed(bad_row, needle):
    normalizer = (reval.normalize_musique_row
                  if "question_decomposition" in bad_row else reval.normalize_2wiki_row)
    with pytest.raises(reval.RelationEvaluationError, match=needle):
        normalizer(bad_row)
