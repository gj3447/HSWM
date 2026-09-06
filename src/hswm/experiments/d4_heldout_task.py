"""Prospective D4 opaque binary-transform task contract; no occurrence runner."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256

TASK_SCHEMA = "hswm-d4-opaque-binary-transform-task-contract/v1"
INSTANCE_SCHEMA = "hswm-d4-opaque-binary-transform-instance/v1"
ACTION_SCHEMA = "hswm-d4-opaque-action/v1"
TRAJECTORY_SCHEMA = "hswm-d4-opaque-binary-transform-trajectory/v1"
OUTCOME_SCHEMA = "hswm-d4-opaque-binary-transform-outcome/v1"
CREDIT_SCHEMA = "hswm-d4-opaque-binary-transform-credit/v1"
DISPOSITION_SCHEMA = "hswm-d4-latent-bit-disposition/v1"
SHUFFLE_SCHEMA = "hswm-d4-opaque-binary-transform-shuffled-credit/v1"
TASK_FAMILY = "hswm-d4-opaque-binary-transform/v1"
OPAQUE_ID_BYTES = 16
OCCURRENCE_COUNT = 32
_SHA = re.compile(r"^[0-9a-f]{64}$")
_UID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class D4HeldoutTaskError(ValueError): pass


def _digest(value: Any) -> str: return canonical_sha256(value)
def _require_sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value): raise D4HeldoutTaskError(f"{name} must be SHA-256")
    return value
def _bit(value: object, name: str) -> int:
    if type(value) is not int or value not in (0, 1): raise D4HeldoutTaskError(f"{name} must be a bit")
    return value
def _uid(value: object, name: str) -> str:
    if not isinstance(value, str) or not _UID.fullmatch(value): raise D4HeldoutTaskError(f"{name} is invalid")
    return value


@dataclass(frozen=True)
class TaskContract:
    generator_source_sha256: str
    compiler_source_sha256: str
    def __post_init__(self) -> None:
        _require_sha(self.generator_source_sha256, "generator_source_sha256"); _require_sha(self.compiler_source_sha256, "compiler_source_sha256")
    def payload(self) -> dict[str, object]:
        return {"action_schema": ACTION_SCHEMA, "compiler_source_sha256": self.compiler_source_sha256,
                "generator_source_sha256": self.generator_source_sha256, "opaque_id_bytes": OPAQUE_ID_BYTES,
                "schema_version": TASK_SCHEMA, "selector_transform": "target_bit=selector_bit XOR latent_bit", "task_family": TASK_FAMILY}
    @property
    def sha256(self) -> str: return _digest(self.payload())


@dataclass(frozen=True)
class Instance:
    occurrence_uid: str; split: str; selector_bit: int; action_codes: tuple[str, str]; table_bits: tuple[int, int]
    def __post_init__(self) -> None:
        _uid(self.occurrence_uid, "occurrence_uid")
        if self.split not in {"TRAIN", "FINAL_HELDOUT"}: raise D4HeldoutTaskError("invalid split")
        _bit(self.selector_bit, "selector_bit")
        if len(self.action_codes) != 2 or len(set(self.action_codes)) != 2 or any(not re.fullmatch(r"[a-f0-9]{32}", x) for x in self.action_codes): raise D4HeldoutTaskError("opaque action IDs invalid")
        if type(self.table_bits) is not tuple or len(self.table_bits) != 2 or any(type(bit) is not int for bit in self.table_bits) or tuple(sorted(self.table_bits)) != (0, 1): raise D4HeldoutTaskError("table must be bijective")
    def payload(self, contract: TaskContract) -> dict[str, object]:
        return {"action_codes": list(self.action_codes), "occurrence_uid": self.occurrence_uid,
                "schema_version": INSTANCE_SCHEMA, "selector_bit": self.selector_bit, "split": self.split,
                "table_bits": list(self.table_bits), "task_contract_sha256": contract.sha256}
    def render(self, contract: TaskContract) -> bytes: return canonical_json_bytes(self.payload(contract))
    def decode(self, action_id: str) -> int:
        if action_id not in self.action_codes: raise D4HeldoutTaskError("action is not displayed")
        return self.table_bits[self.action_codes.index(action_id)]


def parse_action(raw: bytes, instance: Instance) -> str:
    if not isinstance(raw, bytes) or len(raw) > 256: raise D4HeldoutTaskError("action bytes invalid")
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len({key for key, _ in pairs}) != len(pairs): raise D4HeldoutTaskError("action has duplicate fields")
        return dict(pairs)
    try: value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates, parse_constant=lambda _: (_ for _ in ()).throw(D4HeldoutTaskError("nonfinite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error: raise D4HeldoutTaskError("action is not JSON") from error
    if not isinstance(value, dict) or set(value) != {"action_id"} or not isinstance(value["action_id"], str): raise D4HeldoutTaskError("action schema invalid")
    instance.decode(value["action_id"]); return value["action_id"]


def _opaque(seed: bytes, uid: str, split: str, index: int) -> str:
    return sha256(b"HSWM-D4-OPAQUE-ID/v1\0" + seed + uid.encode() + b"\0" + split.encode() + bytes([index])).hexdigest()[:32]

def make_instance(*, seed: bytes, occurrence_uid: str, split: str, selector_bit: int, candidate_order: int) -> Instance:
    if not isinstance(seed, bytes) or len(seed) != 32: raise D4HeldoutTaskError("seed must be 32 bytes")
    _bit(candidate_order, "candidate_order")
    codes = (_opaque(seed, occurrence_uid, split, 0), _opaque(seed, occurrence_uid, split, 1))
    return Instance(occurrence_uid, split, selector_bit, codes, (candidate_order, 1 - candidate_order))


def sealed_train(instance: Instance, contract: TaskContract, action_bytes: bytes) -> dict[str, object]:
    if instance.split != "TRAIN": raise D4HeldoutTaskError("only train can be sealed")
    action = parse_action(action_bytes, instance)
    value = {"action_id": action, "instance_sha256": _digest(instance.payload(contract)), "occurrence_uid": instance.occurrence_uid, "schema_version": TRAJECTORY_SCHEMA}
    return {**value, "trajectory_sha256": _digest(value)}

def _validate_seal(*, instance: Instance, contract: TaskContract, seal: Mapping[str, object]) -> str:
    required = {"action_id", "instance_sha256", "occurrence_uid", "schema_version", "trajectory_sha256"}
    if not isinstance(seal, Mapping) or set(seal) != required or seal.get("schema_version") != TRAJECTORY_SCHEMA or seal.get("occurrence_uid") != instance.occurrence_uid or seal.get("instance_sha256") != _digest(instance.payload(contract)) or seal.get("trajectory_sha256") != _digest({k: v for k, v in seal.items() if k != "trajectory_sha256"}): raise D4HeldoutTaskError("trajectory seal invalid")
    return instance.decode(seal.get("action_id") if isinstance(seal.get("action_id"), str) else "")

def _validate_outcome(*, instance: Instance, seal: Mapping[str, object], outcome: Mapping[str, object]) -> str:
    required = {"outcome", "occurrence_uid", "schema_version", "trajectory_sha256", "outcome_sha256"}
    if not isinstance(outcome, Mapping) or set(outcome) != required or outcome.get("schema_version") != OUTCOME_SCHEMA or outcome.get("occurrence_uid") != instance.occurrence_uid or outcome.get("trajectory_sha256") != seal.get("trajectory_sha256") or outcome.get("outcome") not in {"SUCCESS", "FAILURE"} or outcome.get("outcome_sha256") != _digest({k: v for k, v in outcome.items() if k != "outcome_sha256"}): raise D4HeldoutTaskError("independent outcome invalid")
    return str(outcome["outcome"])

def independently_evaluate(*, instance: Instance, contract: TaskContract, seal: Mapping[str, object], theta: int) -> dict[str, object]:
    if instance.split != "TRAIN": raise D4HeldoutTaskError("evaluator receives a train seal")
    _bit(theta, "theta")
    selected = _validate_seal(instance=instance, contract=contract, seal=seal); outcome = "SUCCESS" if selected == (instance.selector_bit ^ theta) else "FAILURE"
    value = {"outcome": outcome, "occurrence_uid": instance.occurrence_uid, "schema_version": OUTCOME_SCHEMA, "trajectory_sha256": seal["trajectory_sha256"]}
    return {**value, "outcome_sha256": _digest(value)}

def derive_credit(*, contract: TaskContract, instance: Instance, seal: Mapping[str, object], outcome: Mapping[str, object]) -> dict[str, object]:
    if instance.split != "TRAIN": raise D4HeldoutTaskError("credit requires train")
    selected = _validate_seal(instance=instance, contract=contract, seal=seal); observed = _validate_outcome(instance=instance, seal=seal, outcome=outcome); candidate = selected ^ (0 if observed == "SUCCESS" else 1) ^ instance.selector_bit
    value = {"candidate_theta": candidate, "origin_occurrence_uid": instance.occurrence_uid, "outcome_sha256": outcome["outcome_sha256"], "schema_version": CREDIT_SCHEMA, "selected_bit": selected, "selector_bit": instance.selector_bit, "task_contract_sha256": contract.sha256, "trajectory_sha256": seal["trajectory_sha256"]}
    return {**value, "credit_sha256": _digest(value)}

def make_disposition(*, contract: TaskContract, credit: Mapping[str, object]) -> dict[str, object]:
    required = {"candidate_theta", "origin_occurrence_uid", "outcome_sha256", "schema_version", "selected_bit", "selector_bit", "task_contract_sha256", "trajectory_sha256", "credit_sha256"}
    if set(credit) != required or credit.get("schema_version") != CREDIT_SCHEMA or credit.get("task_contract_sha256") != contract.sha256 or not all(_SHA.fullmatch(str(credit.get(key, ""))) for key in ("outcome_sha256", "trajectory_sha256", "credit_sha256")) or not isinstance(credit.get("origin_occurrence_uid"), str) or not _UID.fullmatch(credit["origin_occurrence_uid"]) or any(type(credit.get(key)) is not int or credit[key] not in (0, 1) for key in ("candidate_theta", "selected_bit", "selector_bit")) or credit.get("credit_sha256") != _digest({k: v for k, v in credit.items() if k != "credit_sha256"}): raise D4HeldoutTaskError("credit invalid")
    theta = _bit(credit["candidate_theta"], "candidate_theta")
    return {"compiler_source_sha256": contract.compiler_source_sha256, "credit_sha256": credit["credit_sha256"], "generator_source_sha256": contract.generator_source_sha256, "latent_bit": theta, "schema_version": DISPOSITION_SCHEMA, "task_contract_sha256": contract.sha256, "task_family": TASK_FAMILY, "transform": "XOR"}

def compile_recovered(*, contract: TaskContract, disposition: Mapping[str, object]) -> dict[str, object]:
    expected = {"compiler_source_sha256", "credit_sha256", "generator_source_sha256", "latent_bit", "schema_version", "task_contract_sha256", "task_family", "transform"}
    if set(disposition) != expected or disposition.get("schema_version") != DISPOSITION_SCHEMA or disposition.get("task_contract_sha256") != contract.sha256 or disposition.get("generator_source_sha256") != contract.generator_source_sha256 or disposition.get("compiler_source_sha256") != contract.compiler_source_sha256 or disposition.get("task_family") != TASK_FAMILY or disposition.get("transform") != "XOR" or not _SHA.fullmatch(str(disposition.get("credit_sha256", ""))): raise D4HeldoutTaskError("recovered disposition invalid")
    return {"compiler_source_sha256": contract.compiler_source_sha256, "latent_bit": _bit(disposition.get("latent_bit"), "latent_bit"), "task_contract_sha256": contract.sha256}

def make_schedule(seed: bytes) -> tuple[dict[str, object], ...]:
    """Prospective deterministic schedule; fixture seeds are not scientific draws."""
    if not isinstance(seed, bytes) or len(seed) != 32: raise D4HeldoutTaskError("seed must be 32 bytes")
    rows = []
    for theta in (0, 1):
        for selector in (0, 1):
            for order in (0, 1):
                for sham in (0, 1):
                    for replicate in (0, 1):
                        uid = "d4-" + sha256(b"HSWM-D4-SCHEDULE/v1\0" + seed + bytes([theta, selector, order, sham, replicate])).hexdigest()[:24]
                        rows.append({"candidate_order": order, "occurrence_uid": uid, "selector_bit": selector, "sham_theta": sham, "theta": theta})
    return tuple(sorted(rows, key=lambda row: sha256(b"HSWM-D4-SCHEDULE-RANK/v1\0" + seed + str(row["occurrence_uid"]).encode()).digest()))

def opposite_theta_derangement(schedule: tuple[Mapping[str, object], ...]) -> dict[str, str]:
    if len(schedule) != OCCURRENCE_COUNT: raise D4HeldoutTaskError("schedule must have 32 rows")
    zero = [str(r["occurrence_uid"]) for r in schedule if r.get("theta") == 0]; one = [str(r["occurrence_uid"]) for r in schedule if r.get("theta") == 1]
    if len(zero) != 16 or len(one) != 16 or len(set(zero + one)) != 32: raise D4HeldoutTaskError("schedule strata invalid")
    return {**dict(zip(zero, one, strict=True)), **dict(zip(one, zero, strict=True))}

def shuffled_credit_control(*, contract: TaskContract, credit: Mapping[str, object], receiving_occurrence_uid: str) -> dict[str, object]:
    _uid(receiving_occurrence_uid, "receiving_occurrence_uid")
    make_disposition(contract=contract, credit=credit)
    if credit["origin_occurrence_uid"] == receiving_occurrence_uid: raise D4HeldoutTaskError("shuffled origin invalid")
    return {"control": "SHUFFLED_CREDIT_OPPOSITE_THETA", "credit_sha256": credit.get("credit_sha256"), "origin_occurrence_uid": credit["origin_occurrence_uid"], "receiving_occurrence_uid": receiving_occurrence_uid, "schema_version": SHUFFLE_SCHEMA}
