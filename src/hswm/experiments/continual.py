"""Deterministic prequential benchmark primitives for continual HSWM tests.

The benchmark deliberately separates testing from learning.  A query is scored
against a frozen pre-update state; only afterwards may newly revealed atomic
relations be delivered to a learner.  The generated identifiers are opaque so
that a foundation model cannot solve the task from lexical prior knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import itertools
import json
import math
from typing import Any, Mapping, Protocol, Sequence

import numpy as np


PROTOCOL = "nonce-graph-prequential/v1"
CONFIRMATORY_STREAMS = 24
CONFIRMATORY_HORIZON = 20
CONFIRMATORY_ALPHA = 0.05
CONFIRMATORY_BOOTSTRAPS = 20_000
CONFIRMATORY_MARGINS = {
    "reset": 0.10,
    "no_write": 0.10,
    "plain": 0.05,
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _nonce(seed_preimage: bytes, domain: str, index: int, *, prefix: str) -> str:
    preimage = (
        PROTOCOL.encode("ascii")
        + b"|nonce|"
        + seed_preimage
        + b"|"
        + domain.encode("ascii")
        + b"|"
        + str(index).encode("ascii")
    )
    return f"{prefix}_{sha256(preimage).hexdigest()[:12]}"


def deterministic_test_seed(stream: int) -> bytes:
    """Return a public seed for unit tests and non-confirmatory dry runs only."""

    if stream < 0:
        raise ValueError("stream must be non-negative")
    return sha256(f"{PROTOCOL}|public-test-seed|{stream}".encode("ascii")).digest()


@dataclass(frozen=True, slots=True)
class AtomicEdge:
    edge_id: str
    source: str
    relation: str
    target: str
    reveal_step: int

    def canonical(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "relation": self.relation,
            "reveal_step": self.reveal_step,
            "source": self.source,
            "target": self.target,
        }

    def learning_token(self) -> dict[str, str]:
        return {
            "kind": "atomic_relation",
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
        }


@dataclass(frozen=True, slots=True)
class QueryItem:
    step: int
    source: str
    relations: tuple[str, ...]
    choices: tuple[str, ...]
    answer: str
    support_edge_ids: tuple[str, ...]
    support_reveal_steps: tuple[int, ...]

    def canonical(self, *, include_answer: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "choices": list(self.choices),
            "relations": list(self.relations),
            "source": self.source,
            "step": self.step,
            "support_edge_ids": list(self.support_edge_ids),
            "support_reveal_steps": list(self.support_reveal_steps),
        }
        if include_answer:
            value["answer"] = self.answer
        return value

    def test_token(self) -> dict[str, Any]:
        return {
            "choices": list(self.choices),
            "instruction": (
                "Follow the ordered relations from source using only previously "
                "learned atomic relations. Return exactly {\"choice\":\"n_...\"}."
            ),
            "kind": "nonce_graph_query",
            "relations": list(self.relations),
            "source": self.source,
        }

    def public_probe(self) -> "PublicProbe":
        return PublicProbe(
            step=self.step,
            source=self.source,
            relations=self.relations,
            choices=self.choices,
        )


@dataclass(frozen=True, slots=True)
class PublicProbe:
    """The complete and only query object visible to a tested arm."""

    step: int
    source: str
    relations: tuple[str, ...]
    choices: tuple[str, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "choices": list(self.choices),
            "instruction": (
                "Follow the ordered relations from source using only previously "
                "learned atomic relations. Return exactly {\"choice\":\"n_...\"}."
            ),
            "kind": "nonce_graph_query",
            "relations": list(self.relations),
            "source": self.source,
            "step": self.step,
        }


@dataclass(frozen=True, slots=True)
class PublicLearningToken:
    """An atomic relation token with evaluator-only schedule metadata removed."""

    source: str
    relation: str
    target: str

    def canonical(self) -> dict[str, str]:
        return {
            "kind": "atomic_relation",
            "relation": self.relation,
            "source": self.source,
            "target": self.target,
        }


@dataclass(frozen=True, slots=True)
class StreamManifest:
    stream: int
    generation_attempt: int
    seed_sha256: str
    numpy_version: str
    bit_generator: str
    delay: int
    horizon: int
    choice_count: int
    warmup_edge_ids: tuple[str, ...]
    edges: tuple[AtomicEdge, ...]
    queries: tuple[QueryItem, ...]
    manifest_sha256: str

    @property
    def episode_id(self) -> str:
        """Opaque arm-visible identity that does not disclose the seed preimage."""

        digest = sha256(f"episode|{self.seed_sha256}".encode("ascii")).hexdigest()
        return f"episode_{digest[:24]}"

    def unsigned(self) -> dict[str, Any]:
        return {
            "bit_generator": self.bit_generator,
            "choice_count": self.choice_count,
            "delay": self.delay,
            "edges": [edge.canonical() for edge in self.edges],
            "generation_attempt": self.generation_attempt,
            "horizon": self.horizon,
            "numpy_version": self.numpy_version,
            "protocol": PROTOCOL,
            "queries": [query.canonical() for query in self.queries],
            "seed_sha256": self.seed_sha256,
            "stream": self.stream,
            "warmup_edge_ids": list(self.warmup_edge_ids),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "manifest_sha256": self.manifest_sha256}

    def revealed_after(self, step: int) -> tuple[AtomicEdge, ...]:
        """Return relations exposed only after ``step`` has been scored."""

        return tuple(edge for edge in self.edges if edge.reveal_step == step)

    def warmup_edges(self) -> tuple[AtomicEdge, ...]:
        return tuple(edge for edge in self.edges if edge.reveal_step == 0)


@dataclass(frozen=True, slots=True)
class ArmAnswer:
    response_text: str
    receipt_sha256: str
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int

    def __post_init__(self) -> None:
        if len(self.receipt_sha256) != 64:
            raise ValueError("answer receipt_sha256 must be 64 hex characters")
        int(self.receipt_sha256, 16)
        if min(self.calls, self.input_tokens, self.output_tokens, self.latency_ms) < 0:
            raise ValueError("answer telemetry must be non-negative")

    def canonical(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "latency_ms": self.latency_ms,
            "output_tokens": self.output_tokens,
            "receipt_sha256": self.receipt_sha256,
            "response_text": self.response_text,
        }


@dataclass(frozen=True, slots=True)
class ArmUpdate:
    receipt_sha256: str
    calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int

    def __post_init__(self) -> None:
        if len(self.receipt_sha256) != 64:
            raise ValueError("update receipt_sha256 must be 64 hex characters")
        int(self.receipt_sha256, 16)
        if min(self.calls, self.input_tokens, self.output_tokens, self.latency_ms) < 0:
            raise ValueError("update telemetry must be non-negative")

    def canonical(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "latency_ms": self.latency_ms,
            "output_tokens": self.output_tokens,
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class LearningBatch:
    episode_id: str
    after_step: int
    chosen: str | None
    correct: bool
    learning_tokens: tuple[PublicLearningToken, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "after_step": self.after_step,
            "chosen": self.chosen,
            "correct": self.correct,
            "episode_id": self.episode_id,
            "learning_tokens": [token.canonical() for token in self.learning_tokens],
        }


class PrequentialArm(Protocol):
    """Minimal boundary between the fixed evaluator and a learning mechanism."""

    name: str

    def state_canonical_bytes(self) -> bytes: ...

    def answer(self, probe: PublicProbe) -> ArmAnswer: ...

    def update(self, batch: LearningBatch) -> ArmUpdate: ...


@dataclass(frozen=True, slots=True)
class StepResult:
    step: int
    arm: str
    pre_state_sha256: str
    post_test_state_sha256: str
    post_update_state_sha256: str
    chosen: str | None
    correct: bool
    answer: ArmAnswer
    update: ArmUpdate

    def canonical(self) -> dict[str, Any]:
        return {
            "answer": self.answer.canonical(),
            "arm": self.arm,
            "chosen": self.chosen,
            "correct": self.correct,
            "post_test_state_sha256": self.post_test_state_sha256,
            "post_update_state_sha256": self.post_update_state_sha256,
            "pre_state_sha256": self.pre_state_sha256,
            "step": self.step,
            "update": self.update.canonical(),
        }


@dataclass(frozen=True, slots=True)
class WarmupResult:
    arm: str
    genesis_state_sha256: str
    post_warmup_state_sha256: str
    update: ArmUpdate

    def canonical(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "genesis_state_sha256": self.genesis_state_sha256,
            "post_warmup_state_sha256": self.post_warmup_state_sha256,
            "update": self.update.canonical(),
        }


@dataclass(frozen=True, slots=True)
class StreamRun:
    manifest_sha256: str
    arm_names: tuple[str, ...]
    warmup_results: tuple[WarmupResult, ...]
    results: tuple[StepResult, ...]
    run_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm_names": list(self.arm_names),
            "manifest_sha256": self.manifest_sha256,
            "protocol": PROTOCOL,
            "results": [result.canonical() for result in self.results],
            "warmup_results": [result.canonical() for result in self.warmup_results],
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "run_sha256": self.run_sha256}


@dataclass(frozen=True, slots=True)
class StreamSetValidation:
    stream_count: int
    horizon: int
    delay: int
    choice_count: int
    stream_labels: tuple[int, ...]
    seed_sha256s: tuple[str, ...]
    episode_ids: tuple[str, ...]
    manifest_sha256s: tuple[str, ...]
    validation_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "choice_count": self.choice_count,
            "delay": self.delay,
            "episode_ids": list(self.episode_ids),
            "horizon": self.horizon,
            "manifest_sha256s": list(self.manifest_sha256s),
            "protocol": PROTOCOL,
            "seed_sha256s": list(self.seed_sha256s),
            "stream_count": self.stream_count,
            "stream_labels": list(self.stream_labels),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "validation_sha256": self.validation_sha256}


@dataclass(frozen=True, slots=True)
class ConfirmatoryScoreRow:
    stream_label: int
    manifest_sha256: str
    run_sha256: str
    arm_scores: tuple[tuple[str, tuple[int, ...]], ...]

    def __post_init__(self) -> None:
        if isinstance(self.stream_label, bool) or self.stream_label < 0:
            raise ValueError("score-row stream label must be non-negative")
        for label, digest in (
            ("manifest", self.manifest_sha256),
            ("run", self.run_sha256),
        ):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError(f"score-row {label} digest is invalid")
        if tuple(name for name, _ in self.arm_scores) != (
            "hswm",
            "no_write",
            "plain",
            "reset",
        ):
            raise ValueError("score-row arm set/order is invalid")
        for _, values in self.arm_scores:
            if len(values) != CONFIRMATORY_HORIZON or any(
                isinstance(value, bool) is False or value not in (False, True)
                for value in values
            ):
                raise ValueError("score-row values must be 20 booleans")

    def canonical(self) -> dict[str, Any]:
        return {
            "arm_scores": [
                {"arm": arm, "scores": [int(value) for value in values]}
                for arm, values in self.arm_scores
            ],
            "manifest_sha256": self.manifest_sha256,
            "run_sha256": self.run_sha256,
            "stream_label": self.stream_label,
        }


@dataclass(frozen=True, slots=True)
class ConfirmatoryScoreBundle:
    stream_set_validation_sha256: str
    rows: tuple[ConfirmatoryScoreRow, ...]
    score_bundle_sha256: str

    def __post_init__(self) -> None:
        if len(self.stream_set_validation_sha256) != 64:
            raise ValueError("score bundle has an invalid stream-set digest")
        if len(self.rows) != CONFIRMATORY_STREAMS:
            raise ValueError("score bundle requires exactly 24 rows")
        if tuple(row.stream_label for row in self.rows) != tuple(
            range(CONFIRMATORY_STREAMS)
        ):
            raise ValueError("score bundle rows are not the exact stream range")
        if len({row.manifest_sha256 for row in self.rows}) != len(self.rows):
            raise ValueError("score bundle repeats a manifest")
        if len({row.run_sha256 for row in self.rows}) != len(self.rows):
            raise ValueError("score bundle repeats a run")
        if self.score_bundle_sha256 != canonical_sha256(self.unsigned()):
            raise ValueError("score bundle content hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL,
            "rows": [row.canonical() for row in self.rows],
            "stream_set_validation_sha256": self.stream_set_validation_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "score_bundle_sha256": self.score_bundle_sha256}


@dataclass(frozen=True, slots=True)
class ControlComparison:
    control: str
    mean_delta: float
    last16_delta: float
    final5_delta: float
    exact_pvalue: float
    holm_pvalue: float
    bootstrap_lcb: float
    required_margin: float
    passed: bool

    def canonical(self) -> dict[str, Any]:
        return {
            "bootstrap_lcb": self.bootstrap_lcb,
            "control": self.control,
            "exact_pvalue": self.exact_pvalue,
            "final5_delta": self.final5_delta,
            "holm_pvalue": self.holm_pvalue,
            "last16_delta": self.last16_delta,
            "mean_delta": self.mean_delta,
            "passed": self.passed,
            "required_margin": self.required_margin,
        }


@dataclass(frozen=True, slots=True)
class ConfirmatoryVerdict:
    stream_set_validation_sha256: str
    score_bundle_sha256: str
    arm_accuracy: tuple[tuple[str, float], ...]
    comparisons: tuple[ControlComparison, ...]
    passed: bool
    verdict_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "alpha": CONFIRMATORY_ALPHA,
            "arm_accuracy": [
                {"arm": arm, "accuracy": accuracy}
                for arm, accuracy in self.arm_accuracy
            ],
            "bootstrap_resamples": CONFIRMATORY_BOOTSTRAPS,
            "comparisons": [comparison.canonical() for comparison in self.comparisons],
            "passed": self.passed,
            "protocol": PROTOCOL,
            "score_bundle_sha256": self.score_bundle_sha256,
            "stream_set_validation_sha256": self.stream_set_validation_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "verdict_sha256": self.verdict_sha256}


def _seed(seed_preimage: bytes, attempt: int) -> tuple[str, int]:
    seed_sha = sha256(seed_preimage).hexdigest()
    attempt_sha = sha256(
        PROTOCOL.encode("ascii")
        + b"|generator|"
        + seed_preimage
        + b"|attempt|"
        + str(attempt).encode("ascii")
    ).digest()
    return seed_sha, int.from_bytes(attempt_sha[:16], "big")


def _derangement(rng: np.random.Generator, size: int) -> np.ndarray:
    base = np.arange(size)
    for _ in range(10_000):
        candidate = rng.permutation(size)
        if np.all(candidate != base):
            return candidate
    raise RuntimeError("failed to generate a deterministic derangement")


def _follow(
    *,
    start: int,
    relation_indexes: tuple[int, ...],
    permutations: Sequence[np.ndarray],
    edge_lookup: Mapping[tuple[int, int], AtomicEdge],
) -> tuple[int, tuple[AtomicEdge, ...]]:
    node = start
    support: list[AtomicEdge] = []
    for relation_index in relation_indexes:
        edge = edge_lookup[(node, relation_index)]
        support.append(edge)
        node = int(permutations[relation_index][node])
    return node, tuple(support)


def _candidate_queries(
    *,
    step: int,
    delay: int,
    entity_count: int,
    relation_count: int,
    permutations: Sequence[np.ndarray],
    edge_lookup: Mapping[tuple[int, int], AtomicEdge],
    used: set[tuple[int, tuple[int, ...]]],
) -> list[tuple[int, tuple[int, ...], int, tuple[AtomicEdge, ...]]]:
    length = 2 if step % 2 else 3
    cutoff = max(0, step - delay)
    candidates: list[tuple[int, tuple[int, ...], int, tuple[AtomicEdge, ...]]] = []
    for start in range(entity_count):
        for relation_indexes in itertools.product(range(relation_count), repeat=length):
            relation_tuple = tuple(int(value) for value in relation_indexes)
            key = (start, relation_tuple)
            if key in used:
                continue
            target, support = _follow(
                start=start,
                relation_indexes=relation_tuple,
                permutations=permutations,
                edge_lookup=edge_lookup,
            )
            if target == start:
                continue
            reveal_steps = tuple(edge.reveal_step for edge in support)
            if max(reveal_steps) > cutoff:
                continue
            if step > delay and max(reveal_steps) != cutoff:
                continue
            candidates.append((start, relation_tuple, target, support))
    return candidates


def generate_stream(
    stream: int,
    *,
    seed_preimage: bytes,
    horizon: int = 20,
    delay: int = 4,
    choice_count: int = 8,
    entity_count: int = 96,
    relation_count: int = 3,
    warmup_edges: int = 64,
    reveal_batch: int = 8,
    max_attempts: int = 256,
) -> StreamManifest:
    """Generate a deterministic leakage-checked relational learning stream."""

    if stream < 0 or horizon <= 0 or delay <= 0:
        raise ValueError("stream, horizon, and delay are out of range")
    if not isinstance(seed_preimage, bytes) or len(seed_preimage) < 16:
        raise ValueError("seed_preimage must contain at least 16 secret bytes")
    if not 2 <= choice_count < entity_count:
        raise ValueError("choice_count must be in [2, entity_count)")
    total_edges = entity_count * relation_count
    if warmup_edges + horizon * reveal_batch > total_edges:
        raise ValueError("reveal schedule exceeds the available atomic edges")

    entities = tuple(
        _nonce(seed_preimage, "entity", index, prefix="n")
        for index in range(entity_count)
    )
    relations = tuple(
        _nonce(seed_preimage, "relation", index, prefix="r")
        for index in range(relation_count)
    )

    for attempt in range(max_attempts):
        seed_sha, seed_value = _seed(seed_preimage, attempt)
        rng = np.random.Generator(np.random.PCG64(seed_value))
        permutations = tuple(
            _derangement(rng, entity_count) for _ in range(relation_count)
        )

        raw_edges: list[tuple[int, int, int, str]] = []
        for relation_index, permutation in enumerate(permutations):
            for source_index, target_index in enumerate(permutation):
                edge_id = _nonce(
                    seed_preimage,
                    f"edge-{relation_index}",
                    source_index,
                    prefix="e",
                )
                raw_edges.append(
                    (source_index, relation_index, int(target_index), edge_id)
                )
        reveal_order = rng.permutation(len(raw_edges)).tolist()
        reveal_by_position: dict[int, int] = {}
        for position, raw_index in enumerate(reveal_order):
            if position < warmup_edges:
                reveal_step = 0
            elif position < warmup_edges + horizon * reveal_batch:
                reveal_step = 1 + (position - warmup_edges) // reveal_batch
            else:
                reveal_step = horizon + delay + 1
            reveal_by_position[int(raw_index)] = reveal_step

        edges: list[AtomicEdge] = []
        edge_lookup: dict[tuple[int, int], AtomicEdge] = {}
        for raw_index, (source_index, relation_index, target_index, edge_id) in enumerate(
            raw_edges
        ):
            edge = AtomicEdge(
                edge_id=edge_id,
                source=entities[source_index],
                relation=relations[relation_index],
                target=entities[target_index],
                reveal_step=reveal_by_position[raw_index],
            )
            edges.append(edge)
            edge_lookup[(source_index, relation_index)] = edge

        used: set[tuple[int, tuple[int, ...]]] = set()
        queries: list[QueryItem] = []
        failed = False
        for step in range(1, horizon + 1):
            candidates = _candidate_queries(
                step=step,
                delay=delay,
                entity_count=entity_count,
                relation_count=relation_count,
                permutations=permutations,
                edge_lookup=edge_lookup,
                used=used,
            )
            if not candidates:
                failed = True
                break
            candidate = candidates[int(rng.integers(0, len(candidates)))]
            source_index, relation_indexes, target_index, support = candidate
            used.add((source_index, relation_indexes))
            distractor_indexes = [
                index for index in range(entity_count) if index != target_index
            ]
            picked = rng.choice(
                distractor_indexes,
                size=choice_count - 1,
                replace=False,
            ).tolist()
            choice_indexes = [target_index, *(int(value) for value in picked)]
            rng.shuffle(choice_indexes)
            queries.append(
                QueryItem(
                    step=step,
                    source=entities[source_index],
                    relations=tuple(relations[index] for index in relation_indexes),
                    choices=tuple(entities[index] for index in choice_indexes),
                    answer=entities[target_index],
                    support_edge_ids=tuple(edge.edge_id for edge in support),
                    support_reveal_steps=tuple(edge.reveal_step for edge in support),
                )
            )
        if failed:
            continue

        ordered_edges = tuple(sorted(edges, key=lambda edge: edge.edge_id))
        warmup_ids = tuple(
            edge.edge_id for edge in ordered_edges if edge.reveal_step == 0
        )
        unsigned = {
            "bit_generator": "numpy.random.PCG64",
            "choice_count": choice_count,
            "delay": delay,
            "edges": [edge.canonical() for edge in ordered_edges],
            "generation_attempt": attempt,
            "horizon": horizon,
            "numpy_version": np.__version__,
            "protocol": PROTOCOL,
            "queries": [query.canonical() for query in queries],
            "seed_sha256": seed_sha,
            "stream": stream,
            "warmup_edge_ids": list(warmup_ids),
        }
        manifest = StreamManifest(
            stream=stream,
            generation_attempt=attempt,
            seed_sha256=seed_sha,
            numpy_version=np.__version__,
            bit_generator="numpy.random.PCG64",
            delay=delay,
            horizon=horizon,
            choice_count=choice_count,
            warmup_edge_ids=warmup_ids,
            edges=ordered_edges,
            queries=tuple(queries),
            manifest_sha256=canonical_sha256(unsigned),
        )
        validate_stream(manifest)
        return manifest
    raise RuntimeError("could not generate a valid stream within max_attempts")


def validate_stream(manifest: StreamManifest) -> None:
    """Fail closed on leakage, chronology, and uniqueness violations."""

    if manifest.manifest_sha256 != canonical_sha256(manifest.unsigned()):
        raise ValueError("manifest content hash mismatch")
    if len(manifest.queries) != manifest.horizon:
        raise ValueError("query horizon mismatch")
    edges = {edge.edge_id: edge for edge in manifest.edges}
    if len(edges) != len(manifest.edges):
        raise ValueError("duplicate edge id")
    if set(manifest.warmup_edge_ids) != {
        edge.edge_id for edge in manifest.edges if edge.reveal_step == 0
    }:
        raise ValueError("warmup edge set mismatch")

    seen_queries: set[tuple[str, tuple[str, ...]]] = set()
    for query in manifest.queries:
        key = (query.source, query.relations)
        if key in seen_queries:
            raise ValueError("exact query repeated")
        seen_queries.add(key)
        if len(query.choices) != manifest.choice_count:
            raise ValueError("choice count mismatch")
        if len(set(query.choices)) != len(query.choices):
            raise ValueError("duplicate query choice")
        if query.answer not in query.choices:
            raise ValueError("answer absent from choices")
        support = tuple(edges[edge_id] for edge_id in query.support_edge_ids)
        if tuple(edge.reveal_step for edge in support) != query.support_reveal_steps:
            raise ValueError("support reveal metadata mismatch")
        cutoff = max(0, query.step - manifest.delay)
        if any(edge.reveal_step > cutoff for edge in support):
            raise ValueError("query depends on a not-yet-mature relation")
        if query.step > manifest.delay and max(query.support_reveal_steps) != cutoff:
            raise ValueError("post-warmup query lacks a newly matured relation")
        node = query.source
        for relation, edge in zip(query.relations, support, strict=True):
            if edge.source != node or edge.relation != relation:
                raise ValueError("support path is discontinuous")
            node = edge.target
        if node != query.answer:
            raise ValueError("support path does not produce the answer")
        public_test = query.test_token()
        if json.dumps(public_test, sort_keys=True).count(query.answer) != 1:
            raise ValueError("answer leaked outside its single option occurrence")


def validate_stream_set(
    manifests: Sequence[StreamManifest],
    *,
    expected_count: int,
    expected_horizon: int = 20,
    expected_delay: int = 4,
    expected_choice_count: int = 8,
) -> StreamSetValidation:
    """Bind independent worlds before any stream-level inference is performed."""

    ordered = tuple(sorted(manifests, key=lambda item: item.stream))
    if expected_count <= 0 or len(ordered) != expected_count:
        raise ValueError("stream-set count differs from its preregistration")
    if tuple(item.stream for item in ordered) != tuple(range(expected_count)):
        raise ValueError("stream labels must be the exact preregistered range")

    unique_fields = {
        "seed_sha256": [item.seed_sha256 for item in ordered],
        "episode_id": [item.episode_id for item in ordered],
        "manifest_sha256": [item.manifest_sha256 for item in ordered],
    }
    for label, values in unique_fields.items():
        if len(values) != len(set(values)):
            raise ValueError(f"stream-set {label} values must be unique")

    seen_entities: set[str] = set()
    seen_relations: set[str] = set()
    seen_edges: set[str] = set()
    for manifest in ordered:
        validate_stream(manifest)
        if (
            manifest.horizon != expected_horizon
            or manifest.delay != expected_delay
            or manifest.choice_count != expected_choice_count
        ):
            raise ValueError("stream-set benchmark parameters differ")
        entities = {
            value for edge in manifest.edges for value in (edge.source, edge.target)
        }
        relations = {edge.relation for edge in manifest.edges}
        edge_ids = {edge.edge_id for edge in manifest.edges}
        if seen_entities & entities or seen_relations & relations or seen_edges & edge_ids:
            raise ValueError("stream namespaces are not disjoint")
        seen_entities.update(entities)
        seen_relations.update(relations)
        seen_edges.update(edge_ids)

    unsigned = {
        "choice_count": expected_choice_count,
        "delay": expected_delay,
        "episode_ids": [item.episode_id for item in ordered],
        "horizon": expected_horizon,
        "manifest_sha256s": [item.manifest_sha256 for item in ordered],
        "protocol": PROTOCOL,
        "seed_sha256s": [item.seed_sha256 for item in ordered],
        "stream_count": expected_count,
        "stream_labels": [item.stream for item in ordered],
    }
    return StreamSetValidation(
        stream_count=expected_count,
        horizon=expected_horizon,
        delay=expected_delay,
        choice_count=expected_choice_count,
        stream_labels=tuple(item.stream for item in ordered),
        seed_sha256s=tuple(item.seed_sha256 for item in ordered),
        episode_ids=tuple(item.episode_id for item in ordered),
        manifest_sha256s=tuple(item.manifest_sha256 for item in ordered),
        validation_sha256=canonical_sha256(unsigned),
    )


def parse_choice(response: str, *, choices: Sequence[str]) -> str | None:
    """Strictly parse the programmatically graded response contract."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    try:
        value = json.loads(response, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(value, dict) or set(value) != {"choice"}:
        return None
    choice = value["choice"]
    if not isinstance(choice, str) or choice not in choices:
        return None
    return choice


def _state_digest(arm: PrequentialArm) -> str:
    state = arm.state_canonical_bytes()
    if not isinstance(state, bytes):
        raise ValueError(f"arm {arm.name!r} returned non-bytes state")
    return sha256(state).hexdigest()


def run_prequential(
    manifest: StreamManifest,
    arms: Sequence[PrequentialArm],
) -> StreamRun:
    """Run test-all, then update-all, without exposing gold answers to arms."""

    validate_stream(manifest)
    arm_names = tuple(arm.name for arm in arms)
    if not arm_names or len(set(arm_names)) != len(arm_names):
        raise ValueError("arm names must be non-empty and unique")

    genesis_states = {arm.name: _state_digest(arm) for arm in arms}
    warmup = LearningBatch(
        episode_id=manifest.episode_id,
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=tuple(
            PublicLearningToken(edge.source, edge.relation, edge.target)
            for edge in manifest.warmup_edges()
        ),
    )
    warmup_updates = {arm.name: arm.update(warmup) for arm in arms}
    warmup_results = tuple(
        WarmupResult(
            arm=arm.name,
            genesis_state_sha256=genesis_states[arm.name],
            post_warmup_state_sha256=_state_digest(arm),
            update=warmup_updates[arm.name],
        )
        for arm in arms
    )

    results: list[StepResult] = []
    for query in manifest.queries:
        probe = query.public_probe()
        pre_states = {arm.name: _state_digest(arm) for arm in arms}
        answers = {arm.name: arm.answer(probe) for arm in arms}
        post_test_states = {arm.name: _state_digest(arm) for arm in arms}
        for name in arm_names:
            if post_test_states[name] != pre_states[name]:
                raise ValueError(f"read-only test mutated arm {name!r}")

        chosen = {
            name: parse_choice(answers[name].response_text, choices=query.choices)
            for name in arm_names
        }
        correct = {name: chosen[name] == query.answer for name in arm_names}

        updates: dict[str, ArmUpdate] = {}
        post_update_states: dict[str, str] = {}
        newly_revealed = tuple(
            PublicLearningToken(edge.source, edge.relation, edge.target)
            for edge in manifest.revealed_after(query.step)
        )
        for arm in arms:
            batch = LearningBatch(
                episode_id=manifest.episode_id,
                after_step=query.step,
                chosen=chosen[arm.name],
                correct=correct[arm.name],
                learning_tokens=newly_revealed,
            )
            updates[arm.name] = arm.update(batch)
            post_update_states[arm.name] = _state_digest(arm)

        for name in arm_names:
            results.append(
                StepResult(
                    step=query.step,
                    arm=name,
                    pre_state_sha256=pre_states[name],
                    post_test_state_sha256=post_test_states[name],
                    post_update_state_sha256=post_update_states[name],
                    chosen=chosen[name],
                    correct=correct[name],
                    answer=answers[name],
                    update=updates[name],
                )
            )

    unsigned = {
        "arm_names": list(arm_names),
        "manifest_sha256": manifest.manifest_sha256,
        "protocol": PROTOCOL,
        "results": [result.canonical() for result in results],
        "warmup_results": [result.canonical() for result in warmup_results],
    }
    return StreamRun(
        manifest_sha256=manifest.manifest_sha256,
        arm_names=arm_names,
        warmup_results=warmup_results,
        results=tuple(results),
        run_sha256=canonical_sha256(unsigned),
    )


def paired_stream_deltas(
    hswm_scores: Sequence[Sequence[int]],
    control_scores: Sequence[Sequence[int]],
) -> np.ndarray:
    hswm = np.asarray(hswm_scores, dtype=np.float64)
    control = np.asarray(control_scores, dtype=np.float64)
    if hswm.shape != control.shape or hswm.ndim != 2:
        raise ValueError("score matrices must have identical [stream, step] shape")
    if not np.isin(hswm, (0.0, 1.0)).all() or not np.isin(control, (0.0, 1.0)).all():
        raise ValueError("scores must be binary")
    return np.mean(hswm - control, axis=1)


def exact_sign_flip_pvalue(deltas: Sequence[float]) -> float:
    """Exact one-sided paired randomization p-value for at most 24 streams."""

    values = np.asarray(deltas, dtype=np.float64)
    if values.ndim != 1 or not 1 <= len(values) <= 24:
        raise ValueError("exact sign-flip test requires 1..24 stream deltas")
    observed = float(values.mean())
    exceed = 0
    total = 1 << len(values)
    chunk = 1 << min(len(values), 18)
    bit_positions = np.arange(len(values), dtype=np.uint64)
    for start in range(0, total, chunk):
        integers = np.arange(start, min(start + chunk, total), dtype=np.uint64)
        signs = 1.0 - 2.0 * ((integers[:, None] >> bit_positions) & 1)
        permuted = np.mean(signs * values[None, :], axis=1)
        exceed += int(np.count_nonzero(permuted >= observed - 1e-15))
    return exceed / total


def bootstrap_lcb(
    deltas: Sequence[float],
    *,
    resamples: int = 20_000,
    alpha: float = 0.05,
    seed: int = 0x4853574D,
) -> float:
    values = np.asarray(deltas, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("bootstrap requires at least two stream deltas")
    if resamples <= 0 or not 0 < alpha < 1:
        raise ValueError("invalid bootstrap configuration")
    rng = np.random.Generator(np.random.PCG64(seed))
    samples = rng.choice(values, size=(resamples, len(values)), replace=True)
    return float(np.quantile(samples.mean(axis=1), alpha, method="linear"))


def holm_adjust(pvalues: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (name, pvalue) in enumerate(ordered):
        if not 0 <= pvalue <= 1 or not math.isfinite(pvalue):
            raise ValueError("p-values must be finite and in [0, 1]")
        running = max(running, min(1.0, (count - rank) * pvalue))
        adjusted[name] = running
    return adjusted


def make_confirmatory_score_bundle(
    stream_set: StreamSetValidation,
    manifests: Mapping[int, StreamManifest],
    runs: Mapping[int, StreamRun],
) -> ConfirmatoryScoreBundle:
    """Bind every score bit to one validated manifest and hashed run."""

    if stream_set.validation_sha256 != canonical_sha256(stream_set.unsigned()):
        raise ValueError("stream-set validation receipt hash mismatch")
    if set(manifests) != set(stream_set.stream_labels) or set(runs) != set(
        stream_set.stream_labels
    ):
        raise ValueError("manifest/run labels differ from the validated stream set")
    reconstructed_set = validate_stream_set(
        tuple(manifests[label] for label in stream_set.stream_labels),
        expected_count=CONFIRMATORY_STREAMS,
        expected_horizon=CONFIRMATORY_HORIZON,
    )
    if reconstructed_set.canonical() != stream_set.canonical():
        raise ValueError("stream-set receipt differs from its canonical manifests")

    rows: list[ConfirmatoryScoreRow] = []
    expected_arms = {"hswm", "no_write", "plain", "reset"}
    for index, stream_label in enumerate(stream_set.stream_labels):
        manifest = manifests[stream_label]
        run = runs[stream_label]
        if run.manifest_sha256 != stream_set.manifest_sha256s[index]:
            raise ValueError("run manifest differs from its validated stream")
        if run.run_sha256 != canonical_sha256(run.unsigned()):
            raise ValueError("stream run content hash mismatch")
        if set(run.arm_names) != expected_arms or len(run.arm_names) != 4:
            raise ValueError("stream run arm set is invalid")
        indexed: dict[tuple[str, int], bool] = {}
        for result in run.results:
            key = (result.arm, result.step)
            if (
                result.arm not in expected_arms
                or not 1 <= result.step <= CONFIRMATORY_HORIZON
                or key in indexed
                or not isinstance(result.correct, bool)
            ):
                raise ValueError("stream run score coverage is invalid")
            query = manifest.queries[result.step - 1]
            regraded = parse_choice(
                result.answer.response_text,
                choices=query.choices,
            )
            if result.chosen != regraded or result.correct is not (
                regraded == query.answer
            ):
                raise ValueError("stream run score differs from programmatic regrading")
            indexed[key] = result.correct
        if len(indexed) != len(expected_arms) * CONFIRMATORY_HORIZON:
            raise ValueError("stream run lacks complete arm/step coverage")
        arm_scores = tuple(
            (
                arm,
                tuple(
                    indexed[(arm, step)]
                    for step in range(1, CONFIRMATORY_HORIZON + 1)
                ),
            )
            for arm in sorted(expected_arms)
        )
        rows.append(
            ConfirmatoryScoreRow(
                stream_label=stream_label,
                manifest_sha256=run.manifest_sha256,
                run_sha256=run.run_sha256,
                arm_scores=arm_scores,
            )
        )
    unsigned = {
        "protocol": PROTOCOL,
        "rows": [row.canonical() for row in rows],
        "stream_set_validation_sha256": stream_set.validation_sha256,
    }
    return ConfirmatoryScoreBundle(
        stream_set_validation_sha256=stream_set.validation_sha256,
        rows=tuple(rows),
        score_bundle_sha256=canonical_sha256(unsigned),
    )


def evaluate_confirmatory(
    stream_set: StreamSetValidation,
    score_bundle: ConfirmatoryScoreBundle,
    manifests: Mapping[int, StreamManifest],
    runs: Mapping[int, StreamRun],
) -> ConfirmatoryVerdict:
    """Apply the preregistered stream-level decision rule without pseudo-replication."""

    if (
        stream_set.stream_count != CONFIRMATORY_STREAMS
        or stream_set.horizon != CONFIRMATORY_HORIZON
        or stream_set.delay != 4
        or stream_set.choice_count != 8
        or stream_set.validation_sha256 != canonical_sha256(stream_set.unsigned())
    ):
        raise ValueError("stream-set receipt is not the confirmatory preregistration")
    if (
        score_bundle.stream_set_validation_sha256
        != stream_set.validation_sha256
        or score_bundle.score_bundle_sha256
        != canonical_sha256(score_bundle.unsigned())
    ):
        raise ValueError("score bundle is not bound to the validated stream set")
    reconstructed = make_confirmatory_score_bundle(stream_set, manifests, runs)
    if reconstructed.canonical() != score_bundle.canonical():
        raise ValueError("score bundle differs from its canonical stream runs")
    if tuple(row.manifest_sha256 for row in score_bundle.rows) != (
        stream_set.manifest_sha256s
    ):
        raise ValueError("score bundle manifest order differs from the stream set")

    matrices: dict[str, np.ndarray] = {}
    for arm in ("hswm", "no_write", "plain", "reset"):
        matrix = np.asarray(
            [dict(row.arm_scores)[arm] for row in score_bundle.rows],
            dtype=np.float64,
        )
        if matrix.shape != (CONFIRMATORY_STREAMS, CONFIRMATORY_HORIZON):
            raise ValueError("confirmatory score matrix must be [24, 20]")
        if not np.isin(matrix, (0.0, 1.0)).all():
            raise ValueError("confirmatory scores must be binary")
        matrices[arm] = matrix

    hswm = matrices["hswm"]
    deltas = {
        control: np.mean(hswm - matrices[control], axis=1)
        for control in CONFIRMATORY_MARGINS
    }
    raw_pvalues = {
        control: exact_sign_flip_pvalue(values)
        for control, values in deltas.items()
    }
    adjusted = holm_adjust(raw_pvalues)

    comparisons: list[ControlComparison] = []
    for control in sorted(CONFIRMATORY_MARGINS):
        mean_delta = float(np.mean(deltas[control]))
        last16_delta = float(np.mean(hswm[:, 4:] - matrices[control][:, 4:]))
        final5_delta = float(np.mean(hswm[:, -5:] - matrices[control][:, -5:]))
        lcb = bootstrap_lcb(
            deltas[control],
            resamples=CONFIRMATORY_BOOTSTRAPS,
        )
        required_margin = CONFIRMATORY_MARGINS[control]
        passed = (
            mean_delta >= required_margin
            and last16_delta > 0
            and final5_delta > 0
            and adjusted[control] < CONFIRMATORY_ALPHA
            and lcb > 0
        )
        comparisons.append(
            ControlComparison(
                control=control,
                mean_delta=mean_delta,
                last16_delta=last16_delta,
                final5_delta=final5_delta,
                exact_pvalue=raw_pvalues[control],
                holm_pvalue=adjusted[control],
                bootstrap_lcb=lcb,
                required_margin=required_margin,
                passed=passed,
            )
        )

    arm_accuracy = tuple(
        (arm, float(np.mean(matrices[arm]))) for arm in sorted(matrices)
    )
    overall = all(comparison.passed for comparison in comparisons)
    unsigned = {
        "alpha": CONFIRMATORY_ALPHA,
        "arm_accuracy": [
            {"arm": arm, "accuracy": accuracy}
            for arm, accuracy in arm_accuracy
        ],
        "bootstrap_resamples": CONFIRMATORY_BOOTSTRAPS,
        "comparisons": [comparison.canonical() for comparison in comparisons],
        "passed": overall,
        "protocol": PROTOCOL,
        "score_bundle_sha256": score_bundle.score_bundle_sha256,
        "stream_set_validation_sha256": stream_set.validation_sha256,
    }
    return ConfirmatoryVerdict(
        stream_set_validation_sha256=stream_set.validation_sha256,
        score_bundle_sha256=score_bundle.score_bundle_sha256,
        arm_accuracy=arm_accuracy,
        comparisons=tuple(comparisons),
        passed=overall,
        verdict_sha256=canonical_sha256(unsigned),
    )


__all__ = [
    "ArmAnswer",
    "ArmUpdate",
    "AtomicEdge",
    "CONFIRMATORY_ALPHA",
    "CONFIRMATORY_BOOTSTRAPS",
    "CONFIRMATORY_HORIZON",
    "CONFIRMATORY_MARGINS",
    "CONFIRMATORY_STREAMS",
    "ConfirmatoryScoreBundle",
    "ConfirmatoryScoreRow",
    "ConfirmatoryVerdict",
    "ControlComparison",
    "LearningBatch",
    "PROTOCOL",
    "PrequentialArm",
    "PublicLearningToken",
    "PublicProbe",
    "QueryItem",
    "StepResult",
    "StreamManifest",
    "StreamRun",
    "StreamSetValidation",
    "WarmupResult",
    "bootstrap_lcb",
    "canonical_sha256",
    "deterministic_test_seed",
    "exact_sign_flip_pvalue",
    "evaluate_confirmatory",
    "generate_stream",
    "holm_adjust",
    "make_confirmatory_score_bundle",
    "paired_stream_deltas",
    "parse_choice",
    "run_prequential",
    "validate_stream",
    "validate_stream_set",
]
