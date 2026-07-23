"""Sealed PhantomWiki environment and executable P1 experiment entrypoint."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import tempfile
import unicodedata
from typing import Iterable, Sequence

import numpy as np

from hswm_weight_snapshot import (
    SlowWeightV1,
    WeightSnapshotV1,
    canonical_json_bytes,
    canonical_sha256,
    make_initial_snapshot,
)
from model_deployment_receipt import load_deployment_receipt
from p1_eligibility_tag import make_activation_trace
from p1_llm_answerer import (
    P1AnswererConfigV1,
    RecordedP1Answerer,
    RetrievedDocumentV1,
)
from p1_loop_harness import (
    CandidateGateV1,
    EPISODES,
    EpisodeObservationV1,
    P1ExperimentReceiptV1,
    QUESTIONS_PER_EPISODE,
    run_p1_experiment,
)
from p1_weighted_walk import walk_scores_weighted_strict
from r1_predicate_alias import (
    _norm_words,
    build_predicate_alias_index,
    expand_terms,
    query_term_closure,
)
from r3_phantom_ingest import build_graph, load_universe, source_id_for
from typed_composition import TypedEvidenceArcV1


HERE = Path(__file__).parent
PREREGISTRATION = HERE / "PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json"
DEFAULT_DATASET_ROOT = Path("/Volumes/GM/hswm_lab/phantomwiki_r3")
UNIVERSE = "sparse_t200_fk1"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 10
SEED_K = 3
BOOTSTRAP_REPS = 2000
BOOT_SEED = 9173
FRESH_QUESTIONS_PER_EPISODE = 38
INITIAL_LOG_SALIENCE = -0.25
ANSWER_MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"
ANSWER_MODEL_REVISION = "95a723d08a9490559dae23d0cff1d9466213d989"
ANSWER_MAX_TOKENS = 512
FROZEN_MODULES = (
    "feedback_ports.py",
    "feedback_runtime.py",
    "feedback_store.py",
    "bge_m3_embed.py",
    "hswm_weight_snapshot.py",
    "hswm_weight_store.py",
    "p1_eligibility_tag.py",
    "p1_weighted_walk.py",
    "p1_m_commit.py",
    "p1_loop_harness.py",
    "p1_llm_answerer.py",
    "p1_phantom_environment.py",
    "model_deployment_receipt.py",
    "prom_search_hswm/hswm_absorption_fsm.py",
    "r1_predicate_alias.py",
    "r3_phantom_ingest.py",
    "typed_composition.py",
)


class PhantomEnvironmentError(RuntimeError):
    pass


def _file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preregistration_guard() -> dict:
    locked = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise PhantomEnvironmentError("P1 preregistration is not active")
    expected = locked.get("module_sha256")
    if not isinstance(expected, dict) or set(expected) != set(FROZEN_MODULES):
        raise PhantomEnvironmentError("P1 module hash set is not frozen")
    for module in FROZEN_MODULES:
        actual = _file_sha(HERE / module)
        if expected[module] != actual:
            raise PhantomEnvironmentError(f"frozen module drift: {module}")
    parameters = locked.get("locked_parameters", {})
    required = {
        "episodes_E": EPISODES,
        "questions_per_episode": QUESTIONS_PER_EPISODE,
        "eta": 0.05,
        "canary_epsilon_c": 0.02,
        "mu": 0.1,
        "top_k": TOP_K,
        "seed_k": SEED_K,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "boot_seed": BOOT_SEED,
        "initial_log_salience": INITIAL_LOG_SALIENCE,
        "fresh_questions_per_episode": FRESH_QUESTIONS_PER_EPISODE,
        "embedding_model": EMBEDDING_MODEL,
        "answerer_model": ANSWER_MODEL,
        "answerer_revision": ANSWER_MODEL_REVISION,
        "answerer_temperature": 0,
        "answerer_max_tokens": ANSWER_MAX_TOKENS,
        "answerer_disable_thinking": True,
        "a3_shuffle_seed": BOOT_SEED,
    }
    for key, value in required.items():
        if parameters.get(key) != value:
            raise PhantomEnvironmentError(f"locked parameter drift: {key}")
    return locked


def _trace_golds(question: dict, titles: set[str]) -> tuple[frozenset[str], ...]:
    traces = question.get("solution_traces")
    if isinstance(traces, str):
        try:
            traces = json.loads(traces)
        except json.JSONDecodeError:
            traces = []
    out = []
    for trace in (traces or [])[:20]:
        names = {
            value
            for value in (trace or {}).values()
            if isinstance(value, str) and value in titles
        }
        if names and len(names) <= 8:
            out.append(frozenset(source_id_for(name) for name in names))
    if not out:
        answers = {
            value
            for value in (question.get("answer") or [])
            if isinstance(value, str) and value in titles
        }
        if answers and len(answers) <= 8:
            out.append(frozenset(source_id_for(name) for name in answers))
    return tuple(out)


def _best_gold(
    ranked: Sequence[str], golds: Sequence[frozenset[str]]
) -> tuple[float, frozenset[str]]:
    top = frozenset(ranked[:TOP_K])
    candidates = [
        (len(top & gold) / len(gold), tuple(sorted(gold)), gold) for gold in golds
    ]
    if not candidates:
        return 0.0, frozenset()
    score, _, gold = max(candidates, key=lambda item: (item[0], item[1]))
    return float(score), gold


def _normal_answer(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _set_match(predicted: Sequence[str], gold: Sequence[str]) -> float:
    left = {_normal_answer(value) for value in predicted if value.strip()}
    right = {_normal_answer(value) for value in gold if isinstance(value, str) and value.strip()}
    return 1.0 if left == right else 0.0


def _coverage(needles: Iterable[str], query_terms: frozenset[str]) -> float:
    values = tuple(needles)
    if not values or not query_terms:
        return 0.0
    hits = 0
    for needle in values:
        if any(
            needle == query
            or (
                min(len(needle), len(query)) >= 5
                and (needle.startswith(query) or query.startswith(needle))
            )
            for query in query_terms
        ):
            hits += 1
    return hits / len(values)


def _relation_quality(
    query_terms: frozenset[str],
    arc: TypedEvidenceArcV1,
    alias_index: dict[str, frozenset[str]],
) -> float:
    predicate_terms = alias_index.get(
        arc.source_predicate.exact,
        frozenset(_norm_words(arc.source_predicate.exact)),
    )
    role_terms = expand_terms(set(_norm_words(arc.source_argument_role)))
    return 0.75 * _coverage(predicate_terms, query_terms) + 0.25 * _coverage(
        role_terms, query_terms
    )


def _bootstrap_lower(values: Sequence[float], seed: int) -> float:
    if not values:
        return 0.0
    rng = random.Random(seed)
    n = len(values)
    means = sorted(
        math.fsum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(BOOTSTRAP_REPS)
    )
    return means[int(0.025 * BOOTSTRAP_REPS)]


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temp_path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(
                value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            ).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_path.exists():
            temp_path.unlink()


class PhantomP1Environment:
    def __init__(
        self,
        *,
        dataset_root: Path,
        work_directory: Path,
        answerer: RecordedP1Answerer,
        embedding_cache_folder: Path,
        max_answer_concurrency: int = 2,
    ) -> None:
        self.dataset_path = dataset_root / UNIVERSE
        self.work_directory = work_directory
        self.answerer = answerer
        self.embedding_cache_folder = embedding_cache_folder
        self.max_answer_concurrency = max_answer_concurrency
        self.episode_rows: dict[tuple[str, int], list[dict[str, object]]] = {}
        self.edge_use: dict[tuple[str, int], dict[str, int]] = {}

        self.articles, questions = load_universe(self.dataset_path)
        (
            self.target_ids,
            self.graph,
            _,
            self.title_by_source,
            self.ingest_stats,
        ) = build_graph(self.articles)
        self.article_by_source = {
            source_id_for(article["title"]): article for article in self.articles
        }
        titles = {article["title"] for article in self.articles}
        eligible = [
            question
            for question in questions
            if not question.get("is_aggregation_question") and _trace_golds(question, titles)
        ]
        eligible.sort(
            key=lambda question: canonical_sha256(
                {"seed": BOOT_SEED, "question_id": question["id"]}
            )
        )
        required = EPISODES * (QUESTIONS_PER_EPISODE + FRESH_QUESTIONS_PER_EPISODE)
        if len(eligible) < required:
            raise PhantomEnvironmentError(
                f"eligible question count {len(eligible)} is below required {required}"
            )
        episode_count = EPISODES * QUESTIONS_PER_EPISODE
        episode_flat = eligible[:episode_count]
        gate_flat = eligible[episode_count:required]
        self.episode_questions = tuple(
            tuple(episode_flat[i * QUESTIONS_PER_EPISODE:(i + 1) * QUESTIONS_PER_EPISODE])
            for i in range(EPISODES)
        )
        self.gate_questions = tuple(
            tuple(gate_flat[i * FRESH_QUESTIONS_PER_EPISODE:(i + 1) * FRESH_QUESTIONS_PER_EPISODE])
            for i in range(EPISODES)
        )
        self.question_by_id = {
            question["id"]: question for question in episode_flat + gate_flat
        }
        self.golds_by_id = {
            question["id"]: _trace_golds(question, titles)
            for question in episode_flat + gate_flat
        }
        self.split_manifest = {
            "schema_version": "hswm-p1-phantom-split/v1",
            "universe": UNIVERSE,
            "boot_seed": BOOT_SEED,
            "dataset_files": {
                "articles.json": _file_sha(self.dataset_path / "articles.json"),
                "question_files_root": canonical_sha256(
                    [
                        {
                            "path": path.name,
                            "sha256": _file_sha(path),
                        }
                        for path in sorted((self.dataset_path / "questions").glob("type*.json"))
                    ]
                ),
            },
            "episodes": [[q["id"] for q in group] for group in self.episode_questions],
            "fresh_gates": [[q["id"] for q in group] for group in self.gate_questions],
        }
        self.split_manifest_sha256 = canonical_sha256(self.split_manifest)

        predicates = [arc.source_predicate.exact for arc in self.graph.arcs]
        predicates.extend(
            arc.target_predicate.exact
            for arc in self.graph.arcs
            if arc.target_predicate is not None
        )
        self.alias_index = build_predicate_alias_index(predicates)
        self._prepare_embeddings(episode_flat + gate_flat)

    def _prepare_embeddings(self, questions: Sequence[dict]) -> None:
        cache = self.work_directory / "p1_phantom_embeddings.npz"
        ordered_articles = [self.article_by_source[source_id] for source_id in self.target_ids]
        manifest = canonical_sha256(
            {
                "model": EMBEDDING_MODEL,
                "documents": [
                    canonical_sha256(article["article"]) for article in ordered_articles
                ],
                "questions": [
                    {"id": question["id"], "sha256": canonical_sha256(question["question"])}
                    for question in questions
                ],
            }
        )
        if cache.exists():
            stored = np.load(cache, allow_pickle=False)
            if str(stored["manifest"].item()) != manifest:
                raise PhantomEnvironmentError("embedding cache manifest drift")
            self.doc_vectors = np.asarray(stored["documents"], dtype=np.float64)
            ids = [str(value) for value in stored["question_ids"]]
            vectors = np.asarray(stored["questions"], dtype=np.float64)
            self.query_vectors = dict(zip(ids, vectors))
            return
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            EMBEDDING_MODEL,
            cache_folder=str(self.embedding_cache_folder),
            device="cpu",
        )
        self.doc_vectors = model.encode(
            [article["article"] for article in ordered_articles],
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=64,
            show_progress_bar=True,
        ).astype(np.float64)
        query_matrix = model.encode(
            [question["question"] for question in questions],
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=64,
            show_progress_bar=False,
        ).astype(np.float64)
        self.query_vectors = {
            question["id"]: vector for question, vector in zip(questions, query_matrix)
        }
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache,
            manifest=np.asarray(manifest),
            documents=self.doc_vectors,
            question_ids=np.asarray([question["id"] for question in questions]),
            questions=query_matrix,
        )

    def initial_snapshot(self) -> WeightSnapshotV1:
        return make_initial_snapshot(
            (
                SlowWeightV1(arc.arc_id, INITIAL_LOG_SALIENCE)
                for arc in self.graph.arcs
            ),
            topology_sha256=self.graph.topology_sha256,
            provenance_root_sha256=self.split_manifest_sha256,
        )

    def _retrieve(self, question: dict, snapshot: WeightSnapshotV1):
        static = self.doc_vectors @ self.query_vectors[question["id"]]
        seeds = tuple(int(index) for index in np.argsort(-static, kind="stable")[:SEED_K])
        query_terms = query_term_closure(question["question"])
        result = walk_scores_weighted_strict(
            static,
            self.graph,
            seeds=seeds,
            edge_log_salience=snapshot.weight_map(),
            relation_quality=lambda arc: _relation_quality(
                query_terms, arc, self.alias_index
            ),
        )
        order = np.argsort(-np.asarray(result.k2_scores), kind="stable")[:TOP_K]
        ranked = tuple(self.target_ids[int(index)] for index in order)
        recall, best_gold = _best_gold(ranked, self.golds_by_id[question["id"]])
        return ranked, recall, best_gold, result.path_by_target_id()

    def observe_episode(self, arm_id, episode_index, snapshot):
        questions = self.episode_questions[episode_index - 1]
        prepared = []
        for question in questions:
            ranked, recall, best_gold, paths = self._retrieve(question, snapshot)
            documents = tuple(
                RetrievedDocumentV1(
                    source_id,
                    self.title_by_source[source_id],
                    self.article_by_source[source_id]["article"],
                )
                for source_id in ranked
            )
            prepared.append((question, ranked, recall, best_gold, paths, documents))

        with ThreadPoolExecutor(max_workers=self.max_answer_concurrency) as executor:
            answers = list(
                executor.map(
                    lambda item: self.answerer.answer(item[0]["question"], item[5]),
                    prepared,
                )
            )

        rows = []
        traces = []
        edge_counts: dict[str, int] = {}
        correct_ids = []
        for item, answer in zip(prepared, answers):
            question, ranked, recall, best_gold, paths, _ = item
            accuracy = _set_match(answer.answers, question.get("answer") or [])
            if accuracy == 1.0:
                correct_ids.append(question["id"])
            winning_sources = [source for source in ranked if source in best_gold and source in paths]
            for source_id in winning_sources:
                path = paths[source_id]
                trace = make_activation_trace(
                    episode_id=f"episode:{episode_index}",
                    question_id=question["id"],
                    query_sha256=canonical_sha256(question["question"]),
                    snapshot_id=snapshot.snapshot_id,
                    target_id=source_id,
                    edge_ids=path.edge_ids,
                    raw_contribution=path.raw_contribution,
                )
                traces.append(trace)
                for edge_id in path.edge_ids:
                    edge_counts[edge_id] = edge_counts.get(edge_id, 0) + 1
            rows.append(
                {
                    "question_id": question["id"],
                    "answer_receipt_id": answer.receipt_id,
                    "predicted_answer_sha256": canonical_sha256(list(answer.answers)),
                    "gold_answer_sha256": canonical_sha256(question.get("answer") or []),
                    "retrieved_source_ids": list(ranked),
                    "recall10": recall,
                    "set_match": accuracy,
                    "winning_edge_ids": sorted(
                        {edge for source in winning_sources for edge in paths[source].edge_ids}
                    ),
                }
            )
        self.episode_rows[(arm_id, episode_index)] = rows
        self.edge_use[(arm_id, episode_index)] = edge_counts
        reward = math.fsum(float(row["set_match"]) for row in rows) / len(rows)
        recall10 = math.fsum(float(row["recall10"]) for row in rows) / len(rows)
        evaluator_sha = canonical_sha256(
            {
                "arm_id": arm_id,
                "episode_index": episode_index,
                "snapshot_id": snapshot.snapshot_id,
                "row_receipts": [
                    {
                        "question_id": row["question_id"],
                        "answer_receipt_id": row["answer_receipt_id"],
                        "gold_answer_sha256": row["gold_answer_sha256"],
                        "set_match": row["set_match"],
                    }
                    for row in rows
                ],
            }
        )
        return EpisodeObservationV1(
            arm_id=arm_id,
            episode_index=episode_index,
            episode_id=f"episode:{episode_index}",
            snapshot_id=snapshot.snapshot_id,
            reward=reward,
            recall10=recall10,
            evaluator_receipt_sha256=evaluator_sha,
            winning_traces=tuple(traces),
            correct_question_ids=tuple(sorted(correct_ids)),
        )

    def _recalls(
        self, questions: Sequence[dict], snapshot: WeightSnapshotV1
    ) -> list[float]:
        return [self._retrieve(question, snapshot)[1] for question in questions]

    def evaluate_candidate(
        self, arm_id, episode_index, base_snapshot, candidate_snapshot, history
    ):
        fresh = self.gate_questions[episode_index - 1]
        base_recall = self._recalls(fresh, base_snapshot)
        candidate_recall = self._recalls(fresh, candidate_snapshot)
        deltas = [candidate - base for base, candidate in zip(base_recall, candidate_recall)]
        unseen_delta = math.fsum(deltas) / len(deltas)
        seed = int(
            canonical_sha256({"arm": arm_id, "episode": episode_index})[:16], 16
        )
        ci_low = _bootstrap_lower(deltas, seed)

        canary_ids = sorted(
            {question_id for observation in history for question_id in observation.correct_question_ids}
        )
        canary_questions = [self.question_by_id[question_id] for question_id in canary_ids]
        if canary_questions:
            canary_base = self._recalls(canary_questions, base_snapshot)
            canary_candidate = self._recalls(canary_questions, candidate_snapshot)
            retention_delta = math.fsum(
                candidate - base for base, candidate in zip(canary_base, canary_candidate)
            ) / len(canary_questions)
        else:
            retention_delta = 0.0
        canary_drop = max(0.0, -retention_delta)
        evidence = {
            "schema_version": "hswm-p1-candidate-gate-evidence/v1",
            "arm_id": arm_id,
            "episode_index": episode_index,
            "base_snapshot_id": base_snapshot.snapshot_id,
            "candidate_snapshot_id": candidate_snapshot.snapshot_id,
            "fresh_question_ids": [question["id"] for question in fresh],
            "fresh_deltas": deltas,
            "unseen_delta": unseen_delta,
            "unseen_ci_low": ci_low,
            "canary_question_ids": canary_ids,
            "retention_delta": retention_delta,
            "canary_drop": canary_drop,
        }
        return CandidateGateV1(
            evidence_hash=canonical_sha256(evidence),
            unseen_delta=unseen_delta,
            unseen_ci_low=ci_low,
            retention_delta=retention_delta,
            canary_drop=canary_drop,
        )

    def build_evidence(
        self,
        experiment: P1ExperimentReceiptV1,
        *,
        preregistration_sha256: str,
        answer_cache_stats: dict[str, int],
    ) -> dict[str, object]:
        arms = {arm.arm_id: arm for arm in experiment.arms}
        paired = []
        for episode in range(2, EPISODES + 1):
            a1 = {row["question_id"]: row for row in self.episode_rows[("A1_tagged_commit", episode)]}
            a2 = {row["question_id"]: row for row in self.episode_rows[("A2_no_commit", episode)]}
            for question_id in sorted(a1):
                paired.append(float(a1[question_id]["recall10"]) - float(a2[question_id]["recall10"]))
        primary = math.fsum(paired) / len(paired)
        primary_lower = _bootstrap_lower(paired, BOOT_SEED)
        episode_recall = {
            arm_id: [episode.recall10 for episode in arm.episodes]
            for arm_id, arm in arms.items()
        }
        x_mean = 3.0
        a1_values = episode_recall["A1_tagged_commit"]
        slope = math.fsum(
            (index - x_mean) * (value - math.fsum(a1_values) / len(a1_values))
            for index, value in enumerate(a1_values, 1)
        ) / math.fsum((index - x_mean) ** 2 for index in range(1, 6))

        def later_mean(arm_id: str) -> float:
            values = episode_recall[arm_id][1:]
            return math.fsum(values) / len(values)

        utility_signs = []
        utility_reuse = []
        a1_arm = arms["A1_tagged_commit"]
        for episode in a1_arm.episodes:
            for edge_id, delta in episode.committed_deltas:
                later = sum(
                    self.edge_use.get(("A1_tagged_commit", future), {}).get(edge_id, 0)
                    for future in range(episode.episode_index + 1, EPISODES + 1)
                )
                utility_signs.append(1.0 if delta > 0 else -1.0)
                utility_reuse.append(float(later))
        tag_utility = _spearman(utility_signs, utility_reuse)
        a1_later = later_mean("A1_tagged_commit")
        a3_later = later_mean("A3_shuffled_M")
        a4_later = later_mean("A4_uniform_commit")
        canary_failed = any(
            episode.canary_drop is not None and episode.canary_drop > 0.02
            for arm in experiment.arms
            for episode in arm.episodes
        )
        kill = {
            "K1_primary_failed": primary <= 0.01 or primary_lower <= 0.0,
            "K2_shuffled_not_worse": a3_later >= a1_later,
            "K3_uniform_not_worse": a4_later >= a1_later,
            "K4_canary_regression": canary_failed,
            "K5_tag_utility_nonpositive": tag_utility is None or tag_utility <= 0.0,
        }
        return {
            "schema_version": "hswm-p1-closed-loop-evidence/v1",
            "programme": "LakatosTree_HSWM_20260719",
            "branch": "P1-closed-learning-loop",
            "preregistration": {
                "path": PREREGISTRATION.name,
                "sha256": preregistration_sha256,
            },
            "experiment_receipt": experiment.canonical(),
            "split_manifest": self.split_manifest,
            "split_manifest_sha256": self.split_manifest_sha256,
            "ingest": {
                "articles": self.ingest_stats.articles,
                "facts_bound": self.ingest_stats.facts_bound,
                "facts_unbound": self.ingest_stats.facts_unbound,
                "person_arcs": self.ingest_stats.person_arcs,
            },
            "measurement": {
                "metric": "mean_paired_recall10_gain_A1_minus_A2_episodes_2_to_E",
                "value": primary,
                "bootstrap95_lower": primary_lower,
                "secondary_a1_linear_slope": slope,
                "tag_utility_spearman": tag_utility,
                "later_episode_mean_recall10": {
                    "A1_tagged_commit": a1_later,
                    "A2_no_commit": later_mean("A2_no_commit"),
                    "A3_shuffled_M": a3_later,
                    "A4_uniform_commit": a4_later,
                },
                "episode_recall10": episode_recall,
                "episode_reward": {
                    arm_id: [episode.reward for episode in arm.episodes]
                    for arm_id, arm in arms.items()
                },
            },
            "kill_conditions": kill,
            "verdict": "FAIL" if any(kill.values()) else "PASS",
            "budget": {
                "logical_answer_calls": len(ARMS_FOR_REPORT) * EPISODES * QUESTIONS_PER_EPISODE,
                "answer_cache": answer_cache_stats,
                "fresh_gate_llm_calls": 0,
                "graph_construction_llm_calls": 0,
            },
            "gold_boundary": {
                "gold_sent_to_answer_model": False,
                "gold_opened_only_post_answer": True,
                "per_question_gold_values_published": False,
            },
            "limitations": [
                "Synthetic PhantomWiki only; no real-prose or multi-agent transfer claim.",
                "Candidate promotion uses retrieval recall on a disjoint fresh gate; tiny eta updates may remain rank-invariant and be rejected.",
                "Answer cache replays identical deterministic model-function requests across arms while preserving 800 logical invocations.",
            ],
        }


ARMS_FOR_REPORT = (
    "A1_tagged_commit",
    "A2_no_commit",
    "A3_shuffled_M",
    "A4_uniform_commit",
)


def _rank(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = rank
        cursor = end
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    x = _rank(left)
    y = _rank(right)
    mx = math.fsum(x) / len(x)
    my = math.fsum(y) / len(y)
    numerator = math.fsum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.fsum((a - mx) ** 2 for a in x)
    dy = math.fsum((b - my) ** 2 for b in y)
    if dx <= 0.0 or dy <= 0.0:
        return None
    return numerator / math.sqrt(dx * dy)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--work-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18002/v1")
    parser.add_argument("--model", default=ANSWER_MODEL)
    parser.add_argument("--model-revision", default=ANSWER_MODEL_REVISION)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--embedding-cache-folder", type=Path, required=True)
    parser.add_argument("--answer-concurrency", type=int, default=2)
    args = parser.parse_args(argv)

    preregistration_guard()
    if args.model != ANSWER_MODEL or args.model_revision != ANSWER_MODEL_REVISION:
        raise PhantomEnvironmentError("answer model identity differs from preregistration")
    if not args.deployment_receipt.is_file():
        raise PhantomEnvironmentError("deployment receipt path does not exist")
    deployment = load_deployment_receipt(
        args.deployment_receipt,
        verify_snapshot=True,
        verify_live_process=True,
    )
    if (
        deployment["endpoint"] != args.endpoint.rstrip("/")
        or deployment["served_model"] != args.model
        or deployment["snapshot"]["resolved_revision"] != args.model_revision
    ):
        raise PhantomEnvironmentError("live deployment differs from frozen answerer")
    deployment_sha = _file_sha(args.deployment_receipt)
    args.work_directory.mkdir(parents=True, exist_ok=True)
    config = P1AnswererConfigV1(
        endpoint=args.endpoint,
        model=args.model,
        model_revision=args.model_revision,
        deployment_receipt_sha256=deployment_sha,
        max_tokens=ANSWER_MAX_TOKENS,
    )
    with RecordedP1Answerer(
        args.work_directory / "p1_answers.sqlite3", config=config
    ) as answerer:
        environment = PhantomP1Environment(
            dataset_root=args.dataset_root,
            work_directory=args.work_directory,
            answerer=answerer,
            embedding_cache_folder=args.embedding_cache_folder,
            max_answer_concurrency=args.answer_concurrency,
        )
        prereg_sha = _file_sha(PREREGISTRATION)
        experiment = run_p1_experiment(
            experiment_id="hswm-p1-phantomwiki-20260723",
            initial_snapshot=environment.initial_snapshot(),
            environment=environment,
            work_directory=args.work_directory / "arms",
            preregistration_sha256=prereg_sha,
            split_manifest_sha256=environment.split_manifest_sha256,
        )
        evidence = environment.build_evidence(
            experiment,
            preregistration_sha256=prereg_sha,
            answer_cache_stats=answerer.cache_stats(),
        )
    _atomic_write(args.output, evidence)
    print(json.dumps(
        {
            "evidence_path": str(args.output),
            "evidence_sha256": _file_sha(args.output),
            "receipt_id": experiment.receipt_id,
            "verdict": evidence["verdict"],
            "measurement": evidence["measurement"],
            "kill_conditions": evidence["kill_conditions"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_MODULES",
    "PhantomP1Environment",
    "PhantomEnvironmentError",
    "main",
    "preregistration_guard",
]
