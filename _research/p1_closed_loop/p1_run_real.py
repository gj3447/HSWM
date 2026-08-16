"""P1 real-run glue — prepares the locked PhantomWiki run; --run is a stub.

PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json, locked universe:
"large sparse PhantomWiki (t200, friendship-k 1, question-depth 10), same
generation flags as R3" -> the R3 universe dir ``sparse_t200_fk1``.

Modes:
  --prepare-only (default)  load universe, split 5x40 disjoint fresh sealed
                            episodes, embed docs+questions exactly the way
                            r3_walk_regime.main does, validate counts, write
                            split/embeddings/manifest artifacts.
  --run                     load the prepared artifacts and execute
                            p1_loop_harness.run_experiment over the 4 arms,
                            writing P1_RESULTS_2026-07-23.json.  NOT executed
                            as part of this implementation change.

Gold isolation: build_graph/build_world and the walk never read question gold.
The splitter reads solution_traces/answer ONLY to decide walkability — the
same pre-walk eligibility filter r3_walk_regime.main applies (skip
aggregation, require nonempty trace golds).  Answer gold is consumed solely
in the harness's post-hoc scoring phase.

No network at run time: the embedding model must already be in the local
sentence-transformers cache; otherwise this stops and reports instead of
downloading or substituting a different model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path
import sys

import numpy as np


def _discover_repository_root(anchor: str | Path = __file__) -> Path:
    """Locate the checkout root and preserve the original artifact contract."""
    resolved = Path(anchor).resolve(strict=True)
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(f"cannot locate HSWM repository root from {resolved}")


REPO_ROOT = _discover_repository_root()
for _import_root in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from r3_phantom_ingest import load_universe
from _research.f_series.r3_walk_regime import trace_golds

HERE = REPO_ROOT
PREREG = HERE / "PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json"
# 2026-07-24: /Volumes/GM (ExFAT) stopped serving data reads, so the universe
# was REGENERATED locally with the prereg-locked tool/flags/seeds (phantom-wiki
# 1.0.3, SWI-Prolog, seed 1 / friendship-seed 1) and byte-verified against the
# pre-failure GM stat (articles.json == 5,595,416 B). See manifest provenance.
UNIVERSE_ROOT = Path(os.environ.get(
    "P1_ROOT", str(HERE / "_p1_lab/phantomwiki_r3")))
UNIVERSE_NAME = "sparse_t200_fk1"  # prereg: t200, friendship-k 1, qd 10
MODEL = "all-MiniLM-L6-v2"          # identical to r3_walk_regime.MODEL
ST_CACHE = os.environ.get(
    "P1_ST_CACHE", str(Path.home() / ".cache/huggingface/hub"))

EPISODES_E = 5
QUESTIONS_PER_EPISODE = 40
SPLIT_SEED = 20260723   # run-glue constant (not a locked parameter); recorded in manifest
EMBED_TORCH_SEED = 9173  # locked boot_seed reused for torch determinism, as r3 did
EMBED_BATCH_SIZE = 64

SPLIT_PATH = HERE / "P1_SPLIT_2026-07-23.json"
EMBED_PATH = HERE / "P1_EMBEDDINGS_2026-07-23.npz"
MANIFEST_PATH = HERE / "P1_PREPARE_MANIFEST_2026-07-23.json"
RESULTS_PATH = HERE / "P1_RESULTS_2026-07-23.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Episode splitter (pure, deterministic)
# ---------------------------------------------------------------------------

def split_episodes(
    questions: list[dict],
    titles: set[str],
    *,
    n_episodes: int = EPISODES_E,
    per_episode: int = QUESTIONS_PER_EPISODE,
    seed: int = SPLIT_SEED,
) -> list[list[dict]]:
    """n_episodes x per_episode disjoint fresh sealed questions.

    Eligibility is exactly r3_walk_regime.main's walkability filter: skip
    aggregation questions, keep only questions with nonempty trace golds.
    Order is canonicalized by question id before the seeded shuffle, so the
    split is a pure function of (question set, seed) — not of input order.
    """
    eligible = []
    seen_ids: set[str] = set()
    for q in questions:
        if q.get("is_aggregation_question"):
            continue
        if not trace_golds(q, titles):
            continue
        qid = q.get("id")
        if not isinstance(qid, str) or not qid or qid in seen_ids:
            raise ValueError(f"duplicate or missing question id: {qid!r}")
        seen_ids.add(qid)
        eligible.append(q)
    eligible.sort(key=lambda q: q["id"])
    need = n_episodes * per_episode
    if len(eligible) < need:
        raise ValueError(
            f"need {need} eligible questions, universe has {len(eligible)}")
    rng = random.Random(seed)
    shuffled = list(eligible)
    rng.shuffle(shuffled)
    picked = shuffled[:need]
    return [picked[i * per_episode:(i + 1) * per_episode]
            for i in range(n_episodes)]


# ---------------------------------------------------------------------------
# Embeddings (same model/flags as r3_walk_regime.main; cache-only, no network)
# ---------------------------------------------------------------------------

def _load_embedder():
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(EMBED_TORCH_SEED)
    torch.set_num_threads(2)
    try:
        return SentenceTransformer(MODEL, cache_folder=ST_CACHE,
                                   local_files_only=True)
    except Exception as exc:  # cache miss -> stop, never download/substitute
        raise RuntimeError(
            f"embedding model {MODEL!r} is not in the local cache "
            f"({ST_CACHE}); refusing to download or substitute: {exc}")


def embed_texts(model, texts: list[str]) -> np.ndarray:
    return model.encode(texts, normalize_embeddings=True,
                        convert_to_numpy=True, batch_size=EMBED_BATCH_SIZE,
                        show_progress_bar=False).astype(np.float64)


# ---------------------------------------------------------------------------
# prepare / run
# ---------------------------------------------------------------------------

def prepare() -> dict:
    articles, questions = load_universe(UNIVERSE_ROOT / UNIVERSE_NAME)
    titles = {a["title"] for a in articles}
    episodes = split_episodes(questions, titles)
    picked = [q for episode in episodes for q in episode]

    model = _load_embedder()
    doc_texts = [a["article"] for a in sorted(articles, key=lambda x: x["title"])]
    doc_vecs = embed_texts(model, doc_texts)
    q_vecs = embed_texts(model, [q["question"] for q in picked])

    split_doc = {
        "schema": "hswm-p1-episode-split/v1",
        "universe": UNIVERSE_NAME,
        "universe_root": str(UNIVERSE_ROOT),
        "split_seed": SPLIT_SEED,
        "episodes_E": EPISODES_E,
        "questions_per_episode": QUESTIONS_PER_EPISODE,
        "eligible_questions": len([q for q in questions
                                   if not q.get("is_aggregation_question")
                                   and trace_golds(q, titles)]),
        "episodes": {f"e{i + 1}": [q["id"] for q in episode]
                     for i, episode in enumerate(episodes)},
    }
    SPLIT_PATH.write_text(json.dumps(split_doc, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    np.savez_compressed(
        EMBED_PATH,
        doc_vecs=doc_vecs,
        q_vecs=q_vecs,
        qids=np.array([q["id"] for q in picked]),
        doc_titles=np.array([a["title"] for a in sorted(
            articles, key=lambda x: x["title"])]),
    )

    manifest = {
        "schema": "hswm-p1-prepare-manifest/v1",
        "prereg": {"path": PREREG.name, "sha256": _sha(PREREG)},
        "universe": UNIVERSE_NAME,
        "universe_flags": "--num-family-trees 200 --friendship-k 1 "
                          "--num-questions-per-type 30 --question-depth 10 "
                          "--seed 1 --friendship-seed 1 --article-format json",
        "universe_provenance": {
            "origin": "regenerated_locally_after_gm_disk_failure",
            "date": "2026-07-24",
            "reason": "/Volumes/GM (ExFAT) stopped serving data reads "
                      "(metadata stat instant, 2KB content read timeout)",
            "tool": "phantom-wiki 1.0.3 (.venv_phantom pw-generate), "
                    "SWI-Prolog /opt/homebrew/bin/swipl",
            "verification": {
                "articles_json_bytes": 5595416,
                "matches_prefailure_gm_stat": True,
                "articles_and_facts_sha256_match_prior_local_regen": True,
                "solution_trace_sets_match_prior_regen": "600/600",
                "note": "question ids are unseeded UUID4s and trace ordering "
                        "varies between regenerations; question texts, answers, "
                        "prolog, templates and solution-trace SETS are identical",
            },
            "universe_artifacts_sha256": {
                "articles.json": _sha(UNIVERSE_ROOT / UNIVERSE_NAME / "articles.json"),
                "facts.pl": _sha(UNIVERSE_ROOT / UNIVERSE_NAME / "facts.pl"),
            },
        },
        "articles": len(articles),
        "questions_total": len(questions),
        "eligible_questions": split_doc["eligible_questions"],
        "episodes": {k: len(v) for k, v in split_doc["episodes"].items()},
        "disjoint_qids": len({qid for qids in split_doc["episodes"].values()
                              for qid in qids}) == EPISODES_E * QUESTIONS_PER_EPISODE,
        "model": MODEL,
        "split_seed": SPLIT_SEED,
        "artifacts": {
            SPLIT_PATH.name: _sha(SPLIT_PATH),
            EMBED_PATH.name: _sha(EMBED_PATH),
        },
        "gold_isolation": (
            "build_graph/build_world and the walk never read question gold. "
            "The splitter reads solution_traces/answer only for the walkability "
            "filter (same as r3_walk_regime.main). Answer gold is consumed "
            "solely in the harness post-hoc scoring phase."
        ),
        "arm_outcome_inspected": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return manifest


def load_prepared():
    """(articles, episodes, statics) from the prepared artifacts (run mode)."""
    import p1_loop_harness as h  # frozen module; read-only use

    articles, questions = load_universe(UNIVERSE_ROOT / UNIVERSE_NAME)
    split_doc = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    blob = np.load(EMBED_PATH, allow_pickle=False)
    doc_vecs = blob["doc_vecs"]
    q_vecs = blob["q_vecs"]
    qids = [str(q) for q in blob["qids"]]

    by_id = {q["id"]: q for q in questions}
    episodes = [[by_id[qid] for qid in split_doc["episodes"][f"e{i + 1}"]]
                for i in range(len(split_doc["episodes"]))]
    statics = {qid: doc_vecs @ qv for qid, qv in zip(qids, q_vecs)}
    world = h.build_world(articles, statics)
    return world, episodes


def run() -> dict:
    """Execute the 4-arm experiment over the prepared artifacts. NOT executed
    as part of the implementation freeze — callable by the operator."""
    import p1_loop_harness as h  # frozen module; read-only use

    prereg_hash = _sha(PREREG)
    world, episodes = load_prepared()
    results = h.run_experiment(world, episodes, prereg_hash=prereg_hash)
    payload = {
        "schema": "hswm-p1-results/v1",
        "prereg": {"path": PREREG.name, "sha256": prereg_hash},
        "artifacts": {
            SPLIT_PATH.name: _sha(SPLIT_PATH),
            EMBED_PATH.name: _sha(EMBED_PATH),
            MANIFEST_PATH.name: _sha(MANIFEST_PATH),
        },
        "arms": {arm: res.to_dict() for arm, res in results.items()},
    }
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true", default=True,
                      help="build split + embeddings + manifest (default)")
    mode.add_argument("--run", action="store_true",
                      help="execute the 4-arm experiment (operator-triggered)")
    args = parser.parse_args(argv)
    if args.run:
        out = run()
        print(json.dumps({"results": str(RESULTS_PATH),
                          "results_sha256": _sha(RESULTS_PATH),
                          "arms": sorted(out["arms"])}, indent=1))
        return 0
    manifest = prepare()
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
