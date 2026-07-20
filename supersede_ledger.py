"""S1 supersession as a state-based CRDT — duplicate-immune, order-immune b(e).

Why this module exists
----------------------
The legacy write `readouts.supersede()` mutates in place:

    field.hg.base_salience[edge_id] *= decay

Positive-real multiplication is a *commutative monoid* action, so the multiset of
supersede events determines b(e) irrespective of delivery order. It is NOT
idempotent: applying decay=0.5 twice yields 0.25. That is exactly the gap an
op-based CRDT leaves open, and RR-7506 §2.4 states the assumption it needs —
"reliable broadcast that delivers every update to every replica in an order <d",
i.e. no duplicate delivery. Duplicate tolerance comes only from the state-based
side, RR-7506 §2.3.1: "Since merge is idempotent and commutative ... messages may
be lost, received out of order, or multiple times".

This project actually replays delta packs (the 2026-07-19 P3 incident produced
`PI/kg_replay_session_20260719.cypher`), so a re-applied pack silently squares
the decay of every edge it touches. The repair prescribed in
`SYMPOSIUM/HSWM/PROM_WOLFRAM_IMPORT_2026-07-19.md` §3-A is to guard the product
accumulator with a G-Set of applied event ids — itself a verified CvRDT
(RR-7506 §3.3.1: "merge(S, T) = S union T ... states form a monotonic semilattice
and merge is a LUB operation; G-Set is a CvRDT").

What this buys, precisely
-------------------------
- b(e) becomes a pure function of a SET of events, not of an execution history,
  so replay is total: applying a pack twice is a no-op, and any interleaving of
  packs from any number of sources converges to the same field (SEC).
- The fold is performed in canonical event-id order, so convergence holds at the
  BIT level, not merely at rank level. Floating-point multiplication is
  commutative but not associative; canonicalizing the fold order removes the
  1e-16 perturbations that argsort readouts could otherwise amplify into
  different top-k orders.
- Epochs give a consistent cut. `at_epoch(n)` names a causally closed prefix of
  the write log in the Chandy-Lamport sense, which is what a certification
  receipt must pin instead of wall-clock time.

Scope discipline. Only the S1 (supersede) stream is commutative. The S2
(judgment) stream reads the state it writes and is order-essential; it is NOT
modelled here, and `AdmissionError` is the mechanism that keeps it out. Graph
rewriting confluence is undecidable in general and critical-pair joinability is
not even sufficient (Plump 2005), so admission is a decidable per-op gate rather
than a global proof.

Sources: SYMPOSIUM/HSWM/WOLFRAM_OSS_SOURCES_2026-07-20.md sections 2, 3.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np


class LedgerConflictError(ValueError):
    """Same event id carrying a different payload. Fail closed, never merge."""


class AdmissionError(ValueError):
    """A write-op failed the pairwise commutation gate and may not join stream S1."""


@dataclass(frozen=True)
class SupersedeEvent:
    """One accepted supersession decision.

    event_id must be globally unique and stable across replays; it is the dedup
    key, playing the role of automerge's (actor id, sequence) pair. epoch fences
    certification: permutation is legal within an epoch, never across one.
    """

    event_id: str
    edge_id: int
    decay: float
    epoch: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id:
            raise ValueError("event_id must be a non-empty string")
        if int(self.edge_id) != self.edge_id or self.edge_id < 0:
            raise ValueError("edge_id must be a non-negative integer")
        if not (0.0 < float(self.decay) <= 1.0):
            raise ValueError("decay must be in (0, 1]")
        if int(self.epoch) != self.epoch or self.epoch < 0:
            raise ValueError("epoch must be a non-negative integer")

    def payload(self) -> tuple[int, float, int]:
        return (int(self.edge_id), float(self.decay), int(self.epoch))


class SupersedeLedger:
    """G-Set of supersede events; b(e) is a pure function of the set.

    The payload is a grow-only map keyed by event_id. Union is the LUB, so merge
    is idempotent, commutative and associative — the monotonic-semilattice
    conditions RR-7506 requires of a CvRDT. Adding the same event twice is a
    no-op; adding a different payload under an id already present is a conflict
    and fails closed rather than silently overwriting.
    """

    def __init__(self, events: Iterable[SupersedeEvent] = ()) -> None:
        self._events: dict[str, SupersedeEvent] = {}
        for ev in events:
            self.add(ev)

    # ---- semilattice operations ----

    def add(self, event: SupersedeEvent) -> bool:
        """Idempotent insert. Returns True if the set grew, False if already present."""
        prior = self._events.get(event.event_id)
        if prior is not None:
            if prior.payload() != event.payload():
                raise LedgerConflictError(
                    f"event {event.event_id!r} already present with payload "
                    f"{prior.payload()} != {event.payload()}"
                )
            return False
        self._events[event.event_id] = event
        return True

    def merge(self, other: "SupersedeLedger") -> "SupersedeLedger":
        """LUB of two ledgers. Idempotent, commutative, associative."""
        merged = SupersedeLedger(self._events.values())
        for ev in other._events.values():
            merged.add(ev)
        return merged

    def at_epoch(self, epoch: int) -> "SupersedeLedger":
        """Consistent cut: the causally closed prefix with event.epoch <= epoch."""
        return SupersedeLedger(
            ev for ev in self._events.values() if ev.epoch <= epoch
        )

    # ---- derived state ----

    def events(self) -> list[SupersedeEvent]:
        """Canonical (event-id sorted) event list — the deterministic fold order."""
        return [self._events[k] for k in sorted(self._events)]

    def decay_factors(self, n_edges: int) -> np.ndarray:
        """prod of decays per edge, folded in canonical order (bit-reproducible)."""
        factors = np.ones(int(n_edges), dtype=np.float64)
        for ev in self.events():
            if ev.edge_id >= n_edges:
                raise IndexError(
                    f"event {ev.event_id!r} targets edge {ev.edge_id} outside [0,{n_edges})"
                )
            factors[ev.edge_id] *= ev.decay
        return factors

    def base_salience(self, b0: np.ndarray) -> np.ndarray:
        """b(e) = b0(e) * prod_{i in S, edge=e} delta_i. Pure function of the set."""
        b0 = np.asarray(b0, dtype=np.float64)
        return b0 * self.decay_factors(b0.shape[0])

    def digest(self) -> str:
        """Content hash of the canonical set — the receipt id for a cut."""
        payload = [
            [ev.event_id, int(ev.edge_id), float(ev.decay), int(ev.epoch)]
            for ev in self.events()
        ]
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        return len(self._events)

    def __contains__(self, event_id: object) -> bool:
        return event_id in self._events


def apply_ledger(field, ledger: SupersedeLedger, b0: np.ndarray) -> np.ndarray:
    """Recompute b(e) from (b0, ledger) and install it. Idempotent by construction.

    b0 is the pristine base salience of the compiled world; the ledger is the
    separate accepted-decision snapshot. Keeping them apart is what makes the
    write recomputable rather than a destructive in-place update, and it is the
    same separation the World Compiler decision records as
    "accepted supersession decisions are supplied as a separate ledger snapshot".
    """
    b = ledger.base_salience(b0)
    field.hg.base_salience = b
    return b


# ---- admission rule (decidable gate, not a global confluence proof) ----

def assert_commutes(op_a, op_b, states: Iterable[Mapping | np.ndarray],
                    *, rtol: float = 1e-12, atol: float = 0.0) -> None:
    """Reject a new S1 write-op unless it commutes pairwise on every probe state.

    RR-7506 Definition 2.6: operations f and g commute iff `S * f * g` and
    `S * g * f` are equivalent abstract states. Confluence of hypergraph
    rewriting is undecidable and critical-pair joinability does not even imply
    local confluence there (Plump 2005), so the standard is this finite,
    decidable check on concrete states — the engineering move the undecidability
    result forces. Ops that cannot pass must be declared S2/ordered instead.

    Why this gate is NOT bit-exact while the ledger is. IEEE-754 multiplication
    is commutative but not associative, so composing two genuinely commuting
    decay ops reassociates the rounding: `(b*0.9)*0.7` and `(b*0.7)*0.9` differ
    by an ulp. Demanding bit-equality here would reject correct ops. The ledger
    escapes this not by loosening its standard but by removing the choice —
    it folds in canonical event-id order, so every delivery order takes the same
    associativity path and converges bit-identically. Hence: ulp-scale tolerance
    at the op gate, bit-equality at the ledger, rank-equality at the readout.
    Tightening rtol below ulp scale reintroduces false rejections; loosening it
    far above hides real non-commutation, which argsort readouts would amplify.
    """
    for s in states:
        left = op_b(op_a(np.array(s, dtype=np.float64, copy=True)))
        right = op_a(op_b(np.array(s, dtype=np.float64, copy=True)))
        if not np.allclose(left, right, rtol=rtol, atol=atol):
            raise AdmissionError(
                "write-ops do not commute on a probe state; declare the op as "
                f"S2/ordered instead. max|diff| = {np.max(np.abs(left - right))}"
            )
