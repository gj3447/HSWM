"""P1 run-glue splitter: disjointness, sizes, determinism, eligibility rules."""
import pytest

from _research.p1_closed_loop.p1_run_real import split_episodes

TITLES = {f"P{i:03d}" for i in range(30)}


def _q(qid: str, *, aggregation: bool = False, gold: bool = True) -> dict:
    q = {"id": qid, "question": f"question {qid}",
         "answer": ["P001"], "is_aggregation_question": aggregation}
    if gold:
        q["solution_traces"] = [{"x": "P001", "y": "P002"}]
    else:
        q["solution_traces"] = []
        q["answer"] = ["NOT_A_TITLE"]
    return q


def _pool(n: int, overrides: dict | None = None) -> list[dict]:
    pool = [_q(f"q{i:04d}") for i in range(n)]
    for idx, kw in (overrides or {}).items():
        pool[idx].update(kw)
    return pool


def test_split_sizes_and_disjointness():
    episodes = split_episodes(_pool(250), TITLES, n_episodes=5, per_episode=40)
    assert [len(ep) for ep in episodes] == [40] * 5
    qids = [q["id"] for ep in episodes for q in ep]
    assert len(qids) == 200
    assert len(set(qids)) == 200  # disjoint across episodes


def test_split_is_deterministic_for_same_seed_and_input_order_immune():
    pool = _pool(250)
    first = split_episodes(pool, TITLES, n_episodes=5, per_episode=40, seed=7)
    second = split_episodes(pool, TITLES, n_episodes=5, per_episode=40, seed=7)
    reversed_input = split_episodes(list(reversed(pool)), TITLES,
                                    n_episodes=5, per_episode=40, seed=7)
    for a, b, c in zip(first, second, reversed_input):
        assert [q["id"] for q in a] == [q["id"] for q in b] == [q["id"] for q in c]


def test_different_seed_same_multiset_different_assignment():
    pool = _pool(250)
    a = split_episodes(pool, TITLES, n_episodes=5, per_episode=40, seed=7)
    b = split_episodes(pool, TITLES, n_episodes=5, per_episode=40, seed=8)
    ids_a = [q["id"] for ep in a for q in ep]
    ids_b = [q["id"] for ep in b for q in ep]
    assert ids_a != ids_b  # assignment differs


def test_aggregation_questions_excluded():
    pool = _pool(210, {i: {"is_aggregation_question": True} for i in range(10)})
    episodes = split_episodes(pool, TITLES, n_episodes=5, per_episode=40)
    picked = {q["id"] for ep in episodes for q in ep}
    assert not picked & {f"q{i:04d}" for i in range(10)}


def test_questions_without_trace_golds_excluded():
    pool = _pool(210, {i: {"gold": False} for i in range(10, 20)})
    for i in range(10, 20):
        pool[i]["solution_traces"] = []
        pool[i]["answer"] = ["NOT_A_TITLE"]
    episodes = split_episodes(pool, TITLES, n_episodes=5, per_episode=40)
    picked = {q["id"] for ep in episodes for q in ep}
    assert not picked & {f"q{i:04d}" for i in range(10, 20)}


def test_insufficient_eligible_pool_fails_closed():
    with pytest.raises(ValueError):
        split_episodes(_pool(199), TITLES, n_episodes=5, per_episode=40)
    with pytest.raises(ValueError):
        split_episodes(_pool(200, {0: {"is_aggregation_question": True}}),
                       TITLES, n_episodes=5, per_episode=40)


def test_duplicate_question_ids_rejected():
    pool = _pool(201)
    pool[200] = dict(pool[0])  # same id twice
    with pytest.raises(ValueError):
        split_episodes(pool, TITLES, n_episodes=5, per_episode=40)
