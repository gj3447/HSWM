"""F1 metric v2 — selective utility (correct − c·wrong, abstain = 0).

The v1 development metric was binary coverage (correct = 1, everything else
= 0), which is blind to the difference between an abstention and a fabricated
answer.  Metric v2 scores every (item, arm) run as one of three outcomes:

    correct : answered (abstain is False) and the normalized answer is in the
              item's accepted-answer set
    wrong   : answered and not correct
    abstain : the arm declined to answer

Utility is ``U = 1·correct − c·wrong`` per item (abstain scores 0), exactly
the selective-utility the α gate regression (t2 → t3b) is measured with.
Contrasts are paired per development component (typed − control per
component, then macro-averaged across the 48 source-derived components),
mirroring the component partition discipline of the r8 power builder.

Everything is deterministic, stdlib-only, and exact (``fractions.Fraction``
arithmetic — utilities are rational over the 54-item cohort).  Identity drift
is never silently accepted: every loader / verifier raises
:class:`MetricV2Refusal`.

Identity checks mirrored from ``prom9_f1_r8_power.derive_development_components``:

* suite v4 self-hash (``suite_receipt_sha256``) recomputed over the suite bytes
* manifest hash equals ``suite.manifest_sha256``; run_id/mode agree across
  suite/manifest/gold
* every item runs exactly the five registered arms, no repeats
* gold accepted-answer identity set equals the manifest item identity set
* the selection's component schedule is an exact, source-derived partition of
  the cohort (component ids re-derived from source entity ids, cluster sizes
  and manifest candidate preimages verified)

``_normalize_answer`` is imported from the r8 power module so normalization
can never drift from the builder that froze the cohort.  The power module's
import chain pulls numeric dependencies (numpy via the prior-exposure stack);
in stdlib-only environments (the ooptdd probe host) the identical one-line
implementation below is used instead and ``NORMALIZE_SOURCE`` reports
``"vendored"``.  The test suite asserts both are available and agree on Dell,
so a vendored copy can never silently diverge from the power module.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256

try:  # prefer the power module's normalizer (single source of truth)
    from prom_search_hswm.prom9_f1_r8_power import (
        _normalize_answer as _power_normalize_answer,
    )
except Exception:  # ModuleNotFoundError: numpy chain absent (stdlib-only host)
    _power_normalize_answer = None


def _vendored_normalize_answer(value: str) -> str:
    return " ".join(value.casefold().strip().split())


if _power_normalize_answer is not None:
    _normalize_answer = _power_normalize_answer
    NORMALIZE_SOURCE = "power"
else:
    _normalize_answer = _vendored_normalize_answer
    NORMALIZE_SOURCE = "vendored"


SUITE_SCHEMA = "hswm-prom9-f1-suite/v4"
MANIFEST_SCHEMA = "hswm-prom9-f1-manifest/v3"
GOLD_SCHEMA = "hswm-prom9-f1-gold/v2"
SELECTION_SCHEMA = "hswm-prom9-f1-r8-cohort-selection/v4"
COMPONENT_SCHEMA = "hswm-source-entity-connected-component/v1"

CONTROL_ARMS = (FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
ALL_ARMS = (TYPED_ARM, *CONTROL_ARMS)
DEVELOPMENT_COMPONENTS = 48

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

OUTCOMES = ("correct", "wrong", "abstain")


class MetricV2Refusal(RuntimeError):
    """Raised on any identity drift; drift is never silently accepted."""


def _strict_object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MetricV2Refusal(f"{label} is not a JSON object")
    return value


def _read_json(path: Path | str, label: str) -> Mapping[str, object]:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise MetricV2Refusal(f"{label} unreadable: {error}") from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise MetricV2Refusal(f"{label} is not valid JSON: {error}") from error
    return _strict_object(value, label)


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or not _SHA256.fullmatch(declared):
        raise MetricV2Refusal(f"{label} self-hash field is absent or malformed")
    if canonical_sha256(unsigned) != declared:
        raise MetricV2Refusal(f"{label} self-hash drifted")
    return declared


def load_suite(path: Path | str) -> Mapping[str, object]:
    """Load a development suite v4 receipt, verifying its self-hash."""
    suite = _read_json(path, "development suite")
    if suite.get("schema_version") != SUITE_SCHEMA:
        raise MetricV2Refusal("development suite schema drifted")
    _self_hash(suite, "suite_receipt_sha256", "development suite")
    if suite.get("mode") != "development" or not isinstance(suite.get("run_id"), str):
        raise MetricV2Refusal("development suite run identity drifted")
    if not isinstance(suite.get("item_runs"), list):
        raise MetricV2Refusal("development suite item runs are absent")
    return suite


def load_manifest(path: Path | str) -> Mapping[str, object]:
    manifest = _read_json(path, "development manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise MetricV2Refusal("development manifest schema drifted")
    if manifest.get("mode") != "development" or not isinstance(manifest.get("run_id"), str):
        raise MetricV2Refusal("development manifest run identity drifted")
    if not isinstance(manifest.get("items"), list):
        raise MetricV2Refusal("development manifest items are absent")
    return manifest


def load_gold(path: Path | str) -> Mapping[str, object]:
    gold = _read_json(path, "development gold")
    if gold.get("schema_version") != GOLD_SCHEMA:
        raise MetricV2Refusal("development gold schema drifted")
    if not isinstance(gold.get("run_id"), str) or not isinstance(gold.get("items"), list):
        raise MetricV2Refusal("development gold run identity drifted")
    return gold


def load_selection(path: Path | str) -> Mapping[str, object]:
    selection = _read_json(path, "cohort selection")
    if selection.get("schema_version") != SELECTION_SCHEMA:
        raise MetricV2Refusal("cohort selection schema drifted")
    development = selection.get("development")
    if not isinstance(development, Mapping) or not isinstance(
        development.get("component_schedule"), list
    ):
        raise MetricV2Refusal("development component schedule is absent")
    return selection


@dataclass(frozen=True)
class DevelopmentEvidence:
    """A fully cross-verified development cohort plus its derived outcomes."""

    accepted: Mapping[str, frozenset]
    outcomes: Mapping[tuple[str, str], str]
    schedule: tuple[Mapping[str, object], ...]
    item_ids: frozenset
    suite_sha256: str
    gold_sha256: str
    manifest_sha256: str
    run_id: str

    @property
    def components(self) -> tuple[str, ...]:
        return tuple(str(row["component_id"]) for row in self.schedule)


def _verify_manifest_hash(suite: Mapping[str, object], manifest: Mapping[str, object]) -> str:
    digest = canonical_sha256(manifest)
    if suite.get("manifest_sha256") != digest:
        raise MetricV2Refusal("development manifest differs from terminal suite")
    return digest


def _index_manifest(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    indexed: dict[str, Mapping[str, object]] = {}
    for raw in manifest["items"]:
        row = _strict_object(raw, "development manifest item")
        item_id = str(row.get("item_id"))
        if not item_id or item_id in indexed:
            raise MetricV2Refusal("development manifest item IDs repeat")
        indexed[item_id] = row
    return indexed


def _index_runs(
    suite: Mapping[str, object], indexed_manifest: Mapping[str, Mapping[str, object]]
) -> dict[str, dict[str, Mapping[str, object]]]:
    indexed: dict[str, dict[str, Mapping[str, object]]] = {}
    for raw in suite["item_runs"]:
        run = _strict_object(raw, "development item run")
        item_id = str(run.get("item_id"))
        arm_id = str(run.get("arm_id"))
        if item_id not in indexed_manifest or arm_id not in ALL_ARMS:
            raise MetricV2Refusal("development item run identity drifted")
        arms = indexed.setdefault(item_id, {})
        if arm_id in arms:
            raise MetricV2Refusal("development item-arm run repeats")
        arms[arm_id] = run
    if set(indexed) != set(indexed_manifest) or any(
        set(arms) != set(ALL_ARMS) for arms in indexed.values()
    ):
        raise MetricV2Refusal("development suite does not exactly cover five arms")
    return indexed


def _accepted_answers(
    gold: Mapping[str, object], indexed_manifest: Mapping[str, Mapping[str, object]]
) -> dict[str, frozenset]:
    accepted: dict[str, frozenset] = {}
    for raw in gold["items"]:
        row = _strict_object(raw, "development gold row")
        item_id = str(row.get("item_id"))
        answers = row.get("accepted_answers")
        if (
            item_id in accepted
            or not isinstance(answers, list)
            or not answers
            or any(not isinstance(value, str) or not value for value in answers)
        ):
            raise MetricV2Refusal("development gold identity or answers drifted")
        accepted[item_id] = frozenset(_normalize_answer(value) for value in answers)
    if set(accepted) != set(indexed_manifest):
        raise MetricV2Refusal("development gold and manifest identities differ")
    return accepted


def _verify_schedule(
    selection: Mapping[str, object],
    indexed_manifest: Mapping[str, Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    development = selection["development"]
    schedule = development["component_schedule"]
    selected_item_ids = {str(value) for value in development.get("item_ids", [])}
    if set(indexed_manifest) != selected_item_ids:
        raise MetricV2Refusal("development manifest differs from frozen selection")

    components: list[Mapping[str, object]] = []
    seen_components: set[str] = set()
    seen_entities: set[str] = set()
    for raw in schedule:
        row = _strict_object(raw, "development component schedule")
        component_id = str(row.get("component_id"))
        item_ids = sorted(str(value) for value in row.get("item_ids", []))
        source_entities = sorted(str(value) for value in row.get("source_entity_ids", []))
        if (
            not _SHA256.fullmatch(component_id)
            or component_id in seen_components
            or not item_ids
            or not source_entities
            or len(set(item_ids)) != len(item_ids)
            or len(set(source_entities)) != len(source_entities)
            or not set(item_ids) <= set(indexed_manifest)
            or seen_entities & set(source_entities)
        ):
            raise MetricV2Refusal("development component identity or partition drifted")
        seen_components.add(component_id)
        seen_entities.update(source_entities)
        derived_entities = sorted(
            {
                str(candidate["source_entity_id"])
                for item_id in item_ids
                for candidate in indexed_manifest[item_id].get("candidates", [])
            }
        )
        if source_entities != derived_entities:
            raise MetricV2Refusal("development component source preimage drifted")
        derived_component = canonical_sha256(
            {"schema_version": COMPONENT_SCHEMA, "source_entity_ids": source_entities}
        )
        if component_id != derived_component or any(
            indexed_manifest[item_id].get("component_id") != component_id
            for item_id in item_ids
        ):
            raise MetricV2Refusal("development component was not source-derived")
        if row.get("cluster_size") != len(item_ids):
            raise MetricV2Refusal("development component cluster size drifted")
        components.append(row)
    if len(components) != DEVELOPMENT_COMPONENTS or set(
        item_id for row in components for item_id in row.get("item_ids", [])
    ) != set(indexed_manifest):
        raise MetricV2Refusal("development components do not exactly cover the pilot")
    return tuple(
        sorted(components, key=lambda value: str(value["component_id"]))
    )


def verify_development_identity(
    *,
    suite: Mapping[str, object],
    gold: Mapping[str, object],
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
) -> DevelopmentEvidence:
    """Full cross-artifact identity verification; any drift refuses."""
    if (
        manifest.get("run_id") != suite.get("run_id")
        or gold.get("run_id") != suite.get("run_id")
        or manifest.get("mode") != "development"
        or suite.get("mode") != "development"
    ):
        raise MetricV2Refusal("development run identity drifted")
    for value, label, field in (
        (suite, "development suite", SUITE_SCHEMA),
        (manifest, "development manifest", MANIFEST_SCHEMA),
        (gold, "development gold", GOLD_SCHEMA),
        (selection, "cohort selection", SELECTION_SCHEMA),
    ):
        _strict_object(value, label)
        if value.get("schema_version") != field:
            raise MetricV2Refusal(f"{label} schema drifted")
    suite_sha = _self_hash(suite, "suite_receipt_sha256", "development suite")
    manifest_sha = _verify_manifest_hash(suite, manifest)
    indexed_manifest = _index_manifest(manifest)
    indexed_runs = _index_runs(suite, indexed_manifest)
    accepted = _accepted_answers(gold, indexed_manifest)
    schedule = _verify_schedule(selection, indexed_manifest)

    outcomes: dict[tuple[str, str], str] = {}
    for item_id, arms in indexed_runs.items():
        for arm_id, run in arms.items():
            answer = run.get("answer")
            if not isinstance(answer, Mapping):
                raise MetricV2Refusal("development answer envelope is absent")
            if answer.get("abstain") is not False:
                outcome = "abstain"
            elif _normalize_answer(str(answer.get("answer", ""))) in accepted[item_id]:
                outcome = "correct"
            else:
                outcome = "wrong"
            outcomes[(item_id, arm_id)] = outcome
    return DevelopmentEvidence(
        accepted=accepted,
        outcomes=outcomes,
        schedule=schedule,
        item_ids=frozenset(indexed_manifest),
        suite_sha256=suite_sha,
        gold_sha256=canonical_sha256(gold),
        manifest_sha256=manifest_sha,
        run_id=str(suite["run_id"]),
    )


def load_development_evidence(
    *,
    suite_path: Path | str,
    gold_path: Path | str,
    manifest_path: Path | str,
    selection_path: Path | str,
) -> DevelopmentEvidence:
    """Load and cross-verify a development cohort from four artifact paths."""
    return verify_development_identity(
        suite=load_suite(suite_path),
        gold=load_gold(gold_path),
        manifest=load_manifest(manifest_path),
        selection=load_selection(selection_path),
    )


def _check_c(c: int) -> int:
    if not isinstance(c, int) or isinstance(c, bool) or c < 1:
        raise MetricV2Refusal("utility cost c must be a positive integer")
    return c


def _utility(outcome: str, c: int) -> Fraction:
    if outcome == "correct":
        return Fraction(1)
    if outcome == "wrong":
        return Fraction(-c)
    return Fraction(0)


def per_arm_utility(evidence: DevelopmentEvidence, c: int = 2) -> dict[str, Fraction]:
    """Mean selective utility per arm over the whole cohort (exact)."""
    _check_c(c)
    n = len(evidence.item_ids)
    return {
        arm: sum(
            (_utility(evidence.outcomes[(item_id, arm)], c) for item_id in evidence.item_ids),
            Fraction(0),
        )
        / n
        for arm in ALL_ARMS
    }


def per_component_contrasts(
    evidence: DevelopmentEvidence, c: int = 2
) -> dict[str, dict[str, Fraction]]:
    """Paired typed−control utility contrast inside each component."""
    _check_c(c)
    contrasts: dict[str, dict[str, Fraction]] = {}
    for row in evidence.schedule:
        item_ids = [str(value) for value in row["item_ids"]]
        contrasts[str(row["component_id"])] = {
            arm: sum(
                (
                    _utility(evidence.outcomes[(item_id, TYPED_ARM)], c)
                    - _utility(evidence.outcomes[(item_id, arm)], c)
                    for item_id in item_ids
                ),
                Fraction(0),
            )
            / len(item_ids)
            for arm in CONTROL_ARMS
        }
    return contrasts


def paired_contrasts(evidence: DevelopmentEvidence, c: int = 2) -> dict[str, Fraction]:
    """Component-macro paired contrasts: one mean per control arm."""
    per_component = per_component_contrasts(evidence, c)
    n = len(per_component)
    return {
        arm: sum((row[arm] for row in per_component.values()), Fraction(0)) / n
        for arm in CONTROL_ARMS
    }


def min_contrast(evidence: DevelopmentEvidence, c: int = 2) -> Fraction:
    return min(paired_contrasts(evidence, c).values())


def coverage_v1_contrasts(evidence: DevelopmentEvidence) -> dict[str, Fraction]:
    """The v1 binary-coverage metric on the same partition (ouroboros baseline).

    correct scores 1; wrong AND abstain both score 0 — the blindness v2 fixes.
    """
    score = {
        key: Fraction(1) if outcome == "correct" else Fraction(0)
        for key, outcome in evidence.outcomes.items()
    }
    contrasts: dict[str, list[Fraction]] = {arm: [] for arm in CONTROL_ARMS}
    for row in evidence.schedule:
        item_ids = [str(value) for value in row["item_ids"]]
        for arm in CONTROL_ARMS:
            contrasts[arm].append(
                sum(
                    (
                        score[(item_id, TYPED_ARM)] - score[(item_id, arm)]
                        for item_id in item_ids
                    ),
                    Fraction(0),
                )
                / len(item_ids)
            )
    n = len(evidence.schedule)
    return {
        arm: sum((value for value in values), Fraction(0)) / n
        for arm, values in contrasts.items()
    }


def c_sweep(
    evidence: DevelopmentEvidence, cs: tuple[int, ...] = (1, 2, 3)
) -> dict[int, dict[str, object]]:
    """Per-c utility + contrasts + minimum, for robustness claims."""
    if not cs or any(not isinstance(c, int) or isinstance(c, bool) or c < 1 for c in cs):
        raise MetricV2Refusal("c sweep requires positive integer costs")
    return {
        c: {
            "per_arm_utility": per_arm_utility(evidence, c),
            "paired_contrasts": paired_contrasts(evidence, c),
            "min_contrast": min_contrast(evidence, c),
        }
        for c in cs
    }
