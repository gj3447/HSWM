"""Provider-free DNRD-5 v2 one-block integration instrument.

The actual-byte fixture has no separate mutable fork-state store. This
instrument thus reports typed projection equality, not simulated state
equality: delayed behavior sources W0, and restored behavior sources a restore
transaction which itself targets W0. It dispatches no provider and creates no
occurrence identifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from _research.dnrd5.actual_byte_corpus_contract import ARMS, atom_key_id
from _research.dnrd5.canonical_json import parse_canonical
from _research.dnrd5.independent_actual_byte_judge import judge_actual_byte_corpus


TERMINAL = "INTEGRATION_INSTRUMENT_NOT_OCCURRENCE"
INSTRUMENT_VERSION = "hswm-dnrd5-one-block-provider-free-integration/v2"
_EFFECT_ARMS = ("ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "EXACT_W0_ROLLBACK")


class IntegrationInstrumentRefusal(ValueError):
    """The checked-in fixture cannot support this bounded integration check."""


@dataclass(frozen=True)
class ForkBinding:
    arm: str
    fork_atom_key_id: str
    w0_atom_key_id: str


@dataclass(frozen=True)
class BranchEffect:
    arm: str
    decision: str
    effect_role: str
    decision_atom_key_id: str
    fork_atom_key_id: str
    effect_atom_key_id: str
    behavior_projection_atom_key_id: str | None
    behavior_source_atom_key_id: str | None
    read_set: tuple[str, ...]
    source_transition_id: str


@dataclass(frozen=True)
class OneBlockIntegrationResult:
    terminal: str
    instrument_version: str
    fixture_root_sha256: str
    w0_atom_key_id: str
    forks: tuple[ForkBinding, ...]
    branch_effects: tuple[BranchEffect, ...]
    delayed_behavior_source_equals_w0: bool
    restored_behavior_sources_restore_targeting_w0: bool
    provider_calls: int
    occurrence_ids: tuple[str, ...]


def _blob(root: Path, descriptor: Mapping[str, Any]) -> bytes:
    return (root / "blobs" / descriptor["sha256"]).read_bytes()


def _target(envelope: Mapping[str, Any], role: str) -> str:
    rows = [atom_key_id(row["target"]) for row in envelope["references"] if row["role"] == f"role:dnrd5:v2:{role}"]
    if len(rows) != 1:
        raise IntegrationInstrumentRefusal(f"typed reference must have one {role} target")
    return rows[0]


def _fixture_atoms(root: Path, manifest: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    atoms: dict[str, dict[str, Any]] = {}
    envelopes: dict[str, dict[str, Any]] = {}
    for row in manifest["core"]["atoms"]:
        key = atom_key_id(row["key"])
        if key in atoms:
            raise IntegrationInstrumentRefusal("fixture atom keys are not unique")
        atoms[key] = row
        envelopes[key] = parse_canonical(_blob(root, row["envelope"]))
    return atoms, envelopes


def _journal_effects(root: Path, manifest: Mapping[str, Any], atoms: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    known: set[str] = set()
    effects: list[dict[str, Any]] = []
    for listing in manifest["core"]["journal"][1:]:
        record = parse_canonical(_blob(root, listing["record"]))
        write_ids = tuple(atom_key_id(row["key"]) for row in record["writeBindings"])
        read_ids = tuple(atom_key_id(key) for key in record["receipt"]["readSet"])
        if read_ids != tuple(sorted(set(read_ids))) or not set(read_ids).issubset(known):
            raise IntegrationInstrumentRefusal("journal read-set is not exact prior-state evidence")
        kinds = {atoms[key]["kind"] for key in write_ids}
        if kinds in ({"capability_consumption", "macro_disposition"}, {"capability_consumption", "restore_transaction"}):
            effect_key = next(key for key in write_ids if atoms[key]["kind"] in {"macro_disposition", "restore_transaction"})
            effects.append({"effect_key": effect_key, "kinds": kinds, "read_set": read_ids, "transition_id": record["receipt"]["transitionId"]})
        known.update(write_ids)
    expected = [{"capability_consumption", "macro_disposition"}] * 3 + [{"capability_consumption", "restore_transaction"}]
    if len(effects) != 4 or [row["kinds"] for row in effects] != expected:
        raise IntegrationInstrumentRefusal("fixture must contain exact three-admit/one-restore schedule")
    return tuple(effects)


def run_one_block_integration(repository_root: Path) -> OneBlockIntegrationResult:
    """Reconstruct actual W0/fork/effect/projection links without provider work."""
    root = repository_root / "_research/dnrd5/vectors/actual_byte_corpus_v1"
    judgment = judge_actual_byte_corpus(root)
    manifest = parse_canonical((root / "manifest.json").read_bytes())
    atoms, envelopes = _fixture_atoms(root, manifest)
    w0_rows = [key for key, atom in atoms.items() if atom["kind"] == "w0_snapshot"]
    if len(w0_rows) != 1:
        raise IntegrationInstrumentRefusal("fixture must contain exactly one actual W0 atom")
    w0 = w0_rows[0]

    bindings = []
    for key, atom in atoms.items():
        if atom["kind"] == "fork_incidence":
            payload = parse_canonical(_blob(root, atom["payload"]))
            bindings.append(ForkBinding(payload["arm"], key, _target(envelopes[key], "w0")))
    bindings.sort(key=lambda row: ARMS.index(row.arm) if row.arm in ARMS else len(ARMS))
    if tuple(row.arm for row in bindings) != ARMS or any(row.w0_atom_key_id != w0 for row in bindings):
        raise IntegrationInstrumentRefusal("four actual fork incidences do not bind one actual W0")
    fork_by_arm = {row.arm: row for row in bindings}

    effects = _journal_effects(root, manifest, atoms)
    behaviors: dict[str, tuple[str, str]] = {}
    for key, atom in atoms.items():
        if atom["kind"] == "behavior_projection":
            arm = parse_canonical(_blob(root, atom["payload"]))["arm"]
            behaviors[arm] = (key, _target(envelopes[key], "source"))
    if set(behaviors) != set(ARMS):
        raise IntegrationInstrumentRefusal("four actual behavior projections are required")

    rows: list[BranchEffect] = []
    for arm, effect in zip(_EFFECT_ARMS[:2], effects[:2], strict=True):
        macro = effect["effect_key"]
        decision = _target(envelopes[macro], "revision-admission-decision")
        behavior_key, behavior_source = behaviors[arm]
        if _target(envelopes[decision], "fork") != fork_by_arm[arm].fork_atom_key_id or behavior_source != macro:
            raise IntegrationInstrumentRefusal("admit topology is not bound to its actual fork and macro")
        rows.append(BranchEffect(arm, "ADMIT", "OBSERVABLE_SUCCESSOR", decision, fork_by_arm[arm].fork_atom_key_id, macro, behavior_key, behavior_source, effect["read_set"], effect["transition_id"]))

    # EXACT_W0_ROLLBACK first stages one admitted successor, but the fixture
    # intentionally exposes no behavior projection from that transient state.
    # Its only post-branch behavior projection is sealed after the restore and
    # sources the restore transaction.  Keep those two transitions distinct so
    # this bounded instrument cannot misreport staging as observable behavior.
    staged = effects[2]
    staged_macro = staged["effect_key"]
    staged_decision = _target(
        envelopes[staged_macro], "revision-admission-decision"
    )
    if (
        _target(envelopes[staged_decision], "fork")
        != fork_by_arm["EXACT_W0_ROLLBACK"].fork_atom_key_id
    ):
        raise IntegrationInstrumentRefusal(
            "rollback staging admission is not bound to its actual fork"
        )
    rows.append(
        BranchEffect(
            "EXACT_W0_ROLLBACK",
            "ADMIT",
            "STAGED_FOR_ROLLBACK_NOT_BEHAVIOR_PROJECTED",
            staged_decision,
            fork_by_arm["EXACT_W0_ROLLBACK"].fork_atom_key_id,
            staged_macro,
            None,
            None,
            staged["read_set"],
            staged["transition_id"],
        )
    )

    restore = effects[3]
    restore_key = restore["effect_key"]
    rollback = _target(envelopes[restore_key], "decision")
    exact_behavior_key, exact_behavior_source = behaviors["EXACT_W0_ROLLBACK"]
    if (_target(envelopes[rollback], "fork") != fork_by_arm["EXACT_W0_ROLLBACK"].fork_atom_key_id
            or _target(envelopes[restore_key], "w0") != w0 or exact_behavior_source != restore_key):
        raise IntegrationInstrumentRefusal("restore topology is not bound to exact fork, W0, and behavior")
    restore_required_reads = {
        w0,
        staged_macro,
        rollback,
    }
    if not restore_required_reads.issubset(set(restore["read_set"])):
        raise IntegrationInstrumentRefusal(
            "restore read-set omits W0, staged successor, or rollback decision"
        )
    rows.append(BranchEffect("EXACT_W0_ROLLBACK", "RESTORE_EXACT_W0", "RESTORED_SUCCESSOR_BEHAVIOR_PROJECTED", rollback, fork_by_arm["EXACT_W0_ROLLBACK"].fork_atom_key_id, restore_key, exact_behavior_key, exact_behavior_source, restore["read_set"], restore["transition_id"]))

    delayed_key, delayed_source = behaviors["DELAYED_NO_CREDIT"]
    result = OneBlockIntegrationResult(TERMINAL, INSTRUMENT_VERSION, judgment.root_sha256, w0, tuple(bindings), tuple(rows), delayed_source == w0, exact_behavior_source == restore_key and _target(envelopes[restore_key], "w0") == w0, 0, ())
    validate_one_block_integration(result)
    return result


def validate_one_block_integration(result: OneBlockIntegrationResult) -> None:
    """Fail closed on projection, journal, or occurrence-boundary drift."""
    if result.terminal != TERMINAL or result.instrument_version != INSTRUMENT_VERSION:
        raise IntegrationInstrumentRefusal("integration terminal/version drift")
    if (
        type(result.fixture_root_sha256) is not str
        or len(result.fixture_root_sha256) != 64
        or result.fixture_root_sha256 == "0" * 64
        or any(character not in "0123456789abcdef" for character in result.fixture_root_sha256)
    ):
        raise IntegrationInstrumentRefusal("fixture root SHA-256 drift")
    if result.provider_calls != 0 or result.occurrence_ids:
        raise IntegrationInstrumentRefusal("provider-free instrument cannot claim an occurrence")
    if tuple(row.arm for row in result.forks) != ARMS or len({row.fork_atom_key_id for row in result.forks}) != 4:
        raise IntegrationInstrumentRefusal("fork closure drift")
    if any(row.w0_atom_key_id != result.w0_atom_key_id for row in result.forks):
        raise IntegrationInstrumentRefusal("forks do not share actual W0")
    if len(result.branch_effects) != 4 or [row.decision for row in result.branch_effects] != ["ADMIT", "ADMIT", "ADMIT", "RESTORE_EXACT_W0"]:
        raise IntegrationInstrumentRefusal("effect schedule drift")
    if [row.arm for row in result.branch_effects] != [
        "ACTIVE",
        "OUTCOME_INDEPENDENT_SHAM",
        "EXACT_W0_ROLLBACK",
        "EXACT_W0_ROLLBACK",
    ]:
        raise IntegrationInstrumentRefusal("effect arm chronology drift")
    if [row.effect_role for row in result.branch_effects] != [
        "OBSERVABLE_SUCCESSOR",
        "OBSERVABLE_SUCCESSOR",
        "STAGED_FOR_ROLLBACK_NOT_BEHAVIOR_PROJECTED",
        "RESTORED_SUCCESSOR_BEHAVIOR_PROJECTED",
    ]:
        raise IntegrationInstrumentRefusal("effect role chronology drift")
    if (
        result.branch_effects[2].behavior_projection_atom_key_id is not None
        or result.branch_effects[2].behavior_source_atom_key_id is not None
    ):
        raise IntegrationInstrumentRefusal(
            "rollback staging cannot claim a fixture behavior projection"
        )
    observable = (*result.branch_effects[:2], result.branch_effects[-1])
    if any(
        row.behavior_projection_atom_key_id is None
        or row.behavior_source_atom_key_id != row.effect_atom_key_id
        for row in observable
    ):
        raise IntegrationInstrumentRefusal("observable behavior/effect source binding drift")
    if len({row.behavior_projection_atom_key_id for row in observable}) != 3:
        raise IntegrationInstrumentRefusal("observable behavior projection identities repeat")
    if any(row.read_set != tuple(sorted(set(row.read_set))) for row in result.branch_effects):
        raise IntegrationInstrumentRefusal("effect read-set is not exact")
    fork_by_arm = {row.arm: row.fork_atom_key_id for row in result.forks}
    if any(
        row.fork_atom_key_id != fork_by_arm.get(row.arm)
        for row in result.branch_effects
    ):
        raise IntegrationInstrumentRefusal("effect/fork binding drift")
    if any(
        row.decision_atom_key_id not in row.read_set
        for row in result.branch_effects
    ):
        raise IntegrationInstrumentRefusal("effect decision is absent from read-set")
    if len({row.effect_atom_key_id for row in result.branch_effects}) != 4:
        raise IntegrationInstrumentRefusal("effect identities are not unique")
    if len({row.source_transition_id for row in result.branch_effects}) != 4:
        raise IntegrationInstrumentRefusal("effect transition identities are not unique")
    restore = result.branch_effects[-1]
    staged = result.branch_effects[2]
    if not {
        result.w0_atom_key_id,
        staged.effect_atom_key_id,
        restore.decision_atom_key_id,
    }.issubset(set(restore.read_set)):
        raise IntegrationInstrumentRefusal(
            "restore result omits W0 or staged successor from its read-set"
        )
    if not result.delayed_behavior_source_equals_w0 or not result.restored_behavior_sources_restore_targeting_w0:
        raise IntegrationInstrumentRefusal("actual behavior projection is not exact W0/restore topology")
