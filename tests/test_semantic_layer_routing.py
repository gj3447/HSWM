"""Semantic-layer QKV teeth: changing types, arities, and branch meaning."""
from __future__ import annotations

from dataclasses import fields, replace

import pytest

import qkv_routing as qkv
import semantic_layer_routing as semantic


def _fact(
    fact_id: str,
    subject: str,
    subject_type: str,
    predicate: str,
    object_: str,
    object_type: str,
) -> semantic.TypedFactV1:
    source_id = f"source:{fact_id}"
    source_text = f"{subject} {predicate} {object_}."
    return semantic.TypedFactV1(
        fact_id=fact_id,
        source_id=source_id,
        subject_id=subject,
        subject_type=subject_type,
        predicate=predicate,
        object_id=object_,
        object_type=object_type,
        subject_selector=qkv.bind_exact_selector(source_id, source_text, subject),
        predicate_selector=qkv.bind_exact_selector(source_id, source_text, predicate),
        object_selector=qkv.bind_exact_selector(source_id, source_text, object_),
    )


def _facts(
    *,
    swapped_dates: bool = False,
    tied_dates: bool = False,
    old_city: str = "Oldtown",
    young_city: str = "Youngtown",
) -> tuple[semantic.TypedFactV1, ...]:
    old_date, young_date = "1900-01-02", "2000-03-04"
    if swapped_dates:
        old_date, young_date = young_date, old_date
    if tied_dates:
        young_date = old_date
    return (
        _fact("parent-child-avery", "Morgan", semantic.PERSON,
              "child", "Avery", semantic.PERSON),
        _fact("parent-child-blake", "Morgan", semantic.PERSON,
              "child", "Blake", semantic.PERSON),
        _fact("avery-date", "Avery", semantic.PERSON,
              "birth_date", old_date, semantic.DATE),
        _fact("blake-date", "Blake", semantic.PERSON,
              "birth_date", young_date, semantic.DATE),
        _fact("avery-city", "Avery", semantic.PERSON,
              "birthplace", old_city, semantic.CITY),
        _fact("blake-city", "Blake", semantic.PERSON,
              "birthplace", young_city, semantic.CITY),
    )


def _run(
    facts: tuple[semantic.TypedFactV1, ...], *, reducer: str = "ARGMIN",
    static: bytes = b"static-floor\x00payload",
):
    return semantic.execute_semantic_layers(
        semantic.make_semantic_memory(facts),
        semantic.make_semantic_program("Morgan", reducer=reducer),
        static_payload=static,
    )


@pytest.mark.parametrize(
    ("swapped", "reducer", "terminal"),
    (
        (False, "ARGMIN", b"Oldtown"),
        (False, "ARGMAX", b"Youngtown"),
        (True, "ARGMIN", b"Youngtown"),
        (True, "ARGMAX", b"Oldtown"),
    ),
)
def test_old_young_date_key_pairs_select_bound_person_value(
    swapped: bool, reducer: str, terminal: bytes,
):
    payload, receipt = _run(_facts(swapped_dates=swapped), reducer=reducer)

    assert payload == terminal
    assert receipt.status == "PASS"
    assert receipt.terminal_type == semantic.CITY
    assert receipt.terminal_value_id == terminal.decode()
    reduce_step = receipt.steps[2]
    assert reduce_step.operator == "REDUCE_SELECT"
    assert {pair.person_value for pair in reduce_step.reducer_pairs} == {
        "Avery", "Blake",
    }
    assert sum(pair.selected for pair in reduce_step.reducer_pairs) == 1
    selected = next(pair for pair in reduce_step.reducer_pairs if pair.selected)
    expected_person = {
        b"Oldtown": "Avery",
        b"Youngtown": "Blake",
    }[terminal]
    assert selected.person_value == expected_person


def test_receipt_preserves_branch_ids_lineage_type_arity_and_hash_chain():
    _, receipt = _run(_facts())
    assert [step.operator for step in receipt.steps] == [
        "EXPAND", "MAP_ONE", "REDUCE_SELECT", "LOOKUP_ONE",
    ]
    assert [(step.input_type, step.output_type) for step in receipt.steps] == [
        (semantic.PERSON, semantic.BRANCH_SET_PERSON),
        (semantic.BRANCH_SET_PERSON, semantic.BRANCH_SET_PERSON_DATE),
        (semantic.BRANCH_SET_PERSON_DATE, semantic.SELECTED_PERSON),
        (semantic.SELECTED_PERSON, semantic.CITY),
    ]
    assert [(step.input_arity, step.output_arity) for step in receipt.steps] == [
        ("ONE", "MANY"), ("MANY", "MANY"),
        ("MANY", "ONE"), ("ONE", "ONE"),
    ]
    assert [(step.input_count, step.output_count) for step in receipt.steps] == [
        (1, 2), (2, 2), (2, 1), (1, 1),
    ]

    expand_ids = {item.branch_id for item in receipt.steps[0].branch_lineage}
    map_ids = {item.branch_id for item in receipt.steps[1].branch_lineage}
    reduce_ids = {item.branch_id for item in receipt.steps[2].reducer_pairs}
    assert expand_ids == map_ids == reduce_ids
    assert all(item.date_fact_id is None for item in receipt.steps[0].branch_lineage)
    assert all(item.date_fact_id for item in receipt.steps[1].branch_lineage)
    assert len(receipt.steps[0].evidence_facts) == 2
    assert len(receipt.steps[1].evidence_facts) == 2
    assert receipt.steps[2].evidence_facts == ()
    assert len(receipt.steps[3].evidence_facts) == 1
    for step in (receipt.steps[0], receipt.steps[1], receipt.steps[3]):
        for evidence in step.evidence_facts:
            assert evidence.subject_selector.source_id == evidence.predicate_selector.source_id
            assert evidence.predicate_selector.source_id == evidence.object_selector.source_id
            assert evidence.subject_selector.source_text_sha256 == (
                evidence.object_selector.source_text_sha256
            )
    for left, right in zip(receipt.steps, receipt.steps[1:]):
        assert right.previous_step_sha256 == left.step_sha256
        assert right.input_state_sha256 == left.output_state_sha256


def _assert_atomic_refusal(
    facts: tuple[semantic.TypedFactV1, ...], expected_code: str,
    *, program: semantic.SemanticProgramV1 | None = None,
):
    static = bytes(bytearray(b"opaque-static\x00bytes"))
    memory = semantic.make_semantic_memory(facts)
    route = program or semantic.make_semantic_program("Morgan")
    payload, receipt = semantic.execute_semantic_layers(
        memory, route, static_payload=static,
    )
    assert payload is static
    assert payload == static
    assert receipt.status == "REFUSED"
    assert receipt.refusal_code == expected_code
    assert receipt.steps == ()
    assert receipt.terminal_type is None
    assert receipt.terminal_value_id is None
    assert receipt.static_payload_sha256 == receipt.final_payload_sha256
    return receipt


def test_type_null_refuses_instead_of_softly_scoring_wrong_value_type():
    facts = tuple(
        replace(item, object_type=semantic.CITY)
        if item.fact_id == "avery-date" else item
        for item in _facts()
    )
    receipt = _assert_atomic_refusal(facts, "TYPE_MISMATCH")
    assert receipt.refusal_layer_id == "map-birth-date"


def test_relation_key_null_and_ambiguous_key_each_refuse_atomically():
    key_null = tuple(
        item for item in _facts() if item.fact_id != "avery-date"
    ) + (_fact("avery-death-date", "Avery", semantic.PERSON,
               "death_date", "1900-01-02", semantic.DATE),)
    _assert_atomic_refusal(key_null, "NO_KEY_MATCH")

    ambiguous = _facts() + (
        _fact("avery-date-second", "Avery", semantic.PERSON,
              "birth_date", "1901-01-02", semantic.DATE),
    )
    _assert_atomic_refusal(ambiguous, "AMBIGUOUS_KEY_MATCH")


def test_value_and_reducer_nulls_have_teeth_without_changing_topology():
    base_payload, base = _run(_facts(), reducer="ARGMIN")
    value_payload, value_null = _run(
        _facts(old_city="Youngtown", young_city="Oldtown"), reducer="ARGMIN",
    )
    reducer_payload, reducer_null = _run(_facts(), reducer="ARGMAX")

    assert base_payload == b"Oldtown"
    assert value_payload == reducer_payload == b"Youngtown"
    assert base.steps[2].selected_branch_id == value_null.steps[2].selected_branch_id
    assert base.steps[2].selected_branch_id != reducer_null.steps[2].selected_branch_id
    assert base.steps[0].output_count == value_null.steps[0].output_count == 2


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        ("order", "LAYER_ORDER_MISMATCH"),
        ("type", "TYPE_MISMATCH"),
        ("arity", "ARITY_MISMATCH"),
        ("reducer", "INVALID_REDUCER"),
    ),
)
def test_layer_contract_mismatch_refuses_before_any_layer(
    mutation: str, code: str,
):
    base = semantic.make_semantic_program("Morgan")
    layers = list(base.layers)
    if mutation == "order":
        layers[0], layers[1] = layers[1], layers[0]
    elif mutation == "type":
        layers[1] = replace(layers[1], output_type=semantic.CITY)
    elif mutation == "arity":
        layers[2] = replace(layers[2], input_arity="ONE")
    else:
        layers[2] = replace(layers[2], reducer="MEDIAN")
    program = semantic.SemanticProgramV1("Morgan", tuple(layers))
    _assert_atomic_refusal(_facts(), code, program=program)


def test_missing_duplicate_and_tied_branches_refuse_without_partial_steps():
    missing = tuple(
        item for item in _facts() if item.fact_id != "parent-child-blake"
    )
    _assert_atomic_refusal(missing, "MISSING_BRANCH")

    duplicate = _facts() + (
        _fact("parent-child-avery-again", "Morgan", semantic.PERSON,
              "child", "Avery", semantic.PERSON),
    )
    _assert_atomic_refusal(duplicate, "AMBIGUOUS_BRANCH")
    _assert_atomic_refusal(_facts(tied_dates=True), "TIED_REDUCER_KEY")


def test_late_missing_birthplace_still_discards_all_partial_receipts():
    facts = tuple(item for item in _facts() if item.fact_id != "avery-city")
    receipt = _assert_atomic_refusal(facts, "NO_KEY_MATCH")
    assert receipt.refusal_layer_id == "lookup-birthplace"


def test_branch_erasure_builds_a_hashed_unbound_state_for_the_same_reducer():
    static = b"static-branch-erasure-floor"
    payload, receipt = semantic.execute_semantic_layers(
        semantic.make_semantic_memory(_facts()),
        semantic.make_semantic_program("Morgan"),
        static_payload=static,
        control="BRANCH_ERASURE",
    )

    assert payload == static
    assert receipt.status == "REFUSED"
    assert receipt.control == "BRANCH_ERASURE"
    assert receipt.refusal_code == "MISSING_BRANCH_ASSOCIATION"
    assert receipt.refusal_layer_id == "reduce-date"
    assert receipt.steps == ()
    assert receipt.ablation_state_type == semantic.BRANCH_SET_PERSON_DATE_ERASED
    assert len(receipt.ablation_state_sha256 or "") == 64


def test_memory_input_order_and_repeated_runs_are_receipt_deterministic():
    facts = _facts()
    forward = semantic.make_semantic_memory(facts)
    reverse = semantic.make_semantic_memory(tuple(reversed(facts)))
    program = semantic.make_semantic_program("Morgan")

    assert forward == reverse
    first = semantic.execute_semantic_layers(
        forward, program, static_payload=b"floor",
    )
    again = semantic.execute_semantic_layers(
        forward, program, static_payload=b"floor",
    )
    reordered = semantic.execute_semantic_layers(
        reverse, program, static_payload=b"floor",
    )
    assert first == again == reordered
    assert first[1].receipt_sha256 == reordered[1].receipt_sha256


def test_fact_selectors_must_bind_one_exact_source_preimage():
    local = _facts()[0]
    alien = _facts()[1].object_selector
    with pytest.raises(semantic.SemanticIntegrityError, match="source_id"):
        replace(local, object_selector=alien)


def test_core_program_schema_contains_no_evaluator_supervision_field_names():
    forbidden = {"answer", "gold", "label", "support", "hop", "qid"}
    names = {field.name.casefold() for field in fields(semantic.SemanticProgramV1)}
    names |= {field.name.casefold() for field in fields(semantic.SemanticLayerV1)}
    assert names.isdisjoint(forbidden)
