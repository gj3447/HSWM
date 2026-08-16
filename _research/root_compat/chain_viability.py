"""T0 real-material chain-viability gate — H3-C0 successor, development-only.

H3-C0 (H3_C0_CHAIN_VIABILITY_DIAGNOSIS_2026-07-20.md) ordered this gate:

    The real-material gate must run after extraction/compiler and before
    embedding or efficacy evaluation.  It should publish an immutable chain
    ledger and stop at the first failed rung: [...] If T0 is zero, the system
    must emit ``PRECOMPUTE_NOOP_DEPTH2`` and spend no embedding or certificate
    budget.

This module owns exactly the T0 rung: query-free structural enumeration of
admissible depth-two chains over a ``TypedCompositionGraphV1``, applying the
same admission the traversal kernel enforces at query time
(``typed_composition.py`` frontier expansion):

    T0  A.target_claim_id is not None            (nonterminal first edge)
        B.source_claim_id == A.target_claim_id   (claim continuity)
        B.join_entity_id != A.join_entity_id     (join distinctness)
        B.target not in {A.source, A.target}     (no backtrack, no cycle)
        fanout and join-degree bounds pass       (policy gates)

No query, embedding, model, network, clock, or randomness is consumed; the
ledger is a pure function of (graph, policy) and is content-addressed.
T1-T3 stay in the query-time kernel; this gate deliberately cannot see them.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from typed_composition import (
    TypedCompositionGraphV1,
    TypedCompositionPolicyV1,
    TypedEvidenceArcV1,
)


@dataclass(frozen=True)
class AdmissibleChainV1:
    """One admissible depth-two chain, replayable to exact source selectors."""

    first_arc_id: str
    second_arc_id: str
    source_target: int
    middle_target: int
    final_target: int
    shared_claim_id: str
    first_join_entity_id: str
    second_join_entity_id: str


@dataclass(frozen=True)
class ChainLedgerV1:
    """Immutable T0 ledger for one compiled graph under one policy."""

    topology_sha256: str
    policy_sha256: str
    arc_count: int
    nonterminal_arc_count: int
    continuity_pair_count: int
    admissible_chain_count: int
    chains: tuple[AdmissibleChainV1, ...]
    verdict: str  # "T0_PASS" | "PRECOMPUTE_NOOP_DEPTH2"
    ledger_sha256: str


def _policy_digest(policy: TypedCompositionPolicyV1) -> str:
    payload = {
        "max_fanout": policy.max_fanout,
        "max_join_degree": policy.max_join_degree,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


def _chain_payload(chain: AdmissibleChainV1) -> dict:
    return {
        "first_arc_id": chain.first_arc_id,
        "second_arc_id": chain.second_arc_id,
        "source_target": chain.source_target,
        "middle_target": chain.middle_target,
        "final_target": chain.final_target,
        "shared_claim_id": chain.shared_claim_id,
        "first_join_entity_id": chain.first_join_entity_id,
        "second_join_entity_id": chain.second_join_entity_id,
    }


def enumerate_admissible_chains(
    graph: TypedCompositionGraphV1,
    policy: TypedCompositionPolicyV1 | None = None,
) -> ChainLedgerV1:
    """Enumerate every admissible depth-two chain (T0) in deterministic order.

    Mirrors the traversal kernel's structural admission exactly; anything this
    ledger counts, the kernel could walk at query time (subject to its
    query-dependent T1-T3 rungs), and anything it rejects, the kernel rejects.
    """
    policy = policy or TypedCompositionPolicyV1()

    adjacency: dict[int, list[TypedEvidenceArcV1]] = {}
    join_sources: dict[str, set[int]] = {}
    for arc in graph.arcs:
        adjacency.setdefault(arc.source_target, []).append(arc)
        join_sources.setdefault(arc.join_entity_id, set()).update(
            (arc.source_target, arc.target_target),
        )
    for row in adjacency.values():
        row.sort(key=lambda arc: arc.arc_id)

    by_source_claim: dict[str, list[TypedEvidenceArcV1]] = {}
    for arc in graph.arcs:
        by_source_claim.setdefault(arc.source_claim_id, []).append(arc)
    for row in by_source_claim.values():
        row.sort(key=lambda arc: arc.arc_id)

    nonterminal = [arc for arc in graph.arcs if arc.target_claim_id is not None]
    nonterminal.sort(key=lambda arc: arc.arc_id)

    continuity_pairs = 0
    chains: list[AdmissibleChainV1] = []
    for first in nonterminal:
        # The kernel trips its fanout gate on the raw seed row.
        if len(adjacency.get(first.source_target, ())) > policy.max_fanout:
            continue
        continuations = [
            arc for arc in by_source_claim.get(first.target_claim_id, ())
            if arc.source_target == first.target_target
        ]
        if not continuations:
            continue
        continuity_pairs += len(continuations)
        # Depth-two rows are claim-filtered before the kernel's fanout gate.
        if len(continuations) > policy.max_fanout:
            continue
        for second in continuations:
            if second.join_entity_id == first.join_entity_id:
                continue
            if second.target_target in (first.source_target, first.target_target):
                continue
            if (len(join_sources[first.join_entity_id]) > policy.max_join_degree or
                    len(join_sources[second.join_entity_id]) > policy.max_join_degree):
                continue
            chains.append(AdmissibleChainV1(
                first_arc_id=first.arc_id,
                second_arc_id=second.arc_id,
                source_target=first.source_target,
                middle_target=first.target_target,
                final_target=second.target_target,
                shared_claim_id=first.target_claim_id,
                first_join_entity_id=first.join_entity_id,
                second_join_entity_id=second.join_entity_id,
            ))

    chains.sort(key=lambda c: (c.first_arc_id, c.second_arc_id))
    ledger_sha = sha256(json.dumps(
        {
            "schema": "hswm-chain-ledger/v1",
            "topology_sha256": graph.topology_sha256,
            "policy_sha256": _policy_digest(policy),
            "chains": [_chain_payload(c) for c in chains],
        },
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()

    return ChainLedgerV1(
        topology_sha256=graph.topology_sha256,
        policy_sha256=_policy_digest(policy),
        arc_count=len(graph.arcs),
        nonterminal_arc_count=len(nonterminal),
        continuity_pair_count=continuity_pairs,
        admissible_chain_count=len(chains),
        chains=tuple(chains),
        verdict="T0_PASS" if chains else "PRECOMPUTE_NOOP_DEPTH2",
        ledger_sha256=ledger_sha,
    )


def ledger_as_json(ledger: ChainLedgerV1) -> dict:
    return {
        "schema": "hswm-chain-ledger/v1",
        "topology_sha256": ledger.topology_sha256,
        "policy_sha256": ledger.policy_sha256,
        "arc_count": ledger.arc_count,
        "nonterminal_arc_count": ledger.nonterminal_arc_count,
        "continuity_pair_count": ledger.continuity_pair_count,
        "admissible_chain_count": ledger.admissible_chain_count,
        "verdict": ledger.verdict,
        "ledger_sha256": ledger.ledger_sha256,
        "chains": [_chain_payload(c) for c in ledger.chains],
    }
