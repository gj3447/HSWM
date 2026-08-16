"""Exhaustive teeth for heterogeneous, branch-preserving semantic layers.

The fixture distinguishes a typed semantic stack from the two deliberately
narrow controls registered in the frozen protocol: the existing exact
single-frontier router and an association-erased relation/value bag.  It does
not compare against arbitrary learned attention systems and is not a real-data
efficacy experiment.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import qkv_routing as homogeneous
import semantic_layer_routing as semantic


SCHEMA_VERSION = "hswm-semantic-layer-falsifier/v1"
N_WORLDS = 32
FIXTURE_MANIFEST = "semantic_layer_fixture_manifest.json"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fact(
    world: str,
    fact_name: str,
    subject_id: str,
    subject_type: str,
    predicate: str,
    object_id: str,
    object_type: str,
) -> semantic.TypedFactV1:
    source_id = f"{world}:evidence:{fact_name}"
    source_text = f"{subject_id} | {predicate} | {object_id}."
    return semantic.TypedFactV1(
        fact_id=f"{world}:fact:{fact_name}",
        source_id=source_id,
        subject_id=subject_id,
        subject_type=subject_type,
        predicate=predicate,
        object_id=object_id,
        object_type=object_type,
        subject_selector=homogeneous.bind_exact_selector(
            source_id, source_text, subject_id,
        ),
        predicate_selector=homogeneous.bind_exact_selector(
            source_id, source_text, predicate,
        ),
        object_selector=homogeneous.bind_exact_selector(
            source_id, source_text, object_id,
        ),
    )


def _world_ids(world: str) -> dict[str, str]:
    return {
        key: f"{world}:{value}" for key, value in {
            "parent": "alice",
            "bob": "bob",
            "carol": "carol",
            "paris": "paris",
            "rome": "rome",
        }.items()
    }


def _facts(world: str, assignment: int) -> tuple[semantic.TypedFactV1, ...]:
    if assignment not in {0, 1}:
        raise ValueError("assignment must be 0 or 1")
    ids = _world_ids(world)
    bob_date, carol_date = (
        ("1980-01-01", "1990-01-01")
        if assignment == 0 else ("1990-01-01", "1980-01-01")
    )
    return (
        _fact(world, "alice-child-bob", ids["parent"], semantic.PERSON,
              "child", ids["bob"], semantic.PERSON),
        _fact(world, "alice-child-carol", ids["parent"], semantic.PERSON,
              "child", ids["carol"], semantic.PERSON),
        _fact(world, "bob-birth-date", ids["bob"], semantic.PERSON,
              "birth_date", bob_date, semantic.DATE),
        _fact(world, "carol-birth-date", ids["carol"], semantic.PERSON,
              "birth_date", carol_date, semantic.DATE),
        _fact(world, "bob-birthplace", ids["bob"], semantic.PERSON,
              "birthplace", ids["paris"], semantic.CITY),
        _fact(world, "carol-birthplace", ids["carol"], semantic.PERSON,
              "birthplace", ids["rome"], semantic.CITY),
    )


def _load_expected_manifest(
    n_worlds: int,
) -> tuple[dict[tuple[str, int, str], str], str]:
    """Load literal expected terminals without calling the tested reducer."""

    path = Path(__file__).resolve().parent / FIXTURE_MANIFEST
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("schema_version") != (
        "hswm-semantic-layer-fixture-manifest/v1"
    ):
        raise ValueError("fixture manifest schema mismatch")
    cases = payload.get("cases")
    if payload.get("n_cases") != 128 or not isinstance(cases, list):
        raise ValueError("fixture manifest must contain 128 literal cases")
    expected: dict[tuple[str, int, str], str] = {}
    for case in cases:
        key = (case["world"], case["date_assignment"], case["reducer"])
        if key in expected:
            raise ValueError("duplicate fixture manifest case")
        expected[key] = case["expected_terminal"]
    selected = {
        key: value for key, value in expected.items()
        if int(key[0][1:]) < n_worlds
    }
    if len(selected) != n_worlds * 4:
        raise ValueError("fixture manifest does not cover requested worlds")
    return selected, sha256(raw).hexdigest()


def _rebuild(
    rows: Iterable[semantic.TypedFactV1],
    *,
    predicates: dict[str, str] | None = None,
    object_types: dict[str, str] | None = None,
    object_ids: dict[str, str] | None = None,
) -> tuple[semantic.TypedFactV1, ...]:
    predicates = predicates or {}
    object_types = object_types or {}
    object_ids = object_ids or {}
    rebuilt = []
    for row in rows:
        name = row.fact_id.split(":fact:", 1)[1]
        world = row.fact_id.split(":fact:", 1)[0]
        rebuilt.append(_fact(
            world, name, row.subject_id, row.subject_type,
            predicates.get(name, row.predicate),
            object_ids.get(name, row.object_id),
            object_types.get(name, row.object_type),
        ))
    return tuple(rebuilt)


def _type_null(
    rows: tuple[semantic.TypedFactV1, ...],
) -> tuple[semantic.TypedFactV1, ...]:
    return _rebuild(rows, object_types={"bob-birth-date": semantic.CITY})


def _key_null(
    rows: tuple[semantic.TypedFactV1, ...],
) -> tuple[semantic.TypedFactV1, ...]:
    return _rebuild(rows, predicates={
        "bob-birth-date": "birthplace",
        "carol-birth-date": "birthplace",
        "bob-birthplace": "birth_date",
        "carol-birthplace": "birth_date",
    })


def _value_null(
    rows: tuple[semantic.TypedFactV1, ...],
) -> tuple[semantic.TypedFactV1, ...]:
    dates = {
        row.fact_id.split(":fact:", 1)[1]: row.object_id
        for row in rows if row.predicate == "birth_date"
    }
    return _rebuild(rows, object_ids={
        "bob-birth-date": dates["carol-birth-date"],
        "carol-birth-date": dates["bob-birth-date"],
    })


def _missing_branch(
    rows: tuple[semantic.TypedFactV1, ...],
) -> tuple[semantic.TypedFactV1, ...]:
    return tuple(
        row for row in rows if not row.fact_id.endswith("alice-child-carol")
    )


def _ambiguous_map(
    rows: tuple[semantic.TypedFactV1, ...], world: str,
) -> tuple[semantic.TypedFactV1, ...]:
    ids = _world_ids(world)
    return (*rows, _fact(
        world, "bob-birth-date-duplicate", ids["bob"], semantic.PERSON,
        "birth_date", "2000-01-01", semantic.DATE,
    ))


def _tied_dates(
    rows: tuple[semantic.TypedFactV1, ...],
) -> tuple[semantic.TypedFactV1, ...]:
    return _rebuild(rows, object_ids={
        "bob-birth-date": "1985-01-01",
        "carol-birth-date": "1985-01-01",
    })


def _bad_order(program: semantic.SemanticProgramV1) -> semantic.SemanticProgramV1:
    layers = list(program.layers)
    layers[1], layers[2] = layers[2], layers[1]
    return replace(program, layers=tuple(layers))


def _single_frontier_graph(
    world: str,
) -> homogeneous.QKVGraphV1:
    ids = _world_ids(world)
    records = []
    for name, child in (("bob", ids["bob"]), ("carol", ids["carol"])):
        source_text = f"{ids['parent']} child {child}."
        target_text = f"{child} is a person."
        records.append(homogeneous.EvidenceKVV1(
            record_id=f"{world}:homogeneous:child:{name}",
            source_frontier=ids["parent"], predicate="child",
            target_frontier=child,
            source_selector=homogeneous.bind_exact_selector(
                ids["parent"], source_text, child,
            ),
            target_selector=homogeneous.bind_exact_selector(
                child, target_text, child,
            ),
        ))
    return homogeneous.make_qkv_graph(records)


def _homogeneous_repeat_state(
    memory: semantic.SemanticMemoryV1,
    reducer: str,
) -> dict[str, Any]:
    """Fixed-shape control retaining reducer token but erasing associations."""

    return {
        "schema_version": "hswm-homogeneous-repeat-control/v1",
        "state_shape": "typed_value_multiset_plus_remaining_program_tokens",
        "relation_program": ("child", "birth_date", "birthplace"),
        "reducer": reducer,
        "typed_value_bags": {
            predicate: tuple(sorted(
                (fact.object_type, fact.object_id)
                for fact in memory.facts if fact.predicate == predicate
            ))
            for predicate in ("child", "birth_date", "birthplace")
        },
    }


def _homogeneous_repeat_signature(state: dict[str, Any]) -> str:
    return _digest(state)


def _homogeneous_repeat_guess(state: dict[str, Any]) -> str:
    """Canonical prediction using exactly the state whose digest is reported."""

    cities = sorted(
        value for type_id, value
        in state["typed_value_bags"]["birthplace"]
        if type_id == semantic.CITY
    )
    return cities[0]


def _branch_erasure_control(
    memory: semantic.SemanticMemoryV1,
    program: semantic.SemanticProgramV1,
    static_payload: bytes,
) -> tuple[bytes, semantic.SemanticRouteReceiptV1]:
    """Run the real typed core, erasing associations before its reducer."""

    return semantic.execute_semantic_layers(
        memory, program, static_payload=static_payload,
        control="BRANCH_ERASURE",
    )


def _receipt_envelope_hash_chain_valid(
    receipt: semantic.SemanticRouteReceiptV1,
) -> bool:
    if receipt.status != "PASS" or len(receipt.steps) != 4:
        return False
    expected_types = (
        (semantic.PERSON, semantic.BRANCH_SET_PERSON),
        (semantic.BRANCH_SET_PERSON, semantic.BRANCH_SET_PERSON_DATE),
        (semantic.BRANCH_SET_PERSON_DATE, semantic.SELECTED_PERSON),
        (semantic.SELECTED_PERSON, semantic.CITY),
    )
    previous = _digest({
        "schema_version": semantic.RECEIPT_SCHEMA_VERSION,
        "memory_sha256": receipt.memory_sha256,
        "program_sha256": receipt.program_sha256,
    })
    for index, (step, types) in enumerate(zip(
        receipt.steps, expected_types, strict=True,
    )):
        if (step.input_type, step.output_type) != types:
            return False
        if step.previous_step_sha256 != previous:
            return False
        if index and step.input_state_sha256 != receipt.steps[index - 1].output_state_sha256:
            return False
        step_payload = {
            "depth": step.depth,
            "layer_id": step.layer_id,
            "operator": step.operator,
            "input_type": step.input_type,
            "output_type": step.output_type,
            "input_arity": step.input_arity,
            "output_arity": step.output_arity,
            "input_count": step.input_count,
            "output_count": step.output_count,
            "query_sha256": step.query_sha256,
            "key_sha256": step.key_sha256,
            "value_sha256": step.value_sha256,
            "input_state_sha256": step.input_state_sha256,
            "output_state_sha256": step.output_state_sha256,
            "selected_fact_ids": step.selected_fact_ids,
            "evidence_facts": tuple(asdict(item) for item in step.evidence_facts),
            "branch_lineage": tuple(asdict(item) for item in step.branch_lineage),
            "reducer_pairs": tuple(asdict(item) for item in step.reducer_pairs),
            "selected_branch_id": step.selected_branch_id,
            "previous_step_sha256": step.previous_step_sha256,
        }
        if step.step_sha256 != _digest(step_payload):
            return False
        previous = step.step_sha256
    expand_ids = {item.branch_id for item in receipt.steps[0].branch_lineage}
    map_ids = {item.branch_id for item in receipt.steps[1].branch_lineage}
    reducer_ids = {item.branch_id for item in receipt.steps[2].reducer_pairs}
    selected = receipt.steps[2].selected_branch_id
    receipt_payload = asdict(receipt)
    declared_receipt_sha256 = receipt_payload.pop("receipt_sha256")
    return (
        len(expand_ids) == 2
        and expand_ids == map_ids == reducer_ids
        and selected in map_ids
        and sum(item.selected for item in receipt.steps[2].reducer_pairs) == 1
        and receipt.steps[3].selected_branch_id == selected
        and receipt.terminal_type == semantic.CITY
        and receipt.evaluator_labels_seen == 0
        and declared_receipt_sha256 == _digest(receipt_payload)
    )


def _corrupt_evidence_rejected(row: semantic.TypedFactV1) -> bool:
    selector = row.object_selector
    corruption = "X" * len(selector.exact)
    try:
        semantic.TypedFactV1(
            **{
                **asdict(row),
                "subject_selector": row.subject_selector,
                "predicate_selector": row.predicate_selector,
                "object_selector": replace(selector, exact=corruption),
            }
        )
    except (semantic.SemanticIntegrityError, homogeneous.QKVIntegrityError):
        return True
    return False


def run_experiment(n_worlds: int = N_WORLDS) -> dict[str, Any]:
    if not isinstance(n_worlds, int) or n_worlds < 1:
        raise ValueError("n_worlds must be a positive integer")
    if n_worlds > N_WORLDS:
        raise ValueError(f"n_worlds cannot exceed frozen manifest size {N_WORLDS}")
    expected_manifest, fixture_manifest_sha256 = _load_expected_manifest(n_worlds)

    counts = {
        "typed_exact": 0,
        "single_frontier_exact": 0,
        "single_frontier_ambiguous_refused": 0,
        "homogeneous_repeat_exact": 0,
        "homogeneous_paired_assignment_signature_collisions": 0,
        "homogeneous_reducer_token_distinct": 0,
        "branch_erasure_atomic_refused": 0,
        "type_null_refused": 0,
        "key_null_original_exact": 0,
        "value_null_original_exact": 0,
        "reducer_null_original_exact": 0,
        "layer_order_null_refused": 0,
        "missing_branch_refused": 0,
        "ambiguous_map_refused": 0,
        "tied_reducer_refused": 0,
        "evidence_corruption_rejected": 0,
        "receipt_envelope_hash_chain_valid": 0,
        "atomic_refusal_payload_bit_identical": 0,
        "input_order_and_repeat_deterministic": 0,
    }
    treatment_receipt_roots: list[str] = []
    control_receipt_roots: list[str] = []
    homogeneous_state_roots: list[str] = []

    for index in range(n_worlds):
        world = f"w{index:02d}"
        signatures: dict[tuple[int, str], str] = {}
        single_graph = _single_frontier_graph(world)
        single_program = homogeneous.QueryProgramV1(
            _world_ids(world)["parent"],
            ("child", "birth_date", "birthplace"),
        )
        single_receipt = homogeneous.route_full(
            single_graph, single_program,
        )

        for assignment in (0, 1):
            rows = _facts(world, assignment)
            memory = semantic.make_semantic_memory(rows)
            reversed_memory = semantic.make_semantic_memory(tuple(reversed(rows)))

            for reducer in ("ARGMIN", "ARGMAX"):
                expected = expected_manifest[(world, assignment, reducer)]
                program = semantic.make_semantic_program(
                    _world_ids(world)["parent"], reducer=reducer,
                )
                static = f"static:{world}:{assignment}:{reducer}".encode("ascii")
                homogeneous_state = _homogeneous_repeat_state(memory, reducer)
                signatures[(assignment, reducer)] = _homogeneous_repeat_signature(
                    homogeneous_state,
                )
                homogeneous_state_roots.append(signatures[(assignment, reducer)])
                payload, receipt = semantic.execute_semantic_layers(
                    memory, program, static_payload=static,
                )
                repeat_payload, repeat = semantic.execute_semantic_layers(
                    memory, program, static_payload=static,
                )
                reverse_payload, reverse = semantic.execute_semantic_layers(
                    reversed_memory, program, static_payload=static,
                )

                counts["typed_exact"] += int(
                    receipt.status == "PASS"
                    and receipt.terminal_value_id == expected
                    and payload == expected.encode("utf-8")
                )
                counts["single_frontier_exact"] += int(
                    single_receipt.status == "PASS"
                    and single_receipt.final_frontier == expected
                )
                counts["single_frontier_ambiguous_refused"] += int(
                    single_receipt.status == "REFUSED"
                    and single_receipt.refusal_code == "AMBIGUOUS_KEY_MATCH"
                )
                counts["homogeneous_repeat_exact"] += int(
                    _homogeneous_repeat_guess(homogeneous_state) == expected
                )
                counts["receipt_envelope_hash_chain_valid"] += int(
                    _receipt_envelope_hash_chain_valid(receipt)
                )
                counts["input_order_and_repeat_deterministic"] += int(
                    memory == reversed_memory
                    and (payload, receipt) == (repeat_payload, repeat)
                    and (payload, receipt) == (reverse_payload, reverse)
                )

                erased_payload, erased_receipt = _branch_erasure_control(
                    memory, program, static,
                )
                counts["branch_erasure_atomic_refused"] += int(
                    erased_payload == static
                    and erased_receipt.status == "REFUSED"
                    and erased_receipt.control == "BRANCH_ERASURE"
                    and erased_receipt.refusal_code == (
                        "MISSING_BRANCH_ASSOCIATION"
                    )
                    and erased_receipt.steps == ()
                    and erased_receipt.ablation_state_type == (
                        semantic.BRANCH_SET_PERSON_DATE_ERASED
                    )
                    and isinstance(erased_receipt.ablation_state_sha256, str)
                    and len(erased_receipt.ablation_state_sha256) == 64
                )

                type_payload, type_receipt = semantic.execute_semantic_layers(
                    semantic.make_semantic_memory(_type_null(rows)), program,
                    static_payload=static,
                )
                key_payload, key_receipt = semantic.execute_semantic_layers(
                    semantic.make_semantic_memory(_key_null(rows)), program,
                    static_payload=static,
                )
                value_payload, value_receipt = semantic.execute_semantic_layers(
                    semantic.make_semantic_memory(_value_null(rows)), program,
                    static_payload=static,
                )
                opposite = "ARGMAX" if reducer == "ARGMIN" else "ARGMIN"
                reducer_payload, reducer_receipt = semantic.execute_semantic_layers(
                    memory,
                    semantic.make_semantic_program(
                        _world_ids(world)["parent"], reducer=opposite,
                    ),
                    static_payload=static,
                )
                order_payload, order_receipt = semantic.execute_semantic_layers(
                    memory, _bad_order(program), static_payload=static,
                )
                missing_payload, missing_receipt = semantic.execute_semantic_layers(
                    semantic.make_semantic_memory(_missing_branch(rows)), program,
                    static_payload=static,
                )
                ambiguous_payload, ambiguous_receipt = semantic.execute_semantic_layers(
                    semantic.make_semantic_memory(_ambiguous_map(rows, world)),
                    program, static_payload=static,
                )
                tied_payload, tied_receipt = semantic.execute_semantic_layers(
                    semantic.make_semantic_memory(_tied_dates(rows)), program,
                    static_payload=static,
                )

                counts["type_null_refused"] += int(
                    type_receipt.status == "REFUSED"
                    and type_receipt.refusal_code == "TYPE_MISMATCH"
                )
                counts["key_null_original_exact"] += int(
                    key_receipt.status == "PASS"
                    and key_receipt.terminal_value_id == expected
                )
                counts["value_null_original_exact"] += int(
                    value_receipt.status == "PASS"
                    and value_receipt.terminal_value_id == expected
                )
                counts["reducer_null_original_exact"] += int(
                    reducer_receipt.status == "PASS"
                    and reducer_receipt.terminal_value_id == expected
                )
                counts["layer_order_null_refused"] += int(
                    order_receipt.status == "REFUSED"
                    and order_receipt.refusal_code == "LAYER_ORDER_MISMATCH"
                )
                counts["missing_branch_refused"] += int(
                    missing_receipt.status == "REFUSED"
                    and missing_receipt.refusal_code == "MISSING_BRANCH"
                )
                counts["ambiguous_map_refused"] += int(
                    ambiguous_receipt.status == "REFUSED"
                    and ambiguous_receipt.refusal_code == "AMBIGUOUS_KEY_MATCH"
                )
                counts["tied_reducer_refused"] += int(
                    tied_receipt.status == "REFUSED"
                    and tied_receipt.refusal_code == "TIED_REDUCER_KEY"
                )
                counts["evidence_corruption_rejected"] += int(
                    _corrupt_evidence_rejected(rows[2])
                )
                refused_payloads = (
                    (type_payload, type_receipt),
                    (key_payload, key_receipt),
                    (order_payload, order_receipt),
                    (missing_payload, missing_receipt),
                    (ambiguous_payload, ambiguous_receipt),
                    (tied_payload, tied_receipt),
                )
                counts["atomic_refusal_payload_bit_identical"] += int(all(
                    candidate_payload == static
                    and candidate_receipt.steps == ()
                    and candidate_receipt.terminal_value_id is None
                    for candidate_payload, candidate_receipt in refused_payloads
                ))
                # The value/reducer nulls are expected to complete to the
                # opposite City rather than refuse; retain variables so that
                # accidental payload/result divergence is still observable.
                assert value_payload == (
                    value_receipt.terminal_value_id or ""
                ).encode("utf-8")
                assert reducer_payload == (
                    reducer_receipt.terminal_value_id or ""
                ).encode("utf-8")
                treatment_receipt_roots.append(receipt.receipt_sha256)
                control_receipt_roots.extend((
                    single_receipt.receipt_id,
                    erased_receipt.receipt_sha256,
                    type_receipt.receipt_sha256,
                    key_receipt.receipt_sha256,
                    value_receipt.receipt_sha256,
                    reducer_receipt.receipt_sha256,
                    order_receipt.receipt_sha256,
                    missing_receipt.receipt_sha256,
                    ambiguous_receipt.receipt_sha256,
                    tied_receipt.receipt_sha256,
                ))

        for reducer in ("ARGMIN", "ARGMAX"):
            counts["homogeneous_paired_assignment_signature_collisions"] += int(
                signatures[(0, reducer)] == signatures[(1, reducer)]
            )
        for assignment in (0, 1):
            counts["homogeneous_reducer_token_distinct"] += int(
                signatures[(assignment, "ARGMIN")]
                != signatures[(assignment, "ARGMAX")]
            )

    cases = n_worlds * 2 * 2
    world_variants = n_worlds * 2
    gates = {
        "typed_exact_128_of_128": counts["typed_exact"] == cases,
        "single_frontier_exact_refuses_at_branch": (
            counts["single_frontier_exact"] == 0
            and counts["single_frontier_ambiguous_refused"] == cases
        ),
        "homogeneous_repeat_at_most_half": (
            counts["homogeneous_repeat_exact"] <= cases // 2
        ),
        "homogeneous_fixed_reducer_paired_assignments_collide": (
            counts["homogeneous_paired_assignment_signature_collisions"]
            == n_worlds * 2
        ),
        "homogeneous_control_preserves_reducer_token": (
            counts["homogeneous_reducer_token_distinct"] == world_variants
        ),
        "branch_erasure_refuses_without_invented_pairing": (
            counts["branch_erasure_atomic_refused"] == cases
        ),
        "type_null_refuses": counts["type_null_refused"] == cases,
        "key_null_kills_original": counts["key_null_original_exact"] == 0,
        "value_null_kills_original": counts["value_null_original_exact"] == 0,
        "reducer_null_kills_original": counts["reducer_null_original_exact"] == 0,
        "layer_order_refuses": counts["layer_order_null_refused"] == cases,
        "missing_ambiguous_tied_refuse": (
            counts["missing_branch_refused"] == cases
            and counts["ambiguous_map_refused"] == cases
            and counts["tied_reducer_refused"] == cases
        ),
        "evidence_corruption_rejected": (
            counts["evidence_corruption_rejected"] == cases
        ),
        "receipt_envelope_hash_chain_valid": (
            counts["receipt_envelope_hash_chain_valid"] == cases
        ),
        "atomic_refusal": (
            counts["atomic_refusal_payload_bit_identical"] == cases
        ),
        "deterministic": (
            counts["input_order_and_repeat_deterministic"] == cases
        ),
    }
    root = Path(__file__).resolve().parent
    source_bindings = {
        name: _file_sha256(root / name) for name in (
            "SEMANTIC_QKV_EXPERIMENT_PLAN_2026-07-20.md",
            FIXTURE_MANIFEST,
            "qkv_routing.py",
            "semantic_layer_routing.py",
            "semantic_layer_falsifier.py",
        )
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "protocol_status": "development-only synthetic mechanism",
        "n_worlds": n_worlds,
        "n_world_variants": world_variants,
        "n_cases": cases,
        "n_unique_semantic_templates": 4,
        "namespace_replications_per_template": n_worlds,
        "fixture_manifest_sha256": fixture_manifest_sha256,
        "counts": counts,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "verdict": (
            "SYNTHETIC_HETEROGENEOUS_TYPED_LAYER_MECHANISM_PASS"
            if all(gates.values())
            else "SEMANTIC_LAYER_MECHANISM_GATE_FAIL"
        ),
        "allowed_claim": (
            "On the frozen synthetic two-branch child/date/birthplace "
            "fixtures, this implementation deterministically executed a "
            "supplied heterogeneous typed program with branch-preserving map, "
            "typed reduction, value-bound lookup, evidence receipts, and "
            "query-atomic refusal."
        ),
        "control_boundaries": {
            "SINGLE_FRONTIER_EXACT": (
                "exact-one-key arity diagnostic; not a general homogeneous QKV"
            ),
            "HOMOGENEOUS_REPEAT": (
                "fixed state shape; reducer retained; associations erased"
            ),
            "BRANCH_ERASURE": (
                "typed map retained; only branch IDs and Person-Date pairing erased"
            ),
        },
        "forbidden_claims": [
            "neural attention or learned reasoning",
            "natural-language program induction",
            "real-data retrieval or cognitive uplift",
            "general reasoner",
            "impossibility of arbitrary homogeneous QKV systems",
        ],
        "treatment_receipt_root_sha256": _digest(
            tuple(treatment_receipt_roots)
        ),
        "control_and_mutation_receipt_root_sha256": _digest(
            tuple(control_receipt_roots)
        ),
        "homogeneous_control_state_root_sha256": _digest(
            tuple(homogeneous_state_roots)
        ),
        "source_bindings": source_bindings,
    }
    result["result_sha256"] = _digest(result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=N_WORLDS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    result = run_experiment(args.worlds)
    indent = 2 if args.pretty else None
    rendered = json.dumps(
        result, ensure_ascii=False, sort_keys=True, indent=indent,
    )
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["all_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
