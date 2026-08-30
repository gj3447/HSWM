"""Deterministically commit a prospective, local-only ALFWorld B0 sample.

This module only selects opaque local assets.  It neither starts an ALFWorld
episode nor makes a G0/G1/effectiveness claim.  In particular, ``valid_unseen``
records are counted from their ``split`` token while their identifiers and
paths are never decoded or retained here.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator, Mapping

from _research.dnrd5.canonical_json import canonical_bytes


POOL_SCHEMA = "hswm-alfworld-text-clean-pool/v2"
LOCATOR_SCHEMA = "hswm-alfworld-text-clean-pool-local-locator/v1"
SELECTION_SCHEMA = "hswm-alfworld-b0-selection/v1"
GROUP_DOMAIN = "HSWM_ALFWORLD_B0_GROUP/v1"
GAME_DOMAIN = "HSWM_ALFWORLD_B0_GAME/v1"
TRAIN_GROUP_COUNT = 8
VALID_SEEN_GROUP_COUNT = 4
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SPLIT_RE = re.compile(rb'"split"\s*:\s*"([a-z_]+)"')


class AlfworldB0SelectionError(RuntimeError):
    """The public pool or local-only selection commitment was invalid."""


@dataclass(frozen=True, slots=True)
class OpaqueGameSelection:
    """Private local selection material; never include this object in public output."""

    split: str
    task_group_uid: str
    opaque_uid: str


@dataclass(frozen=True, slots=True)
class B0Selection:
    """A prospective B0 sample plus the commitments needed to reproduce it."""

    protocol_uid: str
    protocol_version: str
    protocol_sha256: str
    selector_source_sha256: str
    pool_manifest_sha256: str
    local_locator_sha256: str
    train: tuple[OpaqueGameSelection, ...]
    valid_seen: tuple[OpaqueGameSelection, ...]
    selection_digest: str

    def public_projection(self) -> dict[str, object]:
        """Return an aggregate-only commitment with no game or task identifiers."""
        value: dict[str, object] = {
            "schema_version": SELECTION_SCHEMA,
            "record_role": "AGGREGATE_PROSPECTIVE_B0_SELECTION_COMMITMENT_NOT_A_RESULT",
            "status": "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN",
            "protocol": {
                "uid": self.protocol_uid,
                "version": self.protocol_version,
                "protocol_file_sha256": self.protocol_sha256,
            },
            "selector_source_sha256": self.selector_source_sha256,
            "input_commitments": {
                "pool_manifest_rendered_json_sha256": self.pool_manifest_sha256,
                "local_locator_rendered_json_sha256": self.local_locator_sha256,
            },
            "selection": {
                "algorithm": SELECTION_SCHEMA,
                "group_rank_domain": GROUP_DOMAIN,
                "game_rank_domain": GAME_DOMAIN,
                "without_replacement": True,
                "selected_group_counts": {"train": len(self.train), "valid_seen": len(self.valid_seen)},
                "valid_unseen_selected_group_count": 0,
                "valid_unseen_record_detail_access": "NONE_BEYOND_AGGREGATE_AND_SPLIT_COUNT",
                "selection_digest_sha256": self.selection_digest,
            },
            "no_claim": [
                "This is a deterministic prospective asset-selection commitment only.",
                "It contains no individual game UID, task-group UID, path, task name, trajectory, game content, action, outcome, model call, or result.",
                "It does not execute ALFWorld and is not a G0 pass, G1 result, comparator result, or HSWM efficacy claim.",
            ],
        }
        unsigned = canonical_bytes(value)
        value["public_projection_sha256"] = sha256(unsigned).hexdigest()
        return value

    def private_receipt(self) -> dict[str, object]:
        """Return local-only identifiers for a receipt stored outside the repository."""
        value: dict[str, object] = {
            "schema_version": "hswm-alfworld-b0-selection-private-receipt/v1",
            "record_role": "LOCAL_NONREPOSITORY_OPAQUE_B0_SELECTION_RECEIPT_NOT_FOR_REDISTRIBUTION",
            "status": "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN",
            "protocol": {
                "uid": self.protocol_uid,
                "version": self.protocol_version,
                "protocol_file_sha256": self.protocol_sha256,
            },
            "selector_source_sha256": self.selector_source_sha256,
            "input_commitments": {
                "pool_manifest_rendered_json_sha256": self.pool_manifest_sha256,
                "local_locator_rendered_json_sha256": self.local_locator_sha256,
            },
            "selection_digest_sha256": self.selection_digest,
            "selected": {
                "train": [_private_row(row) for row in self.train],
                "valid_seen": [_private_row(row) for row in self.valid_seen],
            },
            "valid_unseen_selected_group_count": 0,
            "no_claim": "Local selection receipt only; no experiment was run.",
        }
        value["private_receipt_sha256"] = sha256(canonical_bytes(value)).hexdigest()
        return value


def _private_row(row: OpaqueGameSelection) -> dict[str, str]:
    return {"split": row.split, "task_group_uid": row.task_group_uid, "opaque_uid": row.opaque_uid}


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise AlfworldB0SelectionError(f"{label} must be a lowercase SHA-256")
    return value


def _read_object(path: Path, label: str) -> tuple[bytes, Mapping[str, object]]:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise AlfworldB0SelectionError(f"{label} must be an absolute regular non-symlink file")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldB0SelectionError(f"{label} is unreadable JSON") from error
    if not isinstance(value, dict):
        raise AlfworldB0SelectionError(f"{label} must be a JSON object")
    return raw, value


def _read_regular_bytes(path: Path, label: str) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise AlfworldB0SelectionError(f"{label} must be an absolute regular non-symlink file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise AlfworldB0SelectionError(f"{label} is unreadable") from error


def _locator_schema(raw: bytes) -> str:
    """Read only the schema token; record bodies stay opaque until needed."""
    match = re.search(rb'"schema_version"\s*:\s*"([^"]+)"', raw)
    if match is None:
        raise AlfworldB0SelectionError("local locator schema is absent")
    try:
        return match.group(1).decode("ascii")
    except UnicodeDecodeError as error:
        raise AlfworldB0SelectionError("local locator schema is invalid") from error


def _records_array_start(raw: bytes) -> int:
    marker = b'"records"'
    start = raw.find(marker)
    if start < 0:
        raise AlfworldB0SelectionError("local locator records are absent")
    bracket = raw.find(b"[", start + len(marker))
    if bracket < 0:
        raise AlfworldB0SelectionError("local locator records are malformed")
    return bracket + 1


def _iter_record_slices(raw: bytes) -> Iterator[bytes]:
    """Yield each records-array object without decoding unrelated record fields."""
    index, length = _records_array_start(raw), len(raw)
    while True:
        while index < length and raw[index] in b" \t\r\n,":
            index += 1
        if index >= length or raw[index] == ord("]"):
            return
        if raw[index] != ord("{"):
            raise AlfworldB0SelectionError("local locator record must be an object")
        start, depth, quoted, escaped = index, 0, False, False
        while index < length:
            char = raw[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == ord("\\"):
                    escaped = True
                elif char == ord('"'):
                    quoted = False
            elif char == ord('"'):
                quoted = True
            elif char == ord("{"):
                depth += 1
            elif char == ord("}"):
                depth -= 1
                if depth == 0:
                    yield raw[start:index + 1]
                    index += 1
                    break
            index += 1
        else:
            raise AlfworldB0SelectionError("unterminated local locator record")


def _split_only(record_slice: bytes) -> str:
    match = _SPLIT_RE.search(record_slice)
    if match is None:
        raise AlfworldB0SelectionError("local locator record split is absent")
    try:
        return match.group(1).decode("ascii")
    except UnicodeDecodeError as error:
        raise AlfworldB0SelectionError("local locator record split is invalid") from error


def _decode_selectable_record(record_slice: bytes, split: str) -> OpaqueGameSelection:
    try:
        record = json.loads(record_slice)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldB0SelectionError("selected local locator record is invalid JSON") from error
    expected = {"bytes", "file_sha256", "opaque_uid", "relative_path", "relative_path_sha256", "split", "task_group_uid"}
    if not isinstance(record, dict) or set(record) != expected or record.get("split") != split:
        raise AlfworldB0SelectionError("selected local locator record contract drifted")
    group, opaque = record.get("task_group_uid"), record.get("opaque_uid")
    if not isinstance(group, str) or not group or not isinstance(opaque, str) or not opaque:
        raise AlfworldB0SelectionError("selected local locator opaque identifier is invalid")
    return OpaqueGameSelection(split=split, task_group_uid=group, opaque_uid=opaque)


def _rank(*, domain: str, pool_sha: str, locator_sha: str, protocol_uid: str,
          protocol_version: str, protocol_sha: str, split: str, group_uid: str,
          opaque_uid: str = "") -> str:
    fields = (
        domain, pool_sha, locator_sha, protocol_uid, protocol_version,
        protocol_sha, split, group_uid, opaque_uid,
    )
    return _digest(b"\0".join(field.encode("utf-8") for field in fields))


def _choose_one_per_group(records: tuple[OpaqueGameSelection, ...], *, count: int,
                          pool_sha: str, locator_sha: str, protocol_uid: str,
                          protocol_version: str, protocol_sha: str,
                          split: str) -> tuple[OpaqueGameSelection, ...]:
    groups: dict[str, list[OpaqueGameSelection]] = {}
    for row in records:
        groups.setdefault(row.task_group_uid, []).append(row)
    if len(groups) < count:
        raise AlfworldB0SelectionError(f"{split} has only {len(groups)} task groups; need {count}")
    ranked_groups = sorted(groups, key=lambda group: (_rank(
        domain=GROUP_DOMAIN, pool_sha=pool_sha, locator_sha=locator_sha,
        protocol_uid=protocol_uid, protocol_version=protocol_version, split=split,
        protocol_sha=protocol_sha, group_uid=group), group))
    selected: list[OpaqueGameSelection] = []
    for group in ranked_groups[:count]:
        candidates = groups[group]
        selected.append(min(candidates, key=lambda row: (_rank(
            domain=GAME_DOMAIN, pool_sha=pool_sha, locator_sha=locator_sha,
            protocol_uid=protocol_uid, protocol_version=protocol_version, split=split,
            protocol_sha=protocol_sha, group_uid=group, opaque_uid=row.opaque_uid), row.opaque_uid)))
    if len({row.task_group_uid for row in selected}) != count:
        raise AlfworldB0SelectionError(f"{split} selection duplicated a task group")
    return tuple(selected)


def select_prospective_b0(*, pool_manifest: Path, local_locator: Path,
                          protocol_uid: str, protocol_version: str,
                          protocol_sha256: str) -> B0Selection:
    """Verify commitments and select 8 train plus 4 valid-seen groups, no run implied."""
    if not isinstance(protocol_uid, str) or not protocol_uid or not isinstance(protocol_version, str) or not protocol_version:
        raise AlfworldB0SelectionError("protocol UID and version must be non-empty strings")
    protocol_sha = _sha(protocol_sha256, "protocol_sha256")
    manifest_raw, manifest = _read_object(pool_manifest, "pool manifest")
    # Do not json-decode the whole locator: valid_unseen record bodies remain
    # opaque and are only split-counted below.
    locator_raw = _read_regular_bytes(local_locator, "local locator")
    if manifest.get("schema_version") != POOL_SCHEMA or _locator_schema(locator_raw) != LOCATOR_SCHEMA:
        raise AlfworldB0SelectionError("ALFWorld pool or local locator schema drifted")
    aggregate = manifest.get("aggregate_commitment")
    if not isinstance(aggregate, dict):
        raise AlfworldB0SelectionError("pool aggregate commitment is absent")
    pool_sha, locator_sha = _digest(manifest_raw), _digest(locator_raw)
    if aggregate.get("local_locator_rendered_json_sha256") != locator_sha:
        raise AlfworldB0SelectionError("local locator rendered commitment mismatch")
    expected_counts = aggregate.get("selected_game_counts")
    expected_groups = aggregate.get("selected_task_group_counts")
    if not isinstance(expected_counts, dict) or not isinstance(expected_groups, dict):
        raise AlfworldB0SelectionError("pool aggregate counts are absent")

    selected_records: dict[str, list[OpaqueGameSelection]] = {"train": [], "valid_seen": []}
    raw_counts = {"train": 0, "valid_seen": 0, "valid_unseen": 0}
    for record_slice in _iter_record_slices(locator_raw):
        split = _split_only(record_slice)
        if split not in raw_counts:
            raise AlfworldB0SelectionError("local locator contains an undeclared split")
        raw_counts[split] += 1
        if split != "valid_unseen":
            selected_records[split].append(_decode_selectable_record(record_slice, split))
    for split, observed in raw_counts.items():
        if expected_counts.get(split) != observed:
            raise AlfworldB0SelectionError(f"local locator {split} count does not match aggregate")
    for split in ("train", "valid_seen"):
        if expected_groups.get(split) != len({row.task_group_uid for row in selected_records[split]}):
            raise AlfworldB0SelectionError(f"local locator {split} group count does not match aggregate")

    train = _choose_one_per_group(tuple(selected_records["train"]), count=TRAIN_GROUP_COUNT,
                                  pool_sha=pool_sha, locator_sha=locator_sha,
                                  protocol_uid=protocol_uid, protocol_version=protocol_version,
                                  protocol_sha=protocol_sha, split="train")
    valid_seen = _choose_one_per_group(tuple(selected_records["valid_seen"]), count=VALID_SEEN_GROUP_COUNT,
                                       pool_sha=pool_sha, locator_sha=locator_sha,
                                       protocol_uid=protocol_uid, protocol_version=protocol_version,
                                       protocol_sha=protocol_sha, split="valid_seen")
    digest = _digest(canonical_bytes({"train": [_private_row(row) for row in train], "valid_seen": [_private_row(row) for row in valid_seen]}))
    selector_sha = _digest(Path(__file__).read_bytes())
    return B0Selection(
        protocol_uid, protocol_version, protocol_sha, selector_sha,
        pool_sha, locator_sha, train, valid_seen, digest,
    )


def write_selection_receipts(*, selection: B0Selection, private_output: Path,
                             public_output: Path, repository_root: Path) -> None:
    """Write immutable local/private and aggregate/public receipts after explicit selection."""
    root = repository_root.resolve()
    private, public = private_output.resolve(), public_output.resolve()
    try:
        private.relative_to(root)
    except ValueError:
        pass
    else:
        raise AlfworldB0SelectionError("private selection receipt must be outside repository")
    try:
        public.relative_to((root / "manifests").resolve())
    except ValueError as error:
        raise AlfworldB0SelectionError("public selection projection must stay under repository/manifests") from error
    if private == public or private.exists() or public.exists():
        raise AlfworldB0SelectionError("selection receipt output must be distinct and not already exist")
    if private.is_symlink() or public.is_symlink():
        raise AlfworldB0SelectionError("selection receipt output must not be a symlink")
    if (not private.parent.is_dir() or private.parent.is_symlink()
            or not public.parent.is_dir() or public.parent.is_symlink()):
        raise AlfworldB0SelectionError("selection receipt parent directories must already exist")
    private_bytes = canonical_bytes(selection.private_receipt()) + b"\n"
    public_value = selection.public_projection()
    public_value.pop("public_projection_sha256")
    public_value["private_receipt_sha256"] = _digest(private_bytes)
    public_value["public_projection_sha256"] = _digest(canonical_bytes(public_value))
    public_bytes = canonical_bytes(public_value) + b"\n"
    for path, payload in ((private, private_bytes), (public, public_bytes)):
        try:
            with path.open("xb") as handle:
                handle.write(payload)
        except OSError as error:
            raise AlfworldB0SelectionError(f"could not create immutable selection receipt: {path}") from error
