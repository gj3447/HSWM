"""ooptdd-loop in_process target — conformance for the HSWM F1 metric v2 machinery.

NOT a mock.  ``run_metric_v2_probe`` loads the REAL frozen development suites
(t2 + t3b), gold, manifest and the v4 selection receipt from disk, verifies
every hash identity (suite self-hash, manifest↔suite binding, component
source-derivation), computes the selective-utility metric v2 with exact
Fraction arithmetic, and ships one trace event per genuinely-observed
behaviour.  A regressed metric (coverage-only scoring, silent identity
acceptance, drifted golden values) => the bound gates go RED.

Suites are located via ``HSWM_METRIC_V2_EVIDENCE_DIR`` (default:
``<repo>/.ooptdd-metric-v2-evidence``) with layout::

    <root>/development-a3-t2/{suite.v4.json,gold.v2.json,manifest.v3.json}
    <root>/development-a3-t3b/{suite.v4.json,gold.v2.json,manifest.v3.json}
    <root>/common/selection.v4.json

Every input file's sha256 is recorded in the probe summary for provenance.

Behaviours (one gate each in metric_v2_requirements.yaml):
    v2_typed_beats_all_controls_t2 : all 4 typed−control contrasts > 0 on t2 (c=2)
    v2_robust_across_c             : t2 min contrast > 0 for every c in {1,2,3}
    v2_alpha_gate_is_net_regression: t3b typed utility < t2 typed utility, yet
                                     still above every t3b control arm
    v2_abstain_only_scores_zero    : removal (schema-preserving null) arm utility
                                     is exactly 0 on both suites
    v2_fabrication_is_refused      : a byte-tampered suite copy (one typed answer
                                     flipped correct→wrong) is REFUSED by the
                                     loader's identity checks, and the honest
                                     suite out-scores the tampered implication
    v2_golden_replay               : computed utilities/contrasts match the frozen
                                     golden values within epsilon
    v2_ouroboros_self_measure      : the machinery measures ITSELF — v2's min
                                     contrast on t2 ranks above v1-coverage's,
                                     whose own min contrast on the same bytes is
                                     exactly 0 (the old metric was blind)

# KG: hswm-f1-metric-v2-ooptdd-ouroboros-20260804
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path

from prom_search_hswm import prom9_f1_metric_v2 as m2
from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)

_ADAPTER_DIR = Path(__file__).resolve().parent
_DEFAULT_EVIDENCE = _ADAPTER_DIR.parent / ".ooptdd-metric-v2-evidence"
_EVIDENCE_DIR = Path(
    os.environ.get("HSWM_METRIC_V2_EVIDENCE_DIR", str(_DEFAULT_EVIDENCE))
)

_C_SWEEP = (1, 2, 3)
_GOLDEN_EPS = 1e-3  # goldens are stated to 3 decimals; utility quantum is 1/54

# Frozen golden values (a3 successor measurement, 2026-08-03).  Per-arm
# selective utility at c=2, plus per-c minimum paired contrasts.
_GOLDEN_PER_ARM_T2 = {
    TYPED_ARM: 0.296,
    SHUFFLE_ARM: 0.148,
    VECTOR_ARM: 0.130,
    FLAT_ARM: 0.093,
    REMOVAL_ARM: 0.0,
}
_GOLDEN_PER_ARM_T3B = {TYPED_ARM: 0.185}
_GOLDEN_MIN_CONTRAST_T2 = {1: 0.083, 2: 0.167, 3: 0.229}
_GOLDEN_MIN_CONTRAST_T3B = {1: -0.031, 2: 0.083, 3: 0.083}

_SUITE_FILES = ("suite.v4.json", "gold.v2.json", "manifest.v3.json")


def _ev(cid: str, event: str, **attrs) -> dict:
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "hswm-f1-metric-v2",
        "event": event,
        **attrs,
    }


# One emitter symbol per requirement.  Longinus binds the exact behavior literal
# to the exact oracle that decides whether evidence is strong enough to ship it.
def _emit_v2_typed_beats_all_controls_t2(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-typed-beats-all-controls-t2-20260804
    if ok:
        backend.ship([_ev(cid, "v2_typed_beats_all_controls_t2", **attrs)])
    return ok


def _emit_v2_robust_across_c(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-robust-across-c-20260804
    if ok:
        backend.ship([_ev(cid, "v2_robust_across_c", **attrs)])
    return ok


def _emit_v2_alpha_gate_is_net_regression(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-alpha-gate-is-net-regression-20260804
    if ok:
        backend.ship([_ev(cid, "v2_alpha_gate_is_net_regression", **attrs)])
    return ok


def _emit_v2_abstain_only_scores_zero(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-abstain-only-scores-zero-20260804
    if ok:
        backend.ship([_ev(cid, "v2_abstain_only_scores_zero", **attrs)])
    return ok


def _emit_v2_fabrication_is_refused(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-fabrication-is-refused-20260804
    if ok:
        backend.ship([_ev(cid, "v2_fabrication_is_refused", **attrs)])
    return ok


def _emit_v2_golden_replay(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-golden-replay-20260804
    if ok:
        backend.ship([_ev(cid, "v2_golden_replay", **attrs)])
    return ok


def _emit_v2_ouroboros_self_measure(backend, cid: str, ok: bool, **attrs) -> bool:  # KG: hswm-f1-req-v2-ouroboros-self-measure-20260804
    if ok:
        backend.ship([_ev(cid, "v2_ouroboros_self_measure", **attrs)])
    return ok


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_suite_pair(root: Path, tag: str, selection_path: Path) -> m2.DevelopmentEvidence:
    base = root / f"development-a3-{tag}"
    return m2.load_development_evidence(
        suite_path=base / "suite.v4.json",
        gold_path=base / "gold.v2.json",
        manifest_path=base / "manifest.v3.json",
        selection_path=selection_path,
    )


def _provenance(root: Path) -> dict:
    proof: dict[str, str] = {}
    for tag in ("t2", "t3b"):
        for name in _SUITE_FILES:
            path = root / f"development-a3-{tag}" / name
            proof[f"development-a3-{tag}/{name}"] = _sha256_file(path)
    proof["common/selection.v4.json"] = _sha256_file(root / "common" / "selection.v4.json")
    return proof


def _float_map(values: dict[str, Fraction]) -> dict[str, float]:
    return {arm: round(float(value), 6) for arm, value in values.items()}


def _fabrication_probe(root: Path, honest_typed_utility: Fraction) -> dict:
    """Flip one typed correct answer to a wrong string inside a t2 suite COPY.

    The honest loader must REFUSE the tampered bytes (suite self-hash identity
    check), and the honest typed utility must exceed what the tampered bytes
    would have implied — fabrication is both detected and costly.
    """
    base = root / "development-a3-t2"
    suite = json.loads((base / "suite.v4.json").read_text(encoding="utf-8"))
    gold = json.loads((base / "gold.v2.json").read_text(encoding="utf-8"))
    accepted = {
        str(row["item_id"]): {m2._normalize_answer(v) for v in row["accepted_answers"]}
        for row in gold["items"]
    }
    flipped = None
    for run in suite["item_runs"]:
        if run.get("arm_id") != TYPED_ARM:
            continue
        answer = run.get("answer") or {}
        if (
            answer.get("abstain") is False
            and m2._normalize_answer(str(answer.get("answer", "")))
            in accepted[str(run["item_id"])]
        ):
            answer["answer"] = "ZZZ-FABRICATED-ANSWER-ooptdd-negative-oracle"
            flipped = str(run["item_id"])
            break
    if flipped is None:
        return {"ok": False, "reason": "no typed correct answer available to flip"}

    with tempfile.TemporaryDirectory(prefix="metric-v2-tampered-") as tmp:
        tampered_path = Path(tmp) / "suite.v4.json"
        tampered_path.write_text(json.dumps(suite), encoding="utf-8")
        try:
            m2.load_suite(tampered_path)
        except m2.MetricV2Refusal as error:
            refusal = str(error)
        else:
            refusal = None

        # What the tampered bytes WOULD have implied (raw parse, no verification):
        n_items = len(accepted)
        tampered_correct = 0
        tampered_wrong = 0
        for run in suite["item_runs"]:
            if run.get("arm_id") != TYPED_ARM:
                continue
            answer = run.get("answer") or {}
            if answer.get("abstain") is not False:
                continue
            if m2._normalize_answer(str(answer.get("answer", ""))) in accepted[
                str(run["item_id"])
            ]:
                tampered_correct += 1
            else:
                tampered_wrong += 1
        tampered_utility = Fraction(tampered_correct - 2 * tampered_wrong, n_items)

    ok = refusal is not None and honest_typed_utility > tampered_utility
    return {
        "ok": ok,
        "flipped_item_id": flipped,
        "refusal": refusal,
        "honest_typed_utility": str(honest_typed_utility),
        "tampered_implied_typed_utility": str(tampered_utility),
    }


def run_metric_v2_probe(backend, cid: str) -> dict:  # KG: hswm-f1-metric-v2-ooptdd-ouroboros-20260804
    """Loop entry point.  Computes metric v2 (and the v1 baseline) on the real
    t2/t3b development suites and ships one event per observed behaviour."""
    root = _EVIDENCE_DIR
    summary: dict = {
        "evidence_dir": str(root),
        "normalize_source": m2.NORMALIZE_SOURCE,
        "provenance_sha256": _provenance(root),
    }
    selection_path = root / "common" / "selection.v4.json"
    evidence = {
        tag: _load_suite_pair(root, tag, selection_path) for tag in ("t2", "t3b")
    }
    sweeps = {tag: m2.c_sweep(ev, _C_SWEEP) for tag, ev in evidence.items()}
    v1 = {tag: m2.coverage_v1_contrasts(ev) for tag, ev in evidence.items()}

    for tag in ("t2", "t3b"):
        summary[tag] = {
            "suite_sha256": evidence[tag].suite_sha256,
            "gold_sha256": evidence[tag].gold_sha256,
            "per_arm_utility_c2": _float_map(sweeps[tag][2]["per_arm_utility"]),
            "min_contrast_by_c": {
                c: round(float(sweeps[tag][c]["min_contrast"]), 6) for c in _C_SWEEP
            },
            "v1_coverage_min_contrast": round(float(min(v1[tag].values())), 6),
        }

    # REQ-V2-TYPED-BEATS-ALL-CONTROLS-T2
    t2_contrasts = sweeps["t2"][2]["paired_contrasts"]
    _emit_v2_typed_beats_all_controls_t2(
        backend,
        cid,
        all(value > 0 for value in t2_contrasts.values()),
        contrasts=_float_map(t2_contrasts),
    )

    # REQ-V2-ROBUST-ACROSS-C
    t2_mins = {c: sweeps["t2"][c]["min_contrast"] for c in _C_SWEEP}
    _emit_v2_robust_across_c(
        backend,
        cid,
        all(value > 0 for value in t2_mins.values()),
        min_contrast_by_c={c: round(float(v), 6) for c, v in t2_mins.items()},
    )

    # REQ-V2-ALPHA-GATE-IS-NET-REGRESSION
    t2_typed = sweeps["t2"][2]["per_arm_utility"][TYPED_ARM]
    t3b_utility = sweeps["t3b"][2]["per_arm_utility"]
    t3b_typed = t3b_utility[TYPED_ARM]
    t3b_max_control = max(t3b_utility[arm] for arm in m2.CONTROL_ARMS)
    _emit_v2_alpha_gate_is_net_regression(
        backend,
        cid,
        t3b_typed < t2_typed and t3b_typed > t3b_max_control,
        t2_typed_utility=round(float(t2_typed), 6),
        t3b_typed_utility=round(float(t3b_typed), 6),
        t3b_max_control_utility=round(float(t3b_max_control), 6),
    )

    # REQ-V2-ABSTAIN-ONLY-SCORES-ZERO
    removal = {
        tag: sweeps[tag][2]["per_arm_utility"][REMOVAL_ARM] for tag in ("t2", "t3b")
    }
    _emit_v2_abstain_only_scores_zero(
        backend,
        cid,
        all(value == 0 for value in removal.values()),
        removal_utility={tag: str(value) for tag, value in removal.items()},
    )

    # REQ-V2-FABRICATION-IS-REFUSED
    fabrication = _fabrication_probe(root, t2_typed)
    summary["fabrication"] = fabrication
    _emit_v2_fabrication_is_refused(
        backend,
        cid,
        bool(fabrication.get("ok")),
        flipped_item_id=fabrication.get("flipped_item_id"),
        refusal=fabrication.get("refusal"),
        honest_typed_utility=fabrication.get("honest_typed_utility"),
        tampered_implied_typed_utility=fabrication.get(
            "tampered_implied_typed_utility"
        ),
    )

    # REQ-V2-GOLDEN-REPLAY
    golden_failures: list[str] = []
    for arm, want in _GOLDEN_PER_ARM_T2.items():
        got = float(sweeps["t2"][2]["per_arm_utility"][arm])
        if abs(got - want) > _GOLDEN_EPS:
            golden_failures.append(f"t2/{arm}: got {got:.6f} want {want}")
    for arm, want in _GOLDEN_PER_ARM_T3B.items():
        got = float(sweeps["t3b"][2]["per_arm_utility"][arm])
        if abs(got - want) > _GOLDEN_EPS:
            golden_failures.append(f"t3b/{arm}: got {got:.6f} want {want}")
    for c, want in _GOLDEN_MIN_CONTRAST_T2.items():
        got = float(sweeps["t2"][c]["min_contrast"])
        if abs(got - want) > _GOLDEN_EPS:
            golden_failures.append(f"t2/min_contrast/c{c}: got {got:.6f} want {want}")
    for c, want in _GOLDEN_MIN_CONTRAST_T3B.items():
        got = float(sweeps["t3b"][c]["min_contrast"])
        if abs(got - want) > _GOLDEN_EPS:
            golden_failures.append(f"t3b/min_contrast/c{c}: got {got:.6f} want {want}")
    summary["golden_failures"] = golden_failures
    _emit_v2_golden_replay(
        backend,
        cid,
        not golden_failures,
        epsilon=_GOLDEN_EPS,
        checked=6 + 6,
    )

    # REQ-V2-OUROBOROS-SELF-MEASURE — the machinery scores its OWN history:
    # each suite is one "item", the metric versions are competing "arms", and
    # a metric's outcome on a suite is correct / abstain / wrong according to
    # whether its min paired contrast there is > 0 / == 0 / < 0.
    def _metric_outcome(min_contrast_value: Fraction) -> str:
        if min_contrast_value > 0:
            return "correct"
        if min_contrast_value < 0:
            return "wrong"
        return "abstain"

    self_outcomes: dict[tuple[str, str], str] = {}
    for tag in ("t2", "t3b"):
        self_outcomes[(tag, "v2_utility")] = _metric_outcome(
            sweeps[tag][2]["min_contrast"]
        )
        self_outcomes[(tag, "v1_coverage")] = _metric_outcome(min(v1[tag].values()))
    self_utility = {
        metric: sum(
            (
                Fraction(1)
                if self_outcomes[(tag, metric)] == "correct"
                else Fraction(-2)
                if self_outcomes[(tag, metric)] == "wrong"
                else Fraction(0)
                for tag in ("t2", "t3b")
            ),
            Fraction(0),
        )
        / 2
        for metric in ("v1_coverage", "v2_utility")
    }
    summary["ouroboros"] = {
        "self_outcomes": {f"{tag}/{metric}": outcome for (tag, metric), outcome in self_outcomes.items()},
        "self_utility": {metric: str(value) for metric, value in self_utility.items()},
    }
    _emit_v2_ouroboros_self_measure(
        backend,
        cid,
        self_utility["v2_utility"] > self_utility["v1_coverage"]
        and self_outcomes[("t2", "v1_coverage")] == "abstain"
        and self_outcomes[("t2", "v2_utility")] == "correct",
        t2_v1_min_contrast=str(min(v1["t2"].values())),
        t2_v2_min_contrast=str(sweeps["t2"][2]["min_contrast"]),
        v1_self_utility=str(self_utility["v1_coverage"]),
        v2_self_utility=str(self_utility["v2_utility"]),
    )

    return summary
