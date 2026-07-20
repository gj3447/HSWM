"""Teeth tests for S1 write-order confluence (PROM_WOLFRAM_IMPORT §3-A, T1-T4).

Every positive test here is paired with a negative oracle: a mutation that MUST
fail. A confluence suite that only ever passes proves nothing about the property
it claims to certify, so T2 and T3 assert that removing the guard breaks the
result, and T4 asserts that the epoch fence is load-bearing.

Oracles are bit-level (atol=0), which the canonical event-id fold makes
attainable, plus rank-level on the actual retrieval readout.
"""
from __future__ import annotations

import numpy as np
import pytest

from hypergraph import Hypergraph
from readouts import retrieve, supersede
from supersede_ledger import (
    AdmissionError,
    LedgerConflictError,
    SupersedeEvent,
    SupersedeLedger,
    apply_ledger,
    assert_commutes,
)
from weight_field import WeightField

N_EDGES = 50


def _field(seed: int = 0) -> tuple[WeightField, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_nodes, d = 120, 16
    node_emb = rng.normal(size=(n_nodes, d))
    members = [rng.choice(n_nodes, size=int(rng.integers(2, 5)), replace=False)
               for _ in range(N_EDGES)]
    hg = Hypergraph(
        node_emb=node_emb,
        members=members,
        edge_freq=rng.random(N_EDGES),
        edge_recency=rng.random(N_EDGES),
        base_salience=rng.uniform(0.5, 1.0, size=N_EDGES),
    )
    b0 = hg.base_salience.copy()
    query = rng.normal(size=d)
    return WeightField(hg), b0, query


def _log(n_events: int = 400, seed: int = 7, epochs: int = 1) -> list[SupersedeEvent]:
    """Distinct sources must mint distinct event ids — the id IS the dedup key."""
    rng = np.random.default_rng(seed)
    return [
        SupersedeEvent(
            event_id=f"src{seed}-ev-{i:04d}",
            edge_id=int(rng.integers(0, N_EDGES)),
            decay=float(rng.uniform(0.6, 0.99)),
            epoch=int(i * epochs // n_events),
        )
        for i in range(n_events)
    ]


# ---- T1: permutation invariance (POSITIVE) ----

def test_t1_permuted_delivery_order_is_bit_identical():
    field, b0, query = _field()
    events = _log()
    reference = SupersedeLedger(events).base_salience(b0)

    rng = np.random.default_rng(11)
    for _ in range(8):
        shuffled = list(events)
        rng.shuffle(shuffled)
        got = SupersedeLedger(shuffled).base_salience(b0)
        assert np.array_equal(got, reference), "S1 fold is not order-independent"


def test_t1_permutation_preserves_retrieval_rank():
    field, b0, query = _field()
    events = _log()

    apply_ledger(field, SupersedeLedger(events), b0)
    reference_topk = retrieve(field, query, k=10).tolist()

    rng = np.random.default_rng(12)
    for _ in range(8):
        shuffled = list(events)
        rng.shuffle(shuffled)
        apply_ledger(field, SupersedeLedger(shuffled), b0)
        assert retrieve(field, query, k=10).tolist() == reference_topk


def test_t1_ledger_merge_obeys_semilattice_laws():
    a = SupersedeLedger(_log(n_events=120, seed=1))
    b = SupersedeLedger(_log(n_events=120, seed=2))
    c = SupersedeLedger(_log(n_events=120, seed=3))
    _, b0, _ = _field()

    # idempotent, commutative, associative -> LUB
    assert a.merge(a).digest() == a.digest()
    assert a.merge(b).digest() == b.merge(a).digest()
    assert a.merge(b).merge(c).digest() == a.merge(b.merge(c)).digest()
    assert np.array_equal(
        a.merge(b).base_salience(b0), b.merge(a).base_salience(b0)
    )


# ---- T2: duplicate delivery (POSITIVE + NEGATIVE ORACLE) ----

def test_t2_replaying_the_same_pack_twice_is_a_noop():
    field, b0, query = _field()
    pack = _log(n_events=200, seed=21)

    ledger = SupersedeLedger(pack)
    once = apply_ledger(field, ledger, b0).copy()

    for ev in pack:                       # re-delivery of the identical pack
        assert ledger.add(ev) is False    # G-Set absorbs it
    twice = apply_ledger(field, ledger, b0)

    assert np.array_equal(once, twice), "duplicate replay changed the field"


def test_t2_negative_oracle_legacy_path_does_corrupt_on_double_apply():
    """The test has teeth: without dedup the very same pack squares the decay."""
    field, b0, _ = _field()
    pack = _log(n_events=200, seed=21)

    field.hg.base_salience = b0.copy()
    for ev in pack:
        supersede(field, ev.edge_id, ev.decay)
    legacy_once = field.hg.base_salience.copy()

    for ev in pack:                       # legacy in-place write, applied twice
        supersede(field, ev.edge_id, ev.decay)
    legacy_twice = field.hg.base_salience.copy()

    assert not np.allclose(legacy_once, legacy_twice), (
        "negative oracle failed: the unguarded path must corrupt on re-delivery"
    )
    # and the corruption is exactly a squaring of the accumulated decay
    ratio = legacy_twice / legacy_once
    expected = legacy_once / b0
    assert np.allclose(ratio, expected)

    # the guarded path reproduces the single application, not the squared one
    guarded = SupersedeLedger(pack).base_salience(b0)
    assert np.allclose(guarded, legacy_once)


def test_t2_same_id_different_payload_fails_closed():
    ledger = SupersedeLedger([SupersedeEvent("ev-1", edge_id=3, decay=0.5)])
    with pytest.raises(LedgerConflictError):
        ledger.add(SupersedeEvent("ev-1", edge_id=3, decay=0.7))


# ---- T3: order-essential ops are refused admission (NEGATIVE ORACLE) ----

def test_t3_admission_accepts_commuting_decay_ops():
    probes = [np.linspace(0.2, 1.0, N_EDGES) for _ in range(3)]
    assert_commutes(lambda b: b * 0.9, lambda b: b * 0.7, probes)


def test_t3_admission_rejects_a_judgment_like_state_reading_op():
    """S2 reads the state it writes (SGD-like), so it cannot join stream S1."""
    probes = [np.linspace(0.2, 1.0, N_EDGES)]

    def normalize_then_shrink(b):        # reads global state -> order-essential
        return b / b.max() * 0.95

    def decay(b):
        return b * 0.8

    with pytest.raises(AdmissionError):
        assert_commutes(normalize_then_shrink, decay, probes)


# ---- T4: epoch fence (POSITIVE + NEGATIVE ORACLE) ----

def test_t4_cut_is_a_prefix_and_permutation_inside_an_epoch_is_free():
    _, b0, _ = _field()
    events = _log(n_events=300, seed=31, epochs=3)

    full = SupersedeLedger(events)
    cut = full.at_epoch(1)
    assert len(cut) < len(full)
    assert all(ev.epoch <= 1 for ev in cut.events())

    rng = np.random.default_rng(33)
    shuffled = list(events)
    rng.shuffle(shuffled)
    assert SupersedeLedger(shuffled).at_epoch(1).digest() == cut.digest()


def test_t4_negative_oracle_crossing_the_fence_changes_the_certified_value():
    _, b0, _ = _field()
    events = _log(n_events=300, seed=31, epochs=3)

    cut_1 = SupersedeLedger(events).at_epoch(1).base_salience(b0)
    cut_2 = SupersedeLedger(events).at_epoch(2).base_salience(b0)

    assert not np.allclose(cut_1, cut_2), (
        "negative oracle failed: epochs must actually fence certification"
    )


def test_digest_names_the_cut_not_the_delivery_history():
    events = _log(n_events=150, seed=41)
    rng = np.random.default_rng(42)
    shuffled = list(events)
    rng.shuffle(shuffled)

    assert SupersedeLedger(events).digest() == SupersedeLedger(shuffled).digest()
    assert SupersedeLedger(events[:-1]).digest() != SupersedeLedger(events).digest()
