from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from hswm_weight_snapshot import (
    SlowWeightV1,
    WeightContractError,
    WeightDeltaV1,
    apply_candidate,
    make_initial_snapshot,
    make_weight_candidate,
)
from hswm_weight_store import SQLiteWeightStore, StaleWeightEpochError


TOPOLOGY_SHA = "1" * 64
GENESIS_PROVENANCE_SHA = "2" * 64
POLICY_SHA = "3" * 64
TAG_A_SHA = "4" * 64
TAG_B_SHA = "5" * 64


def _genesis():
    return make_initial_snapshot(
        (SlowWeightV1("edge:a", 0.0), SlowWeightV1("edge:b", -0.25)),
        topology_sha256=TOPOLOGY_SHA,
        provenance_root_sha256=GENESIS_PROVENANCE_SHA,
    )


def _candidate(base, *, edge_id: str, after: float, tag_sha: str):
    before = base.weight_map()[edge_id]
    return make_weight_candidate(
        base,
        (WeightDeltaV1(edge_id, before, after, tag_sha),),
        learning_policy_sha256=POLICY_SHA,
        provenance_root_sha256=tag_sha,
    )


def test_snapshot_and_candidate_are_canonical_and_immutable():
    base = _genesis()
    candidate = _candidate(
        base, edge_id="edge:a", after=-0.1, tag_sha=TAG_A_SHA
    )

    promoted = apply_candidate(base, candidate)

    assert base.epoch == 0
    assert base.weight_map() == {"edge:a": 0.0, "edge:b": -0.25}
    assert promoted.epoch == 1
    assert promoted.parent_snapshot_id == base.snapshot_id
    assert promoted.provenance_root_sha256 == candidate.candidate_id
    assert promoted.weight_map() == {"edge:a": -0.1, "edge:b": -0.25}


def test_candidate_rejects_unknown_edge_and_before_value_mismatch():
    base = _genesis()
    unknown = make_weight_candidate(
        base,
        (WeightDeltaV1("edge:missing", 0.0, -0.1, TAG_A_SHA),),
        learning_policy_sha256=POLICY_SHA,
        provenance_root_sha256=TAG_A_SHA,
    )
    mismatch = make_weight_candidate(
        base,
        (WeightDeltaV1("edge:a", -0.25, -0.1, TAG_A_SHA),),
        learning_policy_sha256=POLICY_SHA,
        provenance_root_sha256=TAG_A_SHA,
    )

    with pytest.raises(WeightContractError, match="unknown edge"):
        apply_candidate(base, unknown)
    with pytest.raises(WeightContractError, match="before-value mismatch"):
        apply_candidate(base, mismatch)
    with pytest.raises(WeightContractError, match="<= 0"):
        SlowWeightV1("edge:a", 0.01)


def test_store_stages_activates_reopens_and_is_idempotent(tmp_path):
    path = tmp_path / "weights.sqlite3"
    base = _genesis()
    candidate = _candidate(
        base, edge_id="edge:a", after=-0.1, tag_sha=TAG_A_SHA
    )

    with SQLiteWeightStore(path, initial_snapshot=base) as store:
        staged_a = store.stage(candidate)
        staged_b = store.stage(candidate)
        receipt_a = store.activate(candidate.candidate_id)
        receipt_b = store.activate(candidate.candidate_id)
        assert store.journal_mode == "wal"
        assert store.synchronous == 2
        assert staged_a == staged_b
        assert receipt_a == receipt_b
        assert receipt_a.active_snapshot_id == staged_a.snapshot_id
        assert store.active_snapshot() == staged_a

    with SQLiteWeightStore(path, initial_snapshot=base) as reopened:
        assert reopened.active_snapshot() == staged_a
        assert reopened.stage(candidate) == staged_a
        assert reopened.activate(candidate.candidate_id) == receipt_a


def test_two_candidates_from_same_epoch_have_one_cas_winner(tmp_path):
    path = tmp_path / "weights.sqlite3"
    base = _genesis()
    candidate_a = _candidate(
        base, edge_id="edge:a", after=-0.1, tag_sha=TAG_A_SHA
    )
    candidate_b = _candidate(
        base, edge_id="edge:b", after=-0.4, tag_sha=TAG_B_SHA
    )
    store_a = SQLiteWeightStore(path, initial_snapshot=base)
    store_b = SQLiteWeightStore(path, initial_snapshot=base)
    try:
        staged = {
            candidate_a.candidate_id: store_a.stage(candidate_a),
            candidate_b.candidate_id: store_b.stage(candidate_b),
        }
        barrier = threading.Barrier(2)

        def activate(store, candidate_id):
            barrier.wait()
            try:
                return ("activated", store.activate(candidate_id))
            except StaleWeightEpochError as error:
                return ("stale", error)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda args: activate(*args),
                    (
                        (store_a, candidate_a.candidate_id),
                        (store_b, candidate_b.candidate_id),
                    ),
                )
            )

        assert sorted(result[0] for result in results) == ["activated", "stale"]
        winner = next(result[1] for result in results if result[0] == "activated")
        assert store_a.active_snapshot().snapshot_id == winner.active_snapshot_id
        assert winner.active_snapshot_id in {
            snapshot.snapshot_id for snapshot in staged.values()
        }
    finally:
        store_a.close()
        store_b.close()
