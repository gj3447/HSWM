"""Exact falsifier for the QKV-R1 ordered routing mechanism.

The experiment exhaustively evaluates two order-colliding relation programs in
32 content-addressed isomorphic worlds.  It is a synthetic conformance result,
not a real-data efficacy test and not a neural-attention claim.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Sequence

import qkv_routing as qkv


SCHEMA_VERSION = "hswm-qkv-routing-falsifier/v1"
N_WORLDS = 32


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(
    world: str,
    record_id: str,
    source: str,
    predicate: str,
    target: str,
) -> qkv.EvidenceKVV1:
    source_id = f"{world}:{source}"
    target_id = f"{world}:{target}"
    value = f"Entity {world}:{target}"
    source_text = f"Entity {world}:{source} {predicate} {value}."
    target_text = f"{value} is the subject of {world}:{target}."
    return qkv.EvidenceKVV1(
        record_id=f"{world}:{record_id}",
        source_frontier=source_id,
        predicate=predicate,
        target_frontier=target_id,
        source_selector=qkv.bind_exact_selector(source_id, source_text, value),
        target_selector=qkv.bind_exact_selector(target_id, target_text, value),
    )


def _records(world: str) -> tuple[qkv.EvidenceKVV1, ...]:
    return (
        _record(world, "a-alpha-b", "A", "alpha relation", "B"),
        _record(world, "a-beta-c", "A", "beta relation", "C"),
        _record(world, "b-beta-d", "B", "beta relation", "D"),
        _record(world, "c-alpha-e", "C", "alpha relation", "E"),
    )


def _key_null(records: tuple[qkv.EvidenceKVV1, ...]) -> tuple[qkv.EvidenceKVV1, ...]:
    out = []
    for record in records:
        if record.record_id.endswith("b-beta-d"):
            record = replace(record, predicate="alpha relation")
        elif record.record_id.endswith("c-alpha-e"):
            record = replace(record, predicate="beta relation")
        out.append(record)
    return tuple(out)


def _value_null(world: str) -> tuple[qkv.EvidenceKVV1, ...]:
    # First-hop records and all keys are unchanged.  Only the two second-hop
    # evidence/value bundles are exchanged.
    return (
        _record(world, "a-alpha-b", "A", "alpha relation", "B"),
        _record(world, "a-beta-c", "A", "beta relation", "C"),
        _record(world, "b-beta-d", "B", "beta relation", "E"),
        _record(world, "c-alpha-e", "C", "alpha relation", "D"),
    )


def _ambiguous(records: tuple[qkv.EvidenceKVV1, ...], world: str
               ) -> tuple[qkv.EvidenceKVV1, ...]:
    return (*records,
            _record(world, "b-beta-x", "B", "beta relation", "X"),
            _record(world, "c-alpha-y", "C", "alpha relation", "Y"))


def _fallback_payload(static_payload: bytes,
                      receipt: qkv.QKVRouteReceiptV1) -> bytes:
    """Score-layer contract: refusal cannot leak a partial routed payload."""

    if receipt.status == "REFUSED":
        return static_payload
    return receipt.route_sha256.encode("ascii")


def _chain_is_valid(receipt: qkv.QKVRouteReceiptV1) -> bool:
    for index, step in enumerate(receipt.steps):
        if step.value.target_frontier != step.q_after.frontier:
            return False
        if step.q_after_sha256 != step.q_after.state_sha256:
            return False
        if index + 1 < len(receipt.steps):
            nxt = receipt.steps[index + 1]
            if (step.q_after != nxt.q_before
                    or step.q_after_sha256 != nxt.q_before_sha256):
                return False
    return True


def run_experiment(n_worlds: int = N_WORLDS) -> dict[str, Any]:
    if not isinstance(n_worlds, int) or n_worlds < 1:
        raise ValueError("n_worlds must be a positive integer")

    counts = {
        "ordered_k2_exact": 0,
        "matched_k1_reaches_k2_target": 0,
        "key_null_exact": 0,
        "value_null_exact": 0,
        "unseen_relation_refused": 0,
        "ambiguous_key_refused": 0,
        "unordered_bag_exact": 0,
        "value_to_next_query_receipt_valid": 0,
        "k1_route_invariant_under_second_step_nulls": 0,
        "refusal_static_payload_bit_identical": 0,
        "input_order_and_repeat_deterministic": 0,
    }
    receipt_roots: list[str] = []

    for index in range(n_worlds):
        world = f"w{index:02d}"
        records = _records(world)
        graph = qkv.make_qkv_graph(records)
        reverse_graph = qkv.make_qkv_graph(tuple(reversed(records)))
        key_graph = qkv.make_qkv_graph(_key_null(records))
        value_graph = qkv.make_qkv_graph(_value_null(world))
        ambiguous_graph = qkv.make_qkv_graph(_ambiguous(records, world))

        programs = (
            (qkv.QueryProgramV1(
                f"{world}:A", ("alpha relation", "beta relation"),
            ), f"{world}:D"),
            (qkv.QueryProgramV1(
                f"{world}:A", ("beta relation", "alpha relation"),
            ), f"{world}:E"),
        )
        for program, expected in programs:
            full = qkv.route_full(graph, program)
            repeated = qkv.route_full(graph, program)
            reordered = qkv.route_full(reverse_graph, program)
            k1 = qkv.route_k1(graph, program)
            key_k1 = qkv.route_k1(key_graph, program)
            value_k1 = qkv.route_k1(value_graph, program)
            key_null = qkv.route_full(key_graph, program)
            value_null = qkv.route_full(value_graph, program)
            unseen = qkv.route_full(graph, qkv.QueryProgramV1(
                program.initial_frontier,
                (program.relations[0], "unseen relation"),
            ))
            ambiguous = qkv.route_full(ambiguous_graph, program)
            unordered = qkv.route_full(graph, qkv.QueryProgramV1(
                program.initial_frontier, tuple(sorted(program.relations)),
            ))
            static = f"static:{world}:{program.program_sha256}".encode("ascii")

            counts["ordered_k2_exact"] += int(
                full.status == "PASS" and full.final_frontier == expected
            )
            counts["matched_k1_reaches_k2_target"] += int(
                k1.final_frontier == expected
            )
            counts["key_null_exact"] += int(
                key_null.status == "PASS" and key_null.final_frontier == expected
            )
            counts["value_null_exact"] += int(
                value_null.status == "PASS" and value_null.final_frontier == expected
            )
            counts["unseen_relation_refused"] += int(
                unseen.status == "REFUSED" and not unseen.steps
                and unseen.final_frontier == unseen.initial_frontier
            )
            counts["ambiguous_key_refused"] += int(
                ambiguous.status == "REFUSED" and not ambiguous.steps
                and ambiguous.final_frontier == ambiguous.initial_frontier
            )
            counts["unordered_bag_exact"] += int(
                unordered.status == "PASS" and unordered.final_frontier == expected
            )
            counts["value_to_next_query_receipt_valid"] += int(
                _chain_is_valid(full)
            )
            counts["k1_route_invariant_under_second_step_nulls"] += int(
                k1.route_sha256 == key_k1.route_sha256 == value_k1.route_sha256
            )
            counts["refusal_static_payload_bit_identical"] += int(
                _fallback_payload(static, unseen) == static
                and _fallback_payload(static, ambiguous) == static
            )
            counts["input_order_and_repeat_deterministic"] += int(
                graph == reverse_graph and full == repeated == reordered
            )
            receipt_roots.append(full.receipt_id)

    n_programs = 2 * n_worlds
    gates = {
        "ordered_k2_exact": counts["ordered_k2_exact"] == n_programs,
        "matched_k1_cannot_reach_terminal": (
            counts["matched_k1_reaches_k2_target"] == 0
        ),
        "second_step_key_null_kills": counts["key_null_exact"] == 0,
        "second_step_value_null_kills": counts["value_null_exact"] == 0,
        "unseen_relation_atomic_refusal": (
            counts["unseen_relation_refused"] == n_programs
        ),
        "ambiguous_key_atomic_refusal": (
            counts["ambiguous_key_refused"] == n_programs
        ),
        "unordered_bag_cannot_discriminate_both_orders": (
            counts["unordered_bag_exact"] <= n_worlds
        ),
        "value_to_next_query_receipts": (
            counts["value_to_next_query_receipt_valid"] == n_programs
        ),
        "matched_k1_route_invariant": (
            counts["k1_route_invariant_under_second_step_nulls"] == n_programs
        ),
        "refusal_static_identity": (
            counts["refusal_static_payload_bit_identical"] == n_programs
        ),
        "deterministic_receipts": (
            counts["input_order_and_repeat_deterministic"] == n_programs
        ),
    }
    passed = all(gates.values())
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if passed else "REFUSED",
        "experiment_scope": "synthetic_ordered_qkv_routing_only",
        "n_worlds": n_worlds,
        "n_programs": n_programs,
        "counts": counts,
        "rates": {
            key: round(value / n_programs, 6) for key, value in counts.items()
        },
        "gates": gates,
        "receipt_root_sha256": sha256(
            _canonical_json(tuple(sorted(receipt_roots))).encode("utf-8")
        ).hexdigest(),
        "implementation": {
            "qkv_routing.py": _file_sha256(Path(qkv.__file__)),
            "qkv_routing_falsifier.py": _file_sha256(Path(__file__)),
        },
        "allowed_claim": (
            "synthetic evidence-bound ordered key-value routing mechanism"
            if passed else None
        ),
        "forbidden_claims": [
            "neural attention",
            "raw natural-language reasoning",
            "real-data retrieval uplift",
            "HSWM cognitive uplift",
        ],
        "research_only": True,
    }
    result["result_sha256"] = sha256(
        _canonical_json(result).encode("utf-8")
    ).hexdigest()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="qkv_routing_result.json")
    parser.add_argument("--worlds", type=int, default=N_WORLDS)
    args = parser.parse_args(argv)
    result = run_experiment(args.worlds)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "n_programs": result["n_programs"],
        "result_sha256": result["result_sha256"],
        "out": args.out,
    }, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["run_experiment"]
