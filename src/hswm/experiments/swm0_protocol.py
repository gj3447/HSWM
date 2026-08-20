"""Preregistered protocol harness for the narrow SWM-0R witness.

SWM-0R is a deterministic representation/conformance experiment.  It asks
whether a role-bearing, n-ary representation retains information erased by
registered lossy projections.  It does *not* test learned ``Theta/R/W``, equal
compute, recurrence, outcome learning, or readiness for SWM-1.  The next gate
after an admissible SWM-0R result is SWM-0W.

The library API is deliberately side-effect free: it returns content-addressed
manifest and result values but never writes a preregistration, evidence file,
or result log.  The CLI prints canonical JSON by default and writes only when
an explicit ``--output`` path is supplied.  Blocks are the unit of splitting
and diagnostic resampling; the nine sibling cases in a q=3 block are never
split apart.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from hswm.experiments import swm0_operator as operator
from hswm.experiments import swm0_worlds as worlds


PROTOCOL_VERSION = "hswm-swm0r-protocol/v1"
MANIFEST_SCHEMA = "hswm-swm0r-manifest/v1"
RESULT_SCHEMA = "hswm-swm0r-result/v1"
INTEGRITY_SCHEMA = "hswm-swm0r-integrity/v1"
PREREGISTRATION_SCHEMA = "hswm-swm0r-preregistration/v1"

DEFAULT_Q = 3
PILOT_SEEDS = (0, 1, 2)
CONFIRMATORY_SEEDS = tuple(range(100, 120))
CONFIRMATORY_FRESH_BLOCKS = 1
DEFAULT_TRAIN_BLOCKS = 1
DEFAULT_DEV_BLOCKS = 1
DEFAULT_BOOTSTRAP_RESAMPLES = 2_000
DEFAULT_BOOTSTRAP_SEED = 20_260_820
DEFAULT_RIDGE = 1.0e-6

SOURCE_PATHS = (
    "src/hswm/experiments/swm0_worlds.py",
    "src/hswm/experiments/swm0_operator.py",
    "src/hswm/experiments/swm0_protocol.py",
)

TARGET_ARM = operator.SWM0Arm.ROLE_NARY_ONE_SWEEP.value
STAR_ARM = operator.SWM0Arm.TYPED_STAR_EQUIV.value
LOSSY_ARMS = tuple(
    arm.value
    for arm in operator.ALL_ARMS
    if arm not in {
        operator.SWM0Arm.ROLE_NARY_ONE_SWEEP,
        operator.SWM0Arm.TYPED_STAR_EQUIV,
    }
)
ALL_ARMS = tuple(arm.value for arm in operator.ALL_ARMS)

CONTROL_METADATA: dict[str, dict[str, Any]] = {
    operator.SWM0Arm.COSINE_OR_FLAT.value: {
        "display_name": "flat node-multiset ridge",
        "is_measured_cosine": False,
    },
    operator.SWM0Arm.TYPED_CLIQUE_2SECTION.value: {
        "display_name": "typed clique 2-section ridge",
        "may_duplicate": operator.SWM0Arm.PAIRWISE_RELATION_SUM.value,
    },
    operator.SWM0Arm.PAIRWISE_RELATION_SUM.value: {
        "display_name": "pairwise relation-sum ridge",
        "may_duplicate": operator.SWM0Arm.TYPED_CLIQUE_2SECTION.value,
    },
    operator.SWM0Arm.ROLE_SHUFFLE.value: {
        "display_name": "deterministic role-projection ablation",
        "is_stochastic_shuffle": False,
    },
    operator.SWM0Arm.GROUPING_SHUFFLE.value: {
        "display_name": "deterministic grouping-projection ablation",
        "is_stochastic_shuffle": False,
    },
}

LIMITATIONS = (
    "SWM-0R uses a hand-constructed representation and balanced ridge readout; "
    "it is not learned Theta/R/W or semantic-weight efficacy.",
    "TYPED_STAR_EQUIV must carry an independent-compiler attestation; output "
    "parity alone is not evidence of independent implementation.",
    "Parameter parity covers only the nominal dense ridge readout; no "
    "equal-compute, FLOP, latency, or optimization-search claim is made.",
    "COSINE_OR_FLAT is a flat node-multiset ridge control, not a measured "
    "cosine-retrieval implementation.",
    "TYPED_CLIQUE_2SECTION and PAIRWISE_RELATION_SUM may be intentionally "
    "duplicate lossy controls.",
    "ROLE_SHUFFLE and GROUPING_SHUFFLE are deterministic projection ablations, "
    "not sampled stochastic shuffles.",
    "The q=3 fixture has only nine fixed semantic worlds per block. Repeated "
    "fresh blocks test nonce/order robustness; bootstrap intervals over those "
    "repetitions are diagnostic and do not create new semantic support.",
)


class SWM0ProtocolError(ValueError):
    """Raised when a manifest, run, or statistic violates the protocol."""


class RunMode(str, Enum):
    PILOT = "pilot"
    CONFIRMATORY = "confirmatory"


class Verdict(str, Enum):
    PASS = "PASS"
    KILL = "KILL"
    INCONCLUSIVE = "INCONCLUSIVE"
    VOID = "VOID"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if hasattr(value, "canonical"):
        return _jsonable(value.canonical())
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SWM0ProtocolError("canonical JSON cannot contain non-finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise SWM0ProtocolError(f"value is not canonical-JSON compatible: {type(value)!r}")


def canonical_json(value: Any) -> str:
    """Return the one machine-readable JSON encoding used by this protocol."""

    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_sha256(value: str, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SWM0ProtocolError(f"{field} must be a lowercase SHA-256")


def _coerce_mode(mode: RunMode | str) -> RunMode:
    try:
        return mode if isinstance(mode, RunMode) else RunMode(mode)
    except (TypeError, ValueError) as exc:
        raise SWM0ProtocolError(f"unsupported SWM-0R mode: {mode!r}") from exc


@dataclass(frozen=True, slots=True)
class Thresholds:
    effect_floor: float = 0.10
    star_noninferiority: float = -0.02
    star_equivalence_upper: float = 0.02
    chance_margin: float = 0.20
    ablation_removal_fraction: float = 0.70
    irrelevant_removal_rope: float = 0.02
    positive_seeds_required: int = 16
    positive_seeds_total: int = 20

    def __post_init__(self) -> None:
        finite = (
            self.effect_floor,
            self.star_noninferiority,
            self.star_equivalence_upper,
            self.chance_margin,
            self.ablation_removal_fraction,
            self.irrelevant_removal_rope,
        )
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in finite):
            raise SWM0ProtocolError("thresholds must be finite")
        if not 0.0 <= self.ablation_removal_fraction <= 1.0:
            raise SWM0ProtocolError("ablation removal fraction must lie in [0, 1]")
        if self.star_noninferiority >= self.star_equivalence_upper:
            raise SWM0ProtocolError("star equivalence interval is empty")
        if self.irrelevant_removal_rope < 0.0:
            raise SWM0ProtocolError("irrelevant-removal ROPE must be non-negative")
        if not 0 < self.positive_seeds_required <= self.positive_seeds_total:
            raise SWM0ProtocolError("positive-seed rule is invalid")

    def canonical(self) -> dict[str, Any]:
        return {
            "ablation_removal_fraction": self.ablation_removal_fraction,
            "chance_margin": self.chance_margin,
            "effect_floor": self.effect_floor,
            "irrelevant_removal_rope": self.irrelevant_removal_rope,
            "positive_seeds_required": self.positive_seeds_required,
            "positive_seeds_total": self.positive_seeds_total,
            "star_noninferiority": self.star_noninferiority,
            "star_equivalence_upper": self.star_equivalence_upper,
        }


@dataclass(frozen=True, slots=True)
class BootstrapSpec:
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES
    alpha: float = 0.05
    seed: int = DEFAULT_BOOTSTRAP_SEED

    def __post_init__(self) -> None:
        if type(self.resamples) is not int or self.resamples <= 0:
            raise SWM0ProtocolError("bootstrap resamples must be a positive integer")
        if not 0.0 < self.alpha < 1.0:
            raise SWM0ProtocolError("bootstrap alpha must lie in (0, 1)")
        if type(self.seed) is not int or self.seed < 0:
            raise SWM0ProtocolError("bootstrap seed must be a non-negative integer")

    def canonical(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "resamples": self.resamples,
            "seed": self.seed,
        }


def frozen_preregistration_contract() -> dict[str, Any]:
    """Return the exact machine fields a confirmatory prereg must bind."""

    return {
        "arms": list(ALL_ARMS),
        "block_counts": {
            "dev": DEFAULT_DEV_BLOCKS,
            "test": CONFIRMATORY_FRESH_BLOCKS,
            "train": DEFAULT_TRAIN_BLOCKS,
        },
        "bootstrap": BootstrapSpec().canonical(),
        "confirmatory_measurements_run_before_registration": False,
        "lossy_arms": list(LOSSY_ARMS),
        "mode": RunMode.CONFIRMATORY.value,
        "q": DEFAULT_Q,
        "registered_before_measurement": True,
        "ridge": DEFAULT_RIDGE,
        "schema": PREREGISTRATION_SCHEMA,
        "seeds": list(CONFIRMATORY_SEEDS),
        "source_paths": list(SOURCE_PATHS),
        "star_arm": STAR_ARM,
        "target_arm": TARGET_ARM,
        "thresholds": Thresholds().canonical(),
    }


def validate_preregistration_payload(payload: Any) -> str:
    """Validate frozen fields while allowing narrative/disclosure additions."""

    if not isinstance(payload, Mapping):
        raise SWM0ProtocolError("SWM-0R preregistration must be a JSON object")
    expected = frozen_preregistration_contract()
    for field, expected_value in expected.items():
        if field not in payload:
            raise SWM0ProtocolError(
                f"SWM-0R preregistration is missing frozen field {field!r}"
            )
        if canonical_json(payload[field]) != canonical_json(expected_value):
            raise SWM0ProtocolError(
                f"SWM-0R preregistration frozen field drift: {field}"
            )
    frozen = {field: payload[field] for field in expected}
    return canonical_sha256(frozen)


@dataclass(frozen=True, slots=True)
class BlockRef:
    seed: int
    split: str
    block_index: int
    block_uid: str
    seed_sha256: str
    block_sha256: str
    opaque_ids_sha256: str
    lossy_buckets_sha256: str

    def canonical(self) -> dict[str, Any]:
        return {
            "block_index": self.block_index,
            "block_sha256": self.block_sha256,
            "block_uid": self.block_uid,
            "lossy_buckets_sha256": self.lossy_buckets_sha256,
            "opaque_ids_sha256": self.opaque_ids_sha256,
            "seed": self.seed,
            "seed_sha256": self.seed_sha256,
            "split": self.split,
        }


@dataclass(frozen=True, slots=True)
class SWM0Manifest:
    mode: RunMode
    q: int
    seeds: tuple[int, ...]
    block_counts: tuple[tuple[str, int], ...]
    blocks: tuple[BlockRef, ...]
    arms: tuple[str, ...]
    lossy_arms: tuple[str, ...]
    target_arm: str
    star_arm: str
    thresholds: Thresholds
    bootstrap: BootstrapSpec
    ridge: float
    seed_source: str
    operator_version: str
    worlds_version: str
    star_compiler_attestation: Mapping[str, Any]
    preregistration_path: str | None
    preregistration_sha256: str | None
    preregistration_commit: str | None
    source_commit: str | None
    source_sha256: tuple[tuple[str, str], ...]
    manifest_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "arms": list(self.arms),
            "block_counts": dict(self.block_counts),
            "blocks": [block.canonical() for block in self.blocks],
            "bootstrap": self.bootstrap.canonical(),
            "experiment": "SWM-0R_REPRESENTATION_CONFORMANCE",
            "learned_operator_claim": False,
            "lossy_arms": list(self.lossy_arms),
            "mode": self.mode.value,
            "next_gate": "SWM-0W",
            "operator_version": self.operator_version,
            "preregistration": (
                None
                if self.preregistration_path is None
                else {
                    "commit": self.preregistration_commit,
                    "path": self.preregistration_path,
                    "sha256": self.preregistration_sha256,
                }
            ),
            "q": self.q,
            "ridge": self.ridge,
            "schema_version": MANIFEST_SCHEMA,
            "seed_source": self.seed_source,
            "seeds": list(self.seeds),
            "star_arm": self.star_arm,
            "star_compiler_attestation": _jsonable(self.star_compiler_attestation),
            "source_commit": self.source_commit,
            "source_sha256": dict(self.source_sha256),
            "target_arm": self.target_arm,
            "thresholds": self.thresholds.canonical(),
            "worlds_version": self.worlds_version,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "manifest_sha256": self.manifest_sha256}

    def to_json(self) -> str:
        return canonical_json(self.canonical())


@dataclass(frozen=True, slots=True)
class IntegrityReceipt:
    passed: bool
    checks: tuple[tuple[str, bool], ...]
    errors: tuple[str, ...]
    blocks_checked: int
    opaque_ids_checked: int
    lossy_bucket_receipt_sha256: str
    receipt_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "blocks_checked": self.blocks_checked,
            "checks": dict(self.checks),
            "errors": list(self.errors),
            "lossy_bucket_receipt_sha256": self.lossy_bucket_receipt_sha256,
            "opaque_ids_checked": self.opaque_ids_checked,
            "passed": self.passed,
            "schema_version": INTEGRITY_SCHEMA,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    lower: float
    upper: float

    def canonical(self) -> list[float]:
        return [self.lower, self.upper]


@dataclass(frozen=True, slots=True)
class Estimate:
    point: float
    paired_ci: ConfidenceInterval
    two_level_ci: ConfidenceInterval

    def canonical(self) -> dict[str, Any]:
        return {
            "paired_bootstrap_ci": self.paired_ci.canonical(),
            "point": self.point,
            "two_level_bootstrap_ci": self.two_level_ci.canonical(),
        }


@dataclass(frozen=True, slots=True)
class MetricSummary:
    primary_target_minus_lossy: Estimate
    target_minus_star: Estimate
    target_minus_chance: Estimate
    ablation_excess: Estimate
    target_minus_irrelevant_removal: Estimate
    ablation_removal_fraction: float
    positive_seed_count: int
    seed_count: int

    def canonical(self) -> dict[str, Any]:
        return {
            "ablation_excess": self.ablation_excess.canonical(),
            "ablation_removal_fraction": self.ablation_removal_fraction,
            "positive_seed_count": self.positive_seed_count,
            "primary_target_minus_lossy": self.primary_target_minus_lossy.canonical(),
            "seed_count": self.seed_count,
            "target_minus_chance": self.target_minus_chance.canonical(),
            "target_minus_irrelevant_removal": (
                self.target_minus_irrelevant_removal.canonical()
            ),
            "target_minus_star": self.target_minus_star.canonical(),
        }


@dataclass(frozen=True, slots=True)
class Reduction:
    verdict: Verdict
    gates: tuple[tuple[str, bool], ...]
    reason_codes: tuple[str, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "gates": dict(self.gates),
            "reason_codes": list(self.reason_codes),
            "verdict": self.verdict.value,
        }


@dataclass(frozen=True, slots=True)
class BlockScore:
    seed: int
    block_uid: str
    correct_by_arm: tuple[tuple[str, int], ...]
    target_removed_correct: int
    matched_irrelevant_removed_correct: int
    target_restored_correct: int
    total: int
    prediction_sha256: str

    def canonical(self) -> dict[str, Any]:
        return {
            "block_uid": self.block_uid,
            "correct_by_arm": dict(self.correct_by_arm),
            "matched_irrelevant_removed_correct": self.matched_irrelevant_removed_correct,
            "prediction_sha256": self.prediction_sha256,
            "seed": self.seed,
            "target_removed_correct": self.target_removed_correct,
            "target_restored_correct": self.target_restored_correct,
            "total": self.total,
        }


@dataclass(frozen=True, slots=True)
class SWM0Result:
    mode: RunMode
    manifest_sha256: str
    integrity: IntegrityReceipt
    strongest_lossy_arm: str | None
    dev_accuracy_by_lossy_arm: tuple[tuple[str, float], ...]
    model_receipts: tuple[Mapping[str, Any], ...]
    block_scores: tuple[BlockScore, ...]
    metrics: MetricSummary | None
    reduction: Reduction
    result_sha256: str

    @property
    def implementation_status(self) -> str:
        return "IMPLEMENTED" if self.integrity.passed else "PARTIAL"

    @property
    def scientific_status(self) -> str:
        return "UNJUDGED"

    @property
    def claim(self) -> str:
        if self.reduction.verdict is Verdict.PASS:
            return (
                "SWM-0R engineering PASS: on the registered finite synthetic q=3 "
                "fixture, "
                "the deterministic single-sweep role-bearing representation exceeded "
                "the dev-frozen strongest lossy projection by the registered margin; "
                "target-role removal erased the registered share and exact restore "
                "recovered the output. This is a representation/non-collapse and "
                "forward-removal engineering conformance result only; scientific_status "
                "remains UNJUDGED. It does not establish Theta/R/W learning, equal "
                "compute, general semantics, or readiness for SWM-1. It authorizes "
                "work on, but does not pass, the next gate SWM-0W."
            )
        if self.reduction.verdict is Verdict.KILL:
            return (
                "SWM-0R KILL: this constructive implementation failed its registered "
                "finite synthetic testbed conjunction. This does not reject or abandon "
                "HSWM; it blocks promotion of this implementation and requires a new "
                "mechanism and preregistration."
            )
        if self.reduction.verdict is Verdict.VOID:
            return "SWM-0R VOID: protocol integrity failed, so no scientific claim is emitted."
        return (
            "SWM-0R INCONCLUSIVE: the run is diagnostic or its confidence interval "
            "crosses a registered boundary; scientific_status remains UNJUDGED."
        )

    def unsigned(self) -> dict[str, Any]:
        return {
            "block_scores": [row.canonical() for row in self.block_scores],
            "claim": self.claim,
            "control_metadata": CONTROL_METADATA,
            "dev_accuracy_by_lossy_arm": dict(self.dev_accuracy_by_lossy_arm),
            "experiment": "SWM-0R_REPRESENTATION_CONFORMANCE",
            "implementation_status": self.implementation_status,
            "integrity": self.integrity.canonical(),
            "learned_operator_claim": False,
            "limitations": list(LIMITATIONS),
            "manifest_sha256": self.manifest_sha256,
            "metrics": None if self.metrics is None else self.metrics.canonical(),
            "mode": self.mode.value,
            "model_receipts": [_jsonable(item) for item in self.model_receipts],
            "next_gate": "SWM-0W",
            "parity_scope": "NOMINAL_DENSE_READOUT_PARAMETER_COUNT_ONLY",
            "reduction": self.reduction.canonical(),
            "schema_version": RESULT_SCHEMA,
            "scientific_status": self.scientific_status,
            "strongest_lossy_arm": self.strongest_lossy_arm,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "result_sha256": self.result_sha256}

    def to_json(self) -> str:
        return canonical_json(self.canonical())


def fixed_seed_preimage(mode: RunMode | str, seed: int) -> bytes:
    """Return a public, deterministic seed preimage for replayable protocol runs."""

    selected = _coerce_mode(mode)
    if type(seed) is not int or seed < 0:
        raise SWM0ProtocolError("seed must be a non-negative integer")
    return sha256(
        f"{PROTOCOL_VERSION}|fixed-seed|{selected.value}|{seed}".encode("ascii")
    ).digest()


def _seed_map(
    mode: RunMode,
    seeds: Sequence[int],
    supplied: Mapping[int, bytes] | None,
) -> tuple[dict[int, bytes], str]:
    if supplied is None:
        return ({seed: fixed_seed_preimage(mode, seed) for seed in seeds}, "fixed-public")
    if set(supplied) != set(seeds):
        raise SWM0ProtocolError("seed preimages must cover exactly the registered seeds")
    result: dict[int, bytes] = {}
    for seed in seeds:
        preimage = supplied[seed]
        if not isinstance(preimage, bytes) or len(preimage) < 16:
            raise SWM0ProtocolError("every seed preimage must contain at least 128 bits")
        result[seed] = preimage
    if len(set(result.values())) != len(result):
        raise SWM0ProtocolError("seed preimages must be disjoint")
    return result, "external-sealed"


def require_uniform_lossy_buckets(
    digests: Sequence[str], targets: Sequence[int], *, q: int = DEFAULT_Q
) -> dict[str, Any]:
    """Fail unless every exact digest bucket has a uniform q-class target count."""

    if q != worlds.FIELD_ORDER:
        raise SWM0ProtocolError("this fixture implements q=3 only")
    if len(digests) != len(targets) or not digests:
        raise SWM0ProtocolError("digest and target rows must be non-empty and aligned")
    buckets: dict[str, Counter[int]] = defaultdict(Counter)
    for digest, target in zip(digests, targets, strict=True):
        _require_sha256(digest, "lossy digest")
        if type(target) is not int or not 0 <= target < q:
            raise SWM0ProtocolError("targets must be integers in F_q")
        buckets[digest][target] += 1
    if len(buckets) >= len(digests):
        raise SWM0ProtocolError("declared lossy digest has no collision")
    canonical_buckets: list[dict[str, Any]] = []
    for digest, counts in sorted(buckets.items()):
        vector = [counts[index] for index in range(q)]
        if min(vector) <= 0 or len(set(vector)) != 1:
            raise SWM0ProtocolError(
                "lossy digest bucket is not exactly target-uniform"
            )
        canonical_buckets.append(
            {"digest": digest, "target_counts": vector, "total": sum(vector)}
        )
    result = {
        "bucket_count": len(canonical_buckets),
        "buckets": canonical_buckets,
        "q": q,
    }
    return {**result, "receipt_sha256": canonical_sha256(result)}


def _opaque_ids(block: worlds.WorldBlockV1) -> frozenset[str]:
    result = {block.block_uid}
    for case in block.cases:
        result.add(case.case_uid)
        result.update(node.uid for node in case.world.nodes)
        result.update(edge.uid for edge in case.world.edges)
    return frozenset(result)


def _feature_digest(world: worlds.WorldV1, arm: str) -> str:
    return canonical_sha256(operator.semantic_feature_map(world, arm))


def _audit_block(
    block: worlds.WorldBlockV1,
    *,
    lossy_arms: Sequence[str],
    q: int,
) -> tuple[str, str, frozenset[str]]:
    if q != worlds.FIELD_ORDER or len(block.cases) != q**2:
        raise SWM0ProtocolError("block is not the registered q=3 Cartesian fixture")
    targets = [case.target for case in block.cases]
    for case in block.cases:
        if worlds.constructive_target(case.world) != case.target:
            raise SWM0ProtocolError("constructive target disagrees with evaluator target")
    full_digests = [worlds.full_sha256(case.world) for case in block.cases]
    if len(set(full_digests)) != q**2:
        raise SWM0ProtocolError("full n-ary representation collapsed sibling worlds")
    star_parity_rows: list[str] = []
    for case in block.cases:
        target_features = operator.semantic_feature_map(case.world, TARGET_ARM)
        star_features = operator.semantic_feature_map(case.world, STAR_ARM)
        if target_features != star_features:
            raise SWM0ProtocolError(
                "native target and independent typed-star features differ"
            )
        star_parity_rows.append(canonical_sha256(target_features))

    bucket_receipts: dict[str, Any] = {}
    projections = {
        "pairwise": [worlds.pairwise_sha256(case.world) for case in block.cases],
        "role_stripped": [
            worlds.role_stripped_sha256(case.world) for case in block.cases
        ],
        "flat": [worlds.flat_sha256(case.world) for case in block.cases],
    }
    for name, digests in projections.items():
        bucket_receipts[f"projection:{name}"] = require_uniform_lossy_buckets(
            digests, targets, q=q
        )
    for arm in lossy_arms:
        bucket_receipts[f"arm:{arm}"] = require_uniform_lossy_buckets(
            [_feature_digest(case.world, arm) for case in block.cases],
            targets,
            q=q,
        )

    ids = _opaque_ids(block)
    opaque_digest = canonical_sha256(sorted(ids))
    lossy_digest = canonical_sha256(
        {"lossy_buckets": bucket_receipts, "star_parity": star_parity_rows}
    )
    return opaque_digest, lossy_digest, ids


def _star_attestation() -> dict[str, Any]:
    """Read an explicit independent-compiler attestation, failing closed if absent."""

    independent = getattr(operator, "STAR_COMPILER_INDEPENDENT", None) is True
    paths = getattr(operator, "ENCODER_PATHS", None)
    if not isinstance(paths, Mapping):
        return {
            "independent": False,
            "reason": "operator did not expose ENCODER_PATHS",
        }
    target_id = paths.get(operator.SWM0Arm.ROLE_NARY_ONE_SWEEP)
    star_id = paths.get(operator.SWM0Arm.TYPED_STAR_EQUIV)
    valid = (
        independent
        and isinstance(target_id, str)
        and isinstance(star_id, str)
        and bool(target_id)
        and bool(star_id)
        and target_id != star_id
    )
    return {
        "independent": valid,
        "operator_attestation": independent,
        "star_compiler_id": star_id,
        "target_compiler_id": target_id,
    }


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_preregistration_binding(
    path: str | Path,
    expected_sha256: str,
    *,
    require_committed: bool,
) -> tuple[str, str | None]:
    """Verify a prereg file and, for confirmatory use, its clean HEAD binding."""

    _require_sha256(expected_sha256, "preregistration_sha256")
    prereg = Path(path).expanduser().resolve()
    if not prereg.is_file():
        raise SWM0ProtocolError("preregistration path is not a regular file")
    root = _repository_root().resolve()
    try:
        relative = prereg.relative_to(root).as_posix()
    except ValueError as exc:
        raise SWM0ProtocolError(
            "SWM-0R preregistration must live inside repository prereg/"
        ) from exc
    relative_path = Path(relative)
    if (
        not relative_path.parts
        or relative_path.parts[0] != "prereg"
        or relative_path.suffix != ".json"
    ):
        raise SWM0ProtocolError(
            "SWM-0R preregistration must be a JSON file under prereg/"
        )
    if relative in SOURCE_PATHS:
        raise SWM0ProtocolError("preregistration path collides with protocol source")
    if _file_sha256(prereg) != expected_sha256:
        raise SWM0ProtocolError("preregistration SHA-256 mismatch")

    def reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SWM0ProtocolError(
                    f"preregistration JSON contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            prereg.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SWM0ProtocolError("preregistration is not valid UTF-8 JSON") from exc
    validate_preregistration_payload(payload)
    if not require_committed:
        return relative, None

    try:
        subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            check=True,
            capture_output=True,
        )
        head_bytes = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{relative}"],
            check=True,
            capture_output=True,
        ).stdout
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise SWM0ProtocolError(
            "confirmatory preregistration must be tracked in repository HEAD"
        ) from exc
    if sha256(head_bytes).hexdigest() != expected_sha256:
        raise SWM0ProtocolError(
            "confirmatory preregistration bytes differ from committed HEAD"
        )
    return relative, commit


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _working_source_binding(
    preregistration_path: str | Path | None,
) -> tuple[tuple[str, str], ...]:
    root = _repository_root()
    paths = list(SOURCE_PATHS)
    if preregistration_path is not None:
        prereg = Path(preregistration_path)
        if prereg.is_absolute():
            try:
                prereg = prereg.resolve().relative_to(root)
            except ValueError as exc:
                raise SWM0ProtocolError(
                    "preregistration must be inside the repository"
                ) from exc
        paths.append(prereg.as_posix())
    result: list[tuple[str, str]] = []
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise SWM0ProtocolError(f"bound source path is missing: {relative}")
        result.append((relative, _file_sha256(path)))
    return tuple(result)


def _committed_source_binding(
    preregistration_path: str,
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Bind protocol sources and prereg to identical working/HEAD bytes."""

    root = _repository_root()
    paths = (*SOURCE_PATHS, preregistration_path)
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        result: list[tuple[str, str]] = []
        for relative in paths:
            current = root / relative
            if not current.is_file():
                raise SWM0ProtocolError(f"bound source path is missing: {relative}")
            subprocess.run(
                ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
                check=True,
                capture_output=True,
            )
            head_bytes = subprocess.run(
                ["git", "-C", str(root), "show", f"HEAD:{relative}"],
                check=True,
                capture_output=True,
            ).stdout
            current_sha = _file_sha256(current)
            if sha256(head_bytes).hexdigest() != current_sha:
                raise SWM0ProtocolError(
                    f"confirmatory source differs from committed HEAD: {relative}"
                )
            result.append((relative, current_sha))
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SWM0ProtocolError(
            "confirmatory sources must be tracked and byte-identical to HEAD"
        ) from exc
    return commit, tuple(result)


def build_manifest(
    mode: RunMode | str = RunMode.PILOT,
    *,
    train_blocks: int | None = None,
    dev_blocks: int | None = None,
    fresh_blocks: int | None = None,
    thresholds: Thresholds = Thresholds(),
    bootstrap: BootstrapSpec = BootstrapSpec(),
    ridge: float = DEFAULT_RIDGE,
    seed_preimages: Mapping[int, bytes] | None = None,
    preregistration_path: str | Path | None = None,
    preregistration_sha256: str | None = None,
    preregistration_commit: str | None = None,
) -> SWM0Manifest:
    """Build and content-bind a pilot or confirmatory block manifest.

    Pilot seeds are exactly ``[0, 1, 2]``.  Confirmatory seeds are exactly
    ``range(100, 120)`` with one exhaustive semantic block in each split.
    Repetition across confirmatory seeds tests nonce/order robustness only.
    """

    selected = _coerce_mode(mode)
    if not isinstance(ridge, (int, float)) or not math.isfinite(ridge) or ridge <= 0.0:
        raise SWM0ProtocolError("ridge must be finite and positive")
    ridge = float(ridge)
    seeds = PILOT_SEEDS if selected is RunMode.PILOT else CONFIRMATORY_SEEDS
    if train_blocks is None:
        train_blocks = 1 if selected is RunMode.PILOT else DEFAULT_TRAIN_BLOCKS
    if dev_blocks is None:
        dev_blocks = 1 if selected is RunMode.PILOT else DEFAULT_DEV_BLOCKS
    if fresh_blocks is None:
        fresh_blocks = 1 if selected is RunMode.PILOT else CONFIRMATORY_FRESH_BLOCKS
    counts = {"train": train_blocks, "dev": dev_blocks, "test": fresh_blocks}
    if any(type(count) is not int or count <= 0 for count in counts.values()):
        raise SWM0ProtocolError("every split requires a positive block count")
    if selected is RunMode.CONFIRMATORY and counts != {
        "train": DEFAULT_TRAIN_BLOCKS,
        "dev": DEFAULT_DEV_BLOCKS,
        "test": CONFIRMATORY_FRESH_BLOCKS,
    }:
        raise SWM0ProtocolError(
            "confirmatory block counts must be exactly train=1, dev=1, test=1"
        )

    if selected is RunMode.CONFIRMATORY:
        if thresholds != Thresholds():
            raise SWM0ProtocolError("confirmatory thresholds differ from the frozen defaults")
        if bootstrap != BootstrapSpec():
            raise SWM0ProtocolError("confirmatory bootstrap differs from the frozen defaults")
        if ridge != DEFAULT_RIDGE:
            raise SWM0ProtocolError("confirmatory ridge differs from the frozen default")
        if seed_preimages is not None:
            raise SWM0ProtocolError("confirmatory seeds use the fixed preregistered preimages")
        if preregistration_path is None or preregistration_sha256 is None:
            raise SWM0ProtocolError(
                "confirmatory manifests require a committed preregistration binding"
            )
    if (preregistration_path is None) != (preregistration_sha256 is None):
        raise SWM0ProtocolError(
            "preregistration path and SHA-256 must be supplied together"
        )
    if preregistration_sha256 is not None:
        _require_sha256(preregistration_sha256, "preregistration_sha256")

    source_commit: str | None = None
    if selected is RunMode.CONFIRMATORY:
        assert preregistration_path is not None
        assert preregistration_sha256 is not None
        bound_path, derived_commit = validate_preregistration_binding(
            preregistration_path,
            preregistration_sha256,
            require_committed=True,
        )
        if preregistration_commit is not None and preregistration_commit != derived_commit:
            raise SWM0ProtocolError("caller-supplied preregistration commit mismatch")
        preregistration_path = bound_path
        preregistration_commit = derived_commit
        source_commit, source_sha256 = _committed_source_binding(bound_path)
        if source_commit != derived_commit:
            raise SWM0ProtocolError("preregistration and protocol source commits differ")
    else:
        source_sha256 = _working_source_binding(preregistration_path)

    preimages, seed_source = _seed_map(selected, seeds, seed_preimages)
    refs: list[BlockRef] = []
    seen_ids: set[str] = set()
    for seed in seeds:
        for split in ("train", "dev", "test"):
            for block_index in range(counts[split]):
                block = worlds.generate_block(
                    split=split,
                    block_index=block_index,
                    seed_preimage=preimages[seed],
                )
                opaque_digest, lossy_digest, identifiers = _audit_block(
                    block, lossy_arms=LOSSY_ARMS, q=DEFAULT_Q
                )
                overlap = seen_ids.intersection(identifiers)
                if overlap:
                    raise SWM0ProtocolError(
                        "opaque identifiers overlap across split-atomic blocks"
                    )
                seen_ids.update(identifiers)
                refs.append(
                    BlockRef(
                        seed=seed,
                        split=split,
                        block_index=block_index,
                        block_uid=block.block_uid,
                        seed_sha256=block.seed_sha256,
                        block_sha256=block.block_sha256,
                        opaque_ids_sha256=opaque_digest,
                        lossy_buckets_sha256=lossy_digest,
                    )
                )

    unsigned_manifest = SWM0Manifest(
        mode=selected,
        q=DEFAULT_Q,
        seeds=tuple(seeds),
        block_counts=tuple(counts.items()),
        blocks=tuple(refs),
        arms=ALL_ARMS,
        lossy_arms=LOSSY_ARMS,
        target_arm=TARGET_ARM,
        star_arm=STAR_ARM,
        thresholds=thresholds,
        bootstrap=bootstrap,
        ridge=ridge,
        seed_source=seed_source,
        operator_version=operator.OPERATOR_VERSION,
        worlds_version=worlds.PROTOCOL_VERSION,
        star_compiler_attestation=_star_attestation(),
        preregistration_path=(
            None if preregistration_path is None else str(preregistration_path)
        ),
        preregistration_sha256=preregistration_sha256,
        preregistration_commit=preregistration_commit,
        source_commit=source_commit,
        source_sha256=source_sha256,
        manifest_sha256="0" * 64,
    )
    return replace(
        unsigned_manifest,
        manifest_sha256=canonical_sha256(unsigned_manifest.unsigned()),
    )


def _resolve_manifest_preimages(
    manifest: SWM0Manifest,
    supplied: Mapping[int, bytes] | None,
) -> dict[int, bytes]:
    if manifest.seed_source == "fixed-public":
        if supplied is not None:
            raise SWM0ProtocolError(
                "fixed-public manifests do not accept replacement seed preimages"
            )
        return {
            seed: fixed_seed_preimage(manifest.mode, seed) for seed in manifest.seeds
        }
    if manifest.seed_source != "external-sealed":
        raise SWM0ProtocolError("unknown manifest seed source")
    values, _ = _seed_map(manifest.mode, manifest.seeds, supplied)
    return values


def _expected_seed_contract(manifest: SWM0Manifest) -> None:
    expected = PILOT_SEEDS if manifest.mode is RunMode.PILOT else CONFIRMATORY_SEEDS
    if manifest.seeds != expected:
        raise SWM0ProtocolError("manifest seed set differs from the fixed mode contract")
    if manifest.q != DEFAULT_Q:
        raise SWM0ProtocolError("manifest q differs from the q=3 world contract")
    if manifest.arms != ALL_ARMS or manifest.lossy_arms != LOSSY_ARMS:
        raise SWM0ProtocolError("manifest arm set differs from the registered operator")
    if manifest.target_arm != TARGET_ARM or manifest.star_arm != STAR_ARM:
        raise SWM0ProtocolError("manifest target/star identity drift")
    if manifest.operator_version != operator.OPERATOR_VERSION:
        raise SWM0ProtocolError("operator version drift")
    if manifest.worlds_version != worlds.PROTOCOL_VERSION:
        raise SWM0ProtocolError("world generator version drift")
    if (
        not isinstance(manifest.ridge, (int, float))
        or not math.isfinite(manifest.ridge)
        or manifest.ridge <= 0.0
    ):
        raise SWM0ProtocolError("manifest ridge is invalid")
    counts = dict(manifest.block_counts)
    if set(counts) != {"train", "dev", "test"}:
        raise SWM0ProtocolError("manifest must bind train/dev/test block counts")
    if any(type(value) is not int or value <= 0 for value in counts.values()):
        raise SWM0ProtocolError("manifest block counts must be positive integers")
    if manifest.mode is RunMode.CONFIRMATORY:
        if counts != {
            "train": DEFAULT_TRAIN_BLOCKS,
            "dev": DEFAULT_DEV_BLOCKS,
            "test": CONFIRMATORY_FRESH_BLOCKS,
        }:
            raise SWM0ProtocolError(
                "confirmatory block counts differ from the registered 1/1/1 contract"
            )
        if manifest.thresholds != Thresholds():
            raise SWM0ProtocolError("confirmatory threshold contract drift")
        if manifest.bootstrap != BootstrapSpec():
            raise SWM0ProtocolError("confirmatory bootstrap contract drift")
        if manifest.ridge != DEFAULT_RIDGE:
            raise SWM0ProtocolError("confirmatory ridge contract drift")
        if manifest.seed_source != "fixed-public":
            raise SWM0ProtocolError("confirmatory seed-source contract drift")
        if (
            manifest.preregistration_path is None
            or manifest.preregistration_sha256 is None
            or manifest.preregistration_commit is None
        ):
            raise SWM0ProtocolError(
                "confirmatory manifest lacks committed preregistration binding"
            )
        prereg_path = Path(manifest.preregistration_path)
        if not prereg_path.is_absolute():
            prereg_path = Path(__file__).resolve().parents[3] / prereg_path
        bound_path, commit = validate_preregistration_binding(
            prereg_path,
            manifest.preregistration_sha256,
            require_committed=True,
        )
        if bound_path != manifest.preregistration_path:
            raise SWM0ProtocolError("confirmatory preregistration path binding drift")
        if commit != manifest.preregistration_commit:
            raise SWM0ProtocolError("confirmatory preregistration HEAD commit drift")
        source_commit, source_sha256 = _committed_source_binding(bound_path)
        if source_commit != manifest.source_commit:
            raise SWM0ProtocolError("confirmatory source HEAD commit drift")
        if source_sha256 != manifest.source_sha256:
            raise SWM0ProtocolError("confirmatory source SHA-256 binding drift")
    else:
        if manifest.source_commit is not None:
            raise SWM0ProtocolError("pilot manifest must not claim a committed source cut")
        if _working_source_binding(manifest.preregistration_path) != manifest.source_sha256:
            raise SWM0ProtocolError("pilot source SHA-256 binding drift")
    if manifest.preregistration_sha256 is not None:
        _require_sha256(
            manifest.preregistration_sha256, "preregistration_sha256"
        )


def validate_manifest(
    manifest: SWM0Manifest,
    *,
    seed_preimages: Mapping[int, bytes] | None = None,
) -> IntegrityReceipt:
    """Replay every registered block and validate all information firewalls."""

    _expected_seed_contract(manifest)
    if canonical_sha256(manifest.unsigned()) != manifest.manifest_sha256:
        raise SWM0ProtocolError("manifest content hash mismatch")
    _require_sha256(manifest.manifest_sha256, "manifest_sha256")
    preimages = _resolve_manifest_preimages(manifest, seed_preimages)
    expected_order = [
        (seed, split, index)
        for seed in manifest.seeds
        for split in ("train", "dev", "test")
        for index in range(dict(manifest.block_counts)[split])
    ]
    observed_order = [
        (block.seed, block.split, block.block_index) for block in manifest.blocks
    ]
    if observed_order != expected_order:
        raise SWM0ProtocolError("manifest block order or split allocation drift")

    seen_ids: set[str] = set()
    lossy_receipts: list[str] = []
    for reference in manifest.blocks:
        block = worlds.generate_block(
            split=reference.split,
            block_index=reference.block_index,
            seed_preimage=preimages[reference.seed],
        )
        opaque_digest, lossy_digest, identifiers = _audit_block(
            block, lossy_arms=manifest.lossy_arms, q=manifest.q
        )
        expected = BlockRef(
            seed=reference.seed,
            split=reference.split,
            block_index=reference.block_index,
            block_uid=block.block_uid,
            seed_sha256=block.seed_sha256,
            block_sha256=block.block_sha256,
            opaque_ids_sha256=opaque_digest,
            lossy_buckets_sha256=lossy_digest,
        )
        if reference != expected:
            raise SWM0ProtocolError("registered block differs from deterministic replay")
        overlap = seen_ids.intersection(identifiers)
        if overlap:
            raise SWM0ProtocolError(
                "opaque identifiers overlap across train/dev/test blocks"
            )
        seen_ids.update(identifiers)
        lossy_receipts.append(lossy_digest)

    star_attestation = _star_attestation()
    attestation_matches = (
        _jsonable(manifest.star_compiler_attestation) == star_attestation
    )
    star_independent = star_attestation.get("independent") is True
    checks = (
        ("block_level_split", True),
        ("deterministic_block_replay", True),
        ("disjoint_opaque_ids", True),
        ("exact_uniform_lossy_buckets", True),
        ("manifest_hash", True),
        ("star_attestation_unchanged", attestation_matches),
        ("typed_star_independent_compiler", star_independent),
    )
    errors = tuple(name for name, passed in checks if not passed)
    unsigned = {
        "blocks_checked": len(manifest.blocks),
        "checks": dict(checks),
        "errors": list(errors),
        "lossy_bucket_receipt_sha256": canonical_sha256(lossy_receipts),
        "opaque_ids_checked": len(seen_ids),
        "passed": not errors,
        "schema_version": INTEGRITY_SCHEMA,
    }
    return IntegrityReceipt(
        passed=not errors,
        checks=checks,
        errors=errors,
        blocks_checked=len(manifest.blocks),
        opaque_ids_checked=len(seen_ids),
        lossy_bucket_receipt_sha256=canonical_sha256(lossy_receipts),
        receipt_sha256=canonical_sha256(unsigned),
    )


def paired_bootstrap_ci(
    values: Sequence[float], *, spec: BootstrapSpec = BootstrapSpec()
) -> ConfidenceInterval:
    """Percentile CI from paired block differences."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or not array.size or not np.isfinite(array).all():
        raise SWM0ProtocolError("paired bootstrap requires finite one-dimensional data")
    rng = np.random.Generator(np.random.PCG64(spec.seed))
    indices = rng.integers(0, array.size, size=(spec.resamples, array.size))
    estimates = array[indices].mean(axis=1)
    lower, upper = np.quantile(
        estimates, [spec.alpha / 2.0, 1.0 - spec.alpha / 2.0]
    )
    return ConfidenceInterval(float(lower), float(upper))


def two_level_bootstrap_ci(
    values_by_seed: Mapping[int, Sequence[float]],
    *,
    spec: BootstrapSpec = BootstrapSpec(),
) -> ConfidenceInterval:
    """Resample seeds, then blocks within each sampled seed."""

    if not values_by_seed:
        raise SWM0ProtocolError("two-level bootstrap requires at least one seed")
    seeds = tuple(sorted(values_by_seed))
    arrays = {
        seed: np.asarray(values_by_seed[seed], dtype=np.float64) for seed in seeds
    }
    if any(
        values.ndim != 1 or not values.size or not np.isfinite(values).all()
        for values in arrays.values()
    ):
        raise SWM0ProtocolError("each seed requires finite block-level values")
    rng = np.random.Generator(np.random.PCG64(spec.seed))
    estimates = np.empty(spec.resamples, dtype=np.float64)
    for replicate in range(spec.resamples):
        sampled_seed_indices = rng.integers(0, len(seeds), size=len(seeds))
        seed_means: list[float] = []
        for seed_index in sampled_seed_indices:
            values = arrays[seeds[int(seed_index)]]
            block_indices = rng.integers(0, values.size, size=values.size)
            seed_means.append(float(values[block_indices].mean()))
        estimates[replicate] = float(np.mean(seed_means))
    lower, upper = np.quantile(
        estimates, [spec.alpha / 2.0, 1.0 - spec.alpha / 2.0]
    )
    return ConfidenceInterval(float(lower), float(upper))


def _estimate(
    values_by_seed: Mapping[int, Sequence[float]], *, spec: BootstrapSpec
) -> Estimate:
    flat = [value for seed in sorted(values_by_seed) for value in values_by_seed[seed]]
    seed_means = [float(np.mean(values_by_seed[seed])) for seed in sorted(values_by_seed)]
    return Estimate(
        point=float(np.mean(seed_means)),
        paired_ci=paired_bootstrap_ci(flat, spec=spec),
        two_level_ci=two_level_bootstrap_ci(values_by_seed, spec=spec),
    )


def summarize_metrics(
    rows: Sequence[BlockScore],
    *,
    strongest_lossy_arm: str,
    q: int,
    thresholds: Thresholds,
    bootstrap: BootstrapSpec,
) -> MetricSummary:
    if strongest_lossy_arm not in LOSSY_ARMS:
        raise SWM0ProtocolError("strongest lossy arm is not registered")
    grouped: dict[str, dict[int, list[float]]] = {
        name: defaultdict(list)
        for name in (
            "primary",
            "star",
            "chance",
            "ablation_excess",
            "irrelevant_removal",
        )
    }
    primary_seed_means: dict[int, list[float]] = defaultdict(list)
    removal_losses: list[float] = []
    primary_gains: list[float] = []
    for row in rows:
        scores = dict(row.correct_by_arm)
        if set(scores) != set(ALL_ARMS):
            raise SWM0ProtocolError("block score does not contain every registered arm")
        total = float(row.total)
        target = scores[TARGET_ARM] / total
        lossy = scores[strongest_lossy_arm] / total
        star = scores[STAR_ARM] / total
        removed = row.target_removed_correct / total
        irrelevant_removed = row.matched_irrelevant_removed_correct / total
        primary = target - lossy
        removal_loss = target - removed
        values = {
            "primary": primary,
            "star": target - star,
            "chance": target - (1.0 / q),
            "ablation_excess": (
                removal_loss - thresholds.ablation_removal_fraction * primary
            ),
            "irrelevant_removal": target - irrelevant_removed,
        }
        for name, value in values.items():
            grouped[name][row.seed].append(value)
        primary_seed_means[row.seed].append(primary)
        removal_losses.append(removal_loss)
        primary_gains.append(primary)

    denominator = float(np.mean(primary_gains))
    removal_fraction = (
        float(np.mean(removal_losses)) / denominator if denominator > 0.0 else 0.0
    )
    positive = sum(
        float(np.mean(values)) > 0.0 for values in primary_seed_means.values()
    )
    return MetricSummary(
        primary_target_minus_lossy=_estimate(grouped["primary"], spec=bootstrap),
        target_minus_star=_estimate(grouped["star"], spec=bootstrap),
        target_minus_chance=_estimate(grouped["chance"], spec=bootstrap),
        ablation_excess=_estimate(grouped["ablation_excess"], spec=bootstrap),
        target_minus_irrelevant_removal=_estimate(
            grouped["irrelevant_removal"], spec=bootstrap
        ),
        ablation_removal_fraction=removal_fraction,
        positive_seed_count=positive,
        seed_count=len(primary_seed_means),
    )


def reduce_verdict(
    mode: RunMode | str,
    integrity: IntegrityReceipt,
    metrics: MetricSummary | None,
    *,
    thresholds: Thresholds = Thresholds(),
) -> Reduction:
    """Apply the frozen PASS/KILL/INCONCLUSIVE/VOID conjunction."""

    selected = _coerce_mode(mode)
    if not integrity.passed:
        return Reduction(
            verdict=Verdict.VOID,
            gates=tuple(integrity.checks),
            reason_codes=("INTEGRITY_FAILURE", *integrity.errors),
        )
    if metrics is None:
        return Reduction(
            verdict=Verdict.VOID,
            gates=(("metrics_present", False),),
            reason_codes=("MISSING_METRICS",),
        )

    primary = metrics.primary_target_minus_lossy.two_level_ci
    star = metrics.target_minus_star.two_level_ci
    chance = metrics.target_minus_chance.two_level_ci
    ablation = metrics.ablation_excess.two_level_ci
    irrelevant = metrics.target_minus_irrelevant_removal.two_level_ci
    gates = (
        ("primary_effect_lcb", primary.lower >= thresholds.effect_floor),
        (
            "star_equivalence_rope",
            star.lower >= thresholds.star_noninferiority
            and star.upper <= thresholds.star_equivalence_upper,
        ),
        ("chance_margin_lcb", chance.lower >= thresholds.chance_margin),
        ("ablation_removal_lcb", ablation.lower >= 0.0),
        (
            "matched_irrelevant_removal_specificity",
            irrelevant.lower >= -thresholds.irrelevant_removal_rope
            and irrelevant.upper <= thresholds.irrelevant_removal_rope,
        ),
        (
            "positive_seed_direction",
            metrics.seed_count == thresholds.positive_seeds_total
            and metrics.positive_seed_count >= thresholds.positive_seeds_required,
        ),
    )
    if selected is RunMode.PILOT:
        return Reduction(
            verdict=Verdict.INCONCLUSIVE,
            gates=gates,
            reason_codes=("PILOT_DIAGNOSTIC_ONLY",),
        )
    if metrics.seed_count != thresholds.positive_seeds_total:
        return Reduction(
            verdict=Verdict.VOID,
            gates=gates,
            reason_codes=("CONFIRMATORY_SEED_COUNT_DRIFT",),
        )
    if all(passed for _, passed in gates):
        return Reduction(verdict=Verdict.PASS, gates=gates, reason_codes=("ALL_GATES_PASS",))

    decisive_failures: list[str] = []
    if primary.upper < thresholds.effect_floor:
        decisive_failures.append("PRIMARY_EFFECT_BELOW_FLOOR")
    if (
        star.upper < thresholds.star_noninferiority
        or star.lower > thresholds.star_equivalence_upper
    ):
        decisive_failures.append("STAR_EQUIVALENCE_FAILED")
    if chance.upper < thresholds.chance_margin:
        decisive_failures.append("CHANCE_MARGIN_FAILED")
    if ablation.upper < 0.0:
        decisive_failures.append("ABLATION_REMOVAL_FAILED")
    if (
        irrelevant.upper < -thresholds.irrelevant_removal_rope
        or irrelevant.lower > thresholds.irrelevant_removal_rope
    ):
        decisive_failures.append("IRRELEVANT_REMOVAL_SPECIFICITY_FAILED")
    if metrics.positive_seed_count < thresholds.positive_seeds_required:
        decisive_failures.append("SEED_DIRECTION_FAILED")
    if decisive_failures:
        return Reduction(
            verdict=Verdict.KILL,
            gates=gates,
            reason_codes=tuple(decisive_failures),
        )
    return Reduction(
        verdict=Verdict.INCONCLUSIVE,
        gates=gates,
        reason_codes=("CONFIDENCE_INTERVAL_CROSSES_GATE",),
    )


def _blocks_for(
    manifest: SWM0Manifest,
    preimages: Mapping[int, bytes],
    *,
    seed: int,
    split: str,
) -> tuple[worlds.WorldBlockV1, ...]:
    references = [
        ref for ref in manifest.blocks if ref.seed == seed and ref.split == split
    ]
    return tuple(
        worlds.generate_block(
            split=split,
            block_index=reference.block_index,
            seed_preimage=preimages[seed],
        )
        for reference in references
    )


def _model_receipt(
    seed: int,
    arm: str,
    model: operator.BalancedRidgeReadout,
    representative_world: worlds.WorldV1,
) -> dict[str, Any]:
    cost = model.encoder_operation_estimate(representative_world)
    return {
        "arm": arm,
        "effective_feature_count": model.effective_feature_count,
        "encoder_cost_scope": "STRUCTURAL_UNITS_NOT_FLOPS_OR_EQUAL_COMPUTE",
        "encoder_operation_estimate": {
            "feature_products": cost.feature_products,
            "incidence_visits": cost.incidence_visits,
            "node_visits": cost.node_visits,
            "pair_terms": cost.pair_terms,
            "total_units": cost.total_units,
            "uid_hashes": cost.uid_hashes,
        },
        "parameter_count": model.parameter_count,
        "ridge": model.ridge,
        "seed": seed,
        "state_sha256": model.state_sha256,
    }


def _correct(predictions: Sequence[int], cases: Sequence[worlds.WorldCaseV1]) -> int:
    if len(predictions) != len(cases):
        raise SWM0ProtocolError("prediction count differs from case count")
    result = 0
    for prediction, case in zip(predictions, cases, strict=True):
        if type(prediction) is not int or not 0 <= prediction < DEFAULT_Q:
            raise SWM0ProtocolError("model emitted a prediction outside F_3")
        result += int(prediction == case.target)
    return result


def _score_fresh_block(
    seed: int,
    block: worlds.WorldBlockV1,
    models: Mapping[str, operator.BalancedRidgeReadout],
) -> tuple[BlockScore, list[str]]:
    cases = block.cases
    predictions: dict[str, list[int]] = {
        arm: [models[arm].predict(case.world) for case in cases] for arm in ALL_ARMS
    }
    repeated_target = [models[TARGET_ARM].predict(case.world) for case in cases]
    errors: list[str] = []
    if repeated_target != predictions[TARGET_ARM]:
        errors.append("TARGET_PREDICTION_REPLAY_DRIFT")

    removed_predictions: list[int] = []
    irrelevant_predictions: list[int] = []
    restored_predictions: list[int] = []
    intervention_receipts: list[dict[str, Any]] = []
    for case in cases:
        role_edges = [
            edge for edge in case.world.edges if edge.relation_type == worlds.ROLE_RELATION
        ]
        grouping_edges = sorted(
            (
                edge
                for edge in case.world.edges
                if edge.relation_type == worlds.GROUPING_RELATION
            ),
            key=lambda edge: edge.uid,
        )
        if len(role_edges) != 1 or not grouping_edges:
            raise SWM0ProtocolError("fresh case lacks registered intervention edges")
        removed_world, receipt = worlds.remove_edge(case.world, role_edges[0].uid)
        restored_world = worlds.restore_edge(removed_world, receipt)
        irrelevant_world, irrelevant_receipt = worlds.remove_edge(
            case.world, grouping_edges[0].uid
        )
        if restored_world.artifact_sha256 != case.world.artifact_sha256:
            errors.append("EXACT_WORLD_RESTORE_FAILED")
        removed_predictions.append(models[TARGET_ARM].predict(removed_world))
        irrelevant_predictions.append(models[TARGET_ARM].predict(irrelevant_world))
        restored_predictions.append(models[TARGET_ARM].predict(restored_world))
        intervention_receipts.append(
            {
                "irrelevant_removal": irrelevant_receipt.receipt_sha256,
                "target_removal": receipt.receipt_sha256,
            }
        )
    if restored_predictions != predictions[TARGET_ARM]:
        errors.append("EXACT_PREDICTION_RESTORE_FAILED")
    correct_by_arm = tuple(
        (arm, _correct(predictions[arm], cases)) for arm in ALL_ARMS
    )
    prediction_payload = {
        "arm_predictions": predictions,
        "intervention_receipts": intervention_receipts,
        "irrelevant_removed": irrelevant_predictions,
        "restored": restored_predictions,
        "target_removed": removed_predictions,
    }
    return (
        BlockScore(
            seed=seed,
            block_uid=block.block_uid,
            correct_by_arm=correct_by_arm,
            target_removed_correct=_correct(removed_predictions, cases),
            matched_irrelevant_removed_correct=_correct(irrelevant_predictions, cases),
            target_restored_correct=_correct(restored_predictions, cases),
            total=len(cases),
            prediction_sha256=canonical_sha256(prediction_payload),
        ),
        errors,
    )


def _void_result(
    manifest: SWM0Manifest,
    integrity: IntegrityReceipt,
    *,
    model_receipts: Sequence[Mapping[str, Any]] = (),
    block_scores: Sequence[BlockScore] = (),
    errors: Sequence[str] = (),
) -> SWM0Result:
    checks = tuple(integrity.checks) + tuple((error, False) for error in errors)
    combined_errors = tuple(dict.fromkeys((*integrity.errors, *errors)))
    unsigned_integrity = {
        "blocks_checked": integrity.blocks_checked,
        "checks": dict(checks),
        "errors": list(combined_errors),
        "lossy_bucket_receipt_sha256": integrity.lossy_bucket_receipt_sha256,
        "opaque_ids_checked": integrity.opaque_ids_checked,
        "passed": False,
        "schema_version": INTEGRITY_SCHEMA,
    }
    failed_integrity = IntegrityReceipt(
        passed=False,
        checks=checks,
        errors=combined_errors,
        blocks_checked=integrity.blocks_checked,
        opaque_ids_checked=integrity.opaque_ids_checked,
        lossy_bucket_receipt_sha256=integrity.lossy_bucket_receipt_sha256,
        receipt_sha256=canonical_sha256(unsigned_integrity),
    )
    reduction = reduce_verdict(manifest.mode, failed_integrity, None, thresholds=manifest.thresholds)
    unsigned = SWM0Result(
        mode=manifest.mode,
        manifest_sha256=manifest.manifest_sha256,
        integrity=failed_integrity,
        strongest_lossy_arm=None,
        dev_accuracy_by_lossy_arm=(),
        model_receipts=tuple(model_receipts),
        block_scores=tuple(block_scores),
        metrics=None,
        reduction=reduction,
        result_sha256="0" * 64,
    )
    return replace(unsigned, result_sha256=canonical_sha256(unsigned.unsigned()))


def run_manifest(
    manifest: SWM0Manifest,
    *,
    seed_preimages: Mapping[int, bytes] | None = None,
) -> SWM0Result:
    """Fit registered arms, freeze the dev winner, and score fresh blocks."""

    integrity = validate_manifest(manifest, seed_preimages=seed_preimages)
    if not integrity.passed:
        return _void_result(manifest, integrity)
    preimages = _resolve_manifest_preimages(manifest, seed_preimages)

    models: dict[int, dict[str, operator.BalancedRidgeReadout]] = {}
    dev_correct: dict[str, int] = {arm: 0 for arm in manifest.lossy_arms}
    dev_total = 0
    model_receipts: list[Mapping[str, Any]] = []
    parameter_counts: set[int] = set()
    for seed in manifest.seeds:
        train = _blocks_for(manifest, preimages, seed=seed, split="train")
        dev = _blocks_for(manifest, preimages, seed=seed, split="dev")
        train_cases = operator.cases_from_blocks(train)
        dev_cases = operator.cases_from_blocks(dev)
        seed_models: dict[str, operator.BalancedRidgeReadout] = {}
        for arm in manifest.arms:
            model = operator.fit_arm(train_cases, arm, ridge=manifest.ridge)
            if model.ridge != manifest.ridge:
                return _void_result(
                    manifest,
                    integrity,
                    model_receipts=model_receipts,
                    errors=("MODEL_RIDGE_DIFFERS_FROM_MANIFEST",),
                )
            seed_models[arm] = model
            parameter_counts.add(model.parameter_count)
            model_receipts.append(
                _model_receipt(seed, arm, model, train_cases[0].world)
            )
            if arm in manifest.lossy_arms:
                predictions = [model.predict(case.world) for case in dev_cases]
                dev_correct[arm] += _correct(predictions, dev_cases)
        models[seed] = seed_models
        dev_total += len(dev_cases)

    if len(parameter_counts) != 1:
        return _void_result(
            manifest,
            integrity,
            model_receipts=model_receipts,
            errors=("NOMINAL_DENSE_PARAMETER_PARITY_FAILED",),
        )
    dev_accuracy = {
        arm: dev_correct[arm] / dev_total for arm in manifest.lossy_arms
    }
    strongest_lossy = min(
        manifest.lossy_arms, key=lambda arm: (-dev_accuracy[arm], arm)
    )
    selection_receipt = canonical_sha256(
        {
            "dev_accuracy": dev_accuracy,
            "selected": strongest_lossy,
            "selection_rule": "highest pooled dev accuracy; lexical arm-id tie break",
        }
    )
    model_receipts.append(
        {
            "kind": "DEV_FROZEN_LOSSY_SELECTION",
            "receipt_sha256": selection_receipt,
            "selected_arm": strongest_lossy,
        }
    )

    rows: list[BlockScore] = []
    prediction_errors: list[str] = []
    for seed in manifest.seeds:
        fresh = _blocks_for(manifest, preimages, seed=seed, split="test")
        for block in fresh:
            row, errors = _score_fresh_block(seed, block, models[seed])
            rows.append(row)
            prediction_errors.extend(errors)
    if prediction_errors:
        return _void_result(
            manifest,
            integrity,
            model_receipts=model_receipts,
            block_scores=rows,
            errors=tuple(sorted(set(prediction_errors))),
        )

    metrics = summarize_metrics(
        rows,
        strongest_lossy_arm=strongest_lossy,
        q=manifest.q,
        thresholds=manifest.thresholds,
        bootstrap=manifest.bootstrap,
    )
    reduction = reduce_verdict(
        manifest.mode, integrity, metrics, thresholds=manifest.thresholds
    )
    unsigned = SWM0Result(
        mode=manifest.mode,
        manifest_sha256=manifest.manifest_sha256,
        integrity=integrity,
        strongest_lossy_arm=strongest_lossy,
        dev_accuracy_by_lossy_arm=tuple(sorted(dev_accuracy.items())),
        model_receipts=tuple(model_receipts),
        block_scores=tuple(rows),
        metrics=metrics,
        reduction=reduction,
        result_sha256="0" * 64,
    )
    return replace(unsigned, result_sha256=canonical_sha256(unsigned.unsigned()))


def replay_result(
    manifest: SWM0Manifest,
    expected: SWM0Result,
    *,
    seed_preimages: Mapping[int, bytes] | None = None,
) -> SWM0Result:
    """Re-run a result and fail unless every machine-readable byte is stable."""

    observed = run_manifest(manifest, seed_preimages=seed_preimages)
    if observed.to_json() != expected.to_json():
        raise SWM0ProtocolError("deterministic result replay mismatch")
    return observed


def _cli_payload(manifest: SWM0Manifest, result: SWM0Result) -> dict[str, Any]:
    unsigned = {
        "manifest": manifest.canonical(),
        "result": result.canonical(),
        "schema_version": "hswm-swm0r-cli-bundle/v1",
    }
    return {**unsigned, "bundle_sha256": canonical_sha256(unsigned)}


def main(argv: Sequence[str] | None = None) -> int:
    """Run a deliberately small CLI around the deterministic protocol."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=[mode.value for mode in RunMode])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prereg-path", type=Path)
    parser.add_argument("--prereg-sha256")
    parser.add_argument("--train-blocks", type=int)
    parser.add_argument("--dev-blocks", type=int)
    parser.add_argument("--fresh-blocks", type=int)
    parser.add_argument(
        "--bootstrap-resamples", type=int, default=DEFAULT_BOOTSTRAP_RESAMPLES
    )
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--ridge", type=float, default=DEFAULT_RIDGE)
    args = parser.parse_args(argv)

    mode = RunMode(args.mode)
    prereg_path: str | None = None
    prereg_sha: str | None = None
    prereg_commit: str | None = None
    if mode is RunMode.CONFIRMATORY:
        if args.prereg_path is None or args.prereg_sha256 is None:
            parser.error(
                "confirmatory mode requires --prereg-path and --prereg-sha256"
            )
        prereg_path = str(args.prereg_path)
        prereg_sha = args.prereg_sha256
    elif args.prereg_path is not None or args.prereg_sha256 is not None:
        if args.prereg_path is None or args.prereg_sha256 is None:
            parser.error("pilot prereg binding requires both path and SHA-256")
        try:
            prereg_path, _ = validate_preregistration_binding(
                args.prereg_path,
                args.prereg_sha256,
                require_committed=False,
            )
        except SWM0ProtocolError as exc:
            parser.error(str(exc))
        prereg_sha = args.prereg_sha256

    try:
        manifest = build_manifest(
            mode,
            train_blocks=args.train_blocks,
            dev_blocks=args.dev_blocks,
            fresh_blocks=args.fresh_blocks,
            bootstrap=BootstrapSpec(
                resamples=args.bootstrap_resamples,
                seed=args.bootstrap_seed,
            ),
            ridge=args.ridge,
            preregistration_path=prereg_path,
            preregistration_sha256=prereg_sha,
            preregistration_commit=prereg_commit,
        )
        result = run_manifest(manifest)
    except SWM0ProtocolError as exc:
        parser.error(str(exc))
    payload = canonical_json(_cli_payload(manifest, result)) + "\n"
    if args.output is None:
        sys.stdout.write(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


__all__ = [
    "ALL_ARMS",
    "BootstrapSpec",
    "BlockRef",
    "BlockScore",
    "CONFIRMATORY_FRESH_BLOCKS",
    "CONFIRMATORY_SEEDS",
    "ConfidenceInterval",
    "CONTROL_METADATA",
    "DEFAULT_BOOTSTRAP_RESAMPLES",
    "DEFAULT_BOOTSTRAP_SEED",
    "DEFAULT_DEV_BLOCKS",
    "DEFAULT_Q",
    "DEFAULT_RIDGE",
    "DEFAULT_TRAIN_BLOCKS",
    "Estimate",
    "IntegrityReceipt",
    "LIMITATIONS",
    "LOSSY_ARMS",
    "MANIFEST_SCHEMA",
    "MetricSummary",
    "PILOT_SEEDS",
    "PREREGISTRATION_SCHEMA",
    "PROTOCOL_VERSION",
    "RESULT_SCHEMA",
    "Reduction",
    "RunMode",
    "STAR_ARM",
    "SWM0Manifest",
    "SWM0ProtocolError",
    "SWM0Result",
    "TARGET_ARM",
    "Thresholds",
    "Verdict",
    "build_manifest",
    "canonical_json",
    "canonical_sha256",
    "fixed_seed_preimage",
    "frozen_preregistration_contract",
    "main",
    "paired_bootstrap_ci",
    "reduce_verdict",
    "replay_result",
    "require_uniform_lossy_buckets",
    "run_manifest",
    "SOURCE_PATHS",
    "summarize_metrics",
    "two_level_bootstrap_ci",
    "validate_manifest",
    "validate_preregistration_binding",
    "validate_preregistration_payload",
]


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI test
    raise SystemExit(main())
