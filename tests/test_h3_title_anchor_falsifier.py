import numpy as np

from hswm.evaluation.h3 import title_anchor_falsifier as h3


def test_cluster_bootstrap_uses_components_and_detects_positive_delta():
    result = h3.cluster_bootstrap(
        np.array([0.1, 0.2, 0.3, 0.4]),
        ("a", "a", "b", "c"), n_boot=2000, seed=7, n_permutations=10000,
    )
    assert result["n_queries"] == 4
    assert result["n_components"] == 3
    assert result["mean_delta"] == 0.25
    assert result["ci95"][0] > 0
    assert result["p_cluster_signflip_one_sided"] < 0.2


def test_query_metrics_requires_all_supports_for_asr10():
    scores = np.arange(20, dtype=np.float64)
    all_in = h3.query_metrics(scores, np.array([19, 18]))
    one_out = h3.query_metrics(scores, np.array([19, 0]))
    assert all_in["asr10"] == 1.0
    assert one_out["asr10"] == 0.0
    assert one_out["support_recall10"] == 0.5


def test_rrf_is_rank_only_and_shape_preserving():
    cosine = np.array([[0.9, 0.1, 0.2], [0.0, 0.5, 0.4]])
    bm25 = np.array([[1.0, 3.0, 2.0], [4.0, 1.0, 2.0]])
    out = h3.rrf_scores(cosine, bm25)
    assert out.shape == cosine.shape
    top = int(np.argmax(out[0]))
    assert top == 0


# --- v2.4.6 guard-path fixtures (vacuity 0/8: survivors sat in _sample_rows
# boundaries and the raw-cache identity/digest guards — Q3 confirmed, same
# guard-class pattern as qkv_b1) ---

def test_sample_rows_exact_n_and_boundary(monkeypatch):
    """cmp@87/89 (len<n -> <=): overshoot must not silently pass; the final
    count must be exactly n_rows or a RuntimeError. Also kills cmp@92
    (!= n -> == n inversion: success becomes an error)."""
    rows = [{"id": f"r{i}", "question": "?", "paragraphs": [
        {"idx": 0, "title": "A B", "paragraph_text": "A B c.", "is_supporting": True},
        {"idx": 1, "title": "B C", "paragraph_text": "B C d.", "is_supporting": True}]}
            for i in range(6)]
    monkeypatch.setattr(h3.ab, "load_pool", lambda dataset, cache_dir: rows)
    got = h3._sample_rows("ds", "/nonexistent", n_rows=4)  # noqa: SLF001
    assert len(got) == 4


def test_sample_rows_raises_when_pool_too_small(monkeypatch):
    rows = [{"id": "r0", "question": "?", "paragraphs": [
        {"idx": 0, "title": "A B", "paragraph_text": "A B c.", "is_supporting": True},
        {"idx": 1, "title": "B C", "paragraph_text": "B C d.", "is_supporting": True}]}]
    monkeypatch.setattr(h3.ab, "load_pool", lambda dataset, cache_dir: rows)
    import pytest
    with pytest.raises(RuntimeError, match="requested"):
        h3._sample_rows("ds", "/nonexistent", n_rows=4)  # noqa: SLF001


def _cache(tmp_path, *, dataset="ds", rows=(), digest=None):
    import json as _json
    from hashlib import sha256
    import relation_eval as reval
    payload = {"dataset": dataset, "rows": list(rows),
               "rows_sha256": digest or sha256(
                   reval.canonical_json(tuple(rows)).encode("utf-8")).hexdigest()}
    p = tmp_path / "h3_relation_raw_ds.json"
    p.write_text(_json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_fetch_raw_map_accepts_valid_cache(tmp_path):
    """Positive fixture — kills cmp@107 NotEq->Eq (valid cache now 'malformed')."""
    cache_dir = _cache(tmp_path, rows=[{"id": "q1", "x": 1}])
    out = h3._fetch_raw_map("ds", str(cache_dir))  # noqa: SLF001
    assert out["q1"]["x"] == 1


def test_fetch_raw_map_rejects_digest_mismatch(tmp_path):
    """cmp@112 NotEq->Eq: a tampered cache (rows changed, digest stale) must
    raise; the inversion lets it through."""
    import pytest
    cache_dir = _cache(tmp_path, rows=[{"id": "q1", "x": 1}], digest="0" * 64)
    with pytest.raises(RuntimeError, match="digest mismatch"):
        h3._fetch_raw_map("ds", str(cache_dir))  # noqa: SLF001
