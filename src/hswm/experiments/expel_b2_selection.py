"""Prospective, B2-only opaque ALFWorld selection.

This selector is deliberately not an occurrence runner.  It receives the
rendered pool and locator pins from a future frozen B2 protocol, streams the
locator, and never JSON-decodes a ``valid_unseen`` record.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
from typing import Mapping

from _research.dnrd5.canonical_json import canonical_bytes
from . import alfworld_b0_selection as b0


SELECTION_SCHEMA = "hswm-expel-b2-selection/v1"
PRIVATE_SCHEMA = "hswm-expel-b2-selection-private-receipt/v1"
GROUP_DOMAIN = "HSWM_EXPEL_B2_GROUP/v1"
GAME_DOMAIN = "HSWM_EXPEL_B2_GAME/v1"
TRAIN_GROUP_COUNT = 8
VALID_SEEN_GROUP_COUNT = 4
B0_UID = "sym:ExploratoryStudy:hswm-alfworld-b0-calibration-2026-08-30"


class ExpelB2SelectionError(RuntimeError):
    """A proposed B2 selection violates a source or zero-touch boundary."""


@dataclass(frozen=True, slots=True)
class B2Selection:
    occurrence_uid: str
    protocol_uid: str
    protocol_version: str
    protocol_sha256: str
    selector_source_sha256: str
    pool_manifest_sha256: str
    local_locator_sha256: str
    train: tuple[b0.OpaqueGameSelection, ...]
    valid_seen: tuple[b0.OpaqueGameSelection, ...]
    selection_digest: str

    def _identity(self) -> dict[str, str]:
        return {"occurrence_uid": self.occurrence_uid, "protocol_uid": self.protocol_uid,
                "protocol_version": self.protocol_version, "protocol_file_sha256": self.protocol_sha256}

    def private_receipt(self) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": PRIVATE_SCHEMA,
            "record_role": "LOCAL_NONREPOSITORY_OPAQUE_B2_SELECTION_RECEIPT_NOT_FOR_REDISTRIBUTION",
            "status": "PROSPECTIVE_SELECTION_ONLY_B2_NOT_RUN",
            "selection_identity": self._identity(),
            "selection_identity_sha256": _canonical_sha(self._identity()),
            "selector": {"schema_version": SELECTION_SCHEMA, "source_sha256": self.selector_source_sha256,
                         "group_rank_domain": GROUP_DOMAIN, "game_rank_domain": GAME_DOMAIN},
            "input_commitments": {"pool_manifest_rendered_json_sha256": self.pool_manifest_sha256,
                                  "local_locator_rendered_json_sha256": self.local_locator_sha256},
            "selection_digest_sha256": self.selection_digest,
            "selected": {"train": [_row(x) for x in self.train], "valid_seen": [_row(x) for x in self.valid_seen]},
            "valid_unseen_selected_group_count": 0,
            "no_claim": "Local prospective selection only; no game, model call, outcome, or occurrence was run.",
        }
        value["private_receipt_sha256"] = _canonical_sha(value)
        return value

    def verify_inputs(self, *, pool_manifest: Path, local_locator: Path) -> None:
        """Recompute this immutable selection before a runner writes its start event.

        The comparison intentionally covers the private receipt, rather than
        only its selected rows: the occurrence/protocol identity, source pins,
        selector identity and canonical selection digest must all remain bound.
        """
        recomputed = select_prospective_b2(
            pool_manifest=pool_manifest, local_locator=local_locator,
            occurrence_uid=self.occurrence_uid, protocol_uid=self.protocol_uid,
            protocol_version=self.protocol_version, protocol_sha256=self.protocol_sha256,
            expected_pool_manifest_sha256=self.pool_manifest_sha256,
            expected_local_locator_sha256=self.local_locator_sha256,
        )
        if recomputed.private_receipt() != self.private_receipt():
            raise ExpelB2SelectionError("B2 selection private receipt identity or digest drifted")

    def public_projection(self, *, private_receipt_sha256: str) -> dict[str, object]:
        _sha(private_receipt_sha256, "private_receipt_sha256")
        value: dict[str, object] = {
            "schema_version": SELECTION_SCHEMA,
            "record_role": "AGGREGATE_PROSPECTIVE_B2_SELECTION_COMMITMENT_NOT_A_RESULT",
            "status": "PROSPECTIVE_SELECTION_ONLY_B2_NOT_RUN",
            "selection_identity": self._identity(),
            "selection_identity_sha256": _canonical_sha(self._identity()),
            "selector": {"schema_version": SELECTION_SCHEMA, "source_sha256": self.selector_source_sha256,
                         "group_rank_domain": GROUP_DOMAIN, "game_rank_domain": GAME_DOMAIN},
            "input_commitments": {"pool_manifest_rendered_json_sha256": self.pool_manifest_sha256,
                                  "local_locator_rendered_json_sha256": self.local_locator_sha256},
            "selection": {"without_replacement": True, "selected_group_counts": {"train": TRAIN_GROUP_COUNT, "valid_seen": VALID_SEEN_GROUP_COUNT},
                          "valid_unseen_selected_group_count": 0,
                          "valid_unseen_record_detail_access": "SPLIT_TOKEN_ONLY_NO_UID_PATH_DECODE_OR_RETENTION",
                          "selection_digest_sha256": self.selection_digest},
            "private_receipt_sha256": private_receipt_sha256,
            "no_claim": ["Aggregate prospective selection only.", "No individual game UID, group UID, path, task, prompt, trajectory, outcome, model call, or result is present.", "Not a G0/G1 result or efficacy claim."],
        }
        value["public_projection_sha256"] = _canonical_sha(value)
        return value


def _row(value: b0.OpaqueGameSelection) -> dict[str, str]:
    return {"split": value.split, "task_group_uid": value.task_group_uid, "opaque_uid": value.opaque_uid}


def _canonical_sha(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _sha(value: object, label: str) -> str:
    try:
        return b0._sha(value, label)
    except b0.AlfworldB0SelectionError as error:
        raise ExpelB2SelectionError(str(error)) from error


def _identity(*, occurrence_uid: str, protocol_uid: str, protocol_version: str, protocol_sha256: str) -> None:
    for label, value in (("occurrence_uid", occurrence_uid), ("protocol_uid", protocol_uid), ("protocol_version", protocol_version)):
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ExpelB2SelectionError(f"{label} must be a nonempty bounded identifier")
        if value == B0_UID or "alfworld-b0" in value.lower():
            raise ExpelB2SelectionError(f"{label} must not reuse a B0 identity")
    _sha(protocol_sha256, "protocol_sha256")


def _rank(*, domain: str, pool_sha: str, locator_sha: str, occurrence_uid: str, protocol_uid: str,
          protocol_version: str, protocol_sha: str, split: str, group_uid: str, opaque_uid: str = "") -> str:
    return sha256(b"\0".join(x.encode() for x in (domain, pool_sha, locator_sha, occurrence_uid, protocol_uid,
                  protocol_version, protocol_sha, split, group_uid, opaque_uid))).hexdigest()


def _select(rows: tuple[b0.OpaqueGameSelection, ...], *, split: str, count: int, pool_sha: str, locator_sha: str,
            occurrence_uid: str, protocol_uid: str, protocol_version: str, protocol_sha: str) -> tuple[b0.OpaqueGameSelection, ...]:
    groups: dict[str, list[b0.OpaqueGameSelection]] = {}
    for row in rows:
        groups.setdefault(row.task_group_uid, []).append(row)
    if len(groups) < count:
        raise ExpelB2SelectionError(f"{split} has too few task groups")
    ordered = sorted(groups, key=lambda group: (_rank(domain=GROUP_DOMAIN, pool_sha=pool_sha, locator_sha=locator_sha, occurrence_uid=occurrence_uid, protocol_uid=protocol_uid, protocol_version=protocol_version, protocol_sha=protocol_sha, split=split, group_uid=group), group))
    return tuple(min(groups[group], key=lambda row: (_rank(domain=GAME_DOMAIN, pool_sha=pool_sha, locator_sha=locator_sha, occurrence_uid=occurrence_uid, protocol_uid=protocol_uid, protocol_version=protocol_version, protocol_sha=protocol_sha, split=split, group_uid=group, opaque_uid=row.opaque_uid), row.opaque_uid)) for group in ordered[:count])


def select_prospective_b2(*, pool_manifest: Path, local_locator: Path, occurrence_uid: str, protocol_uid: str,
                          protocol_version: str, protocol_sha256: str, expected_pool_manifest_sha256: str,
                          expected_local_locator_sha256: str) -> B2Selection:
    """Verify mandatory source pins and select B2's fresh 8+4 groups only."""
    _identity(occurrence_uid=occurrence_uid, protocol_uid=protocol_uid, protocol_version=protocol_version, protocol_sha256=protocol_sha256)
    expected_pool, expected_locator = _sha(expected_pool_manifest_sha256, "expected_pool_manifest_sha256"), _sha(expected_local_locator_sha256, "expected_local_locator_sha256")
    try:
        manifest_raw, manifest = b0._read_object(pool_manifest, "pool manifest")
        locator_raw = b0._read_regular_bytes(local_locator, "local locator")
    except b0.AlfworldB0SelectionError as error:
        raise ExpelB2SelectionError(str(error)) from error
    pool_sha, locator_sha = sha256(manifest_raw).hexdigest(), sha256(locator_raw).hexdigest()
    if pool_sha != expected_pool or locator_sha != expected_locator:
        raise ExpelB2SelectionError("source-pinned pool or locator rendered digest mismatch")
    if manifest.get("schema_version") != b0.POOL_SCHEMA or b0._locator_schema(locator_raw) != b0.LOCATOR_SCHEMA:
        raise ExpelB2SelectionError("pool or locator schema drifted")
    aggregate = manifest.get("aggregate_commitment")
    if not isinstance(aggregate, dict) or aggregate.get("local_locator_rendered_json_sha256") != locator_sha:
        raise ExpelB2SelectionError("pool does not commit the exact local locator")
    expected_counts, expected_groups = aggregate.get("selected_game_counts"), aggregate.get("selected_task_group_counts")
    if not isinstance(expected_counts, dict) or not isinstance(expected_groups, dict):
        raise ExpelB2SelectionError("pool aggregate commitments are absent")
    records: dict[str, list[b0.OpaqueGameSelection]] = {"train": [], "valid_seen": []}
    counts = {"train": 0, "valid_seen": 0, "valid_unseen": 0}
    try:
        slices = b0._iter_record_slices(locator_raw)
        for record_slice in slices:
            split = b0._split_only(record_slice)
            if split not in counts:
                raise ExpelB2SelectionError("local locator contains an undeclared split")
            counts[split] += 1
            if split != "valid_unseen":
                records[split].append(b0._decode_selectable_record(record_slice, split))
    except b0.AlfworldB0SelectionError as error:
        raise ExpelB2SelectionError(str(error)) from error
    if any(expected_counts.get(split) != count for split, count in counts.items()):
        raise ExpelB2SelectionError("local locator count does not match pool commitment")
    if any(expected_groups.get(split) != len({x.task_group_uid for x in records[split]}) for split in records):
        raise ExpelB2SelectionError("local locator group count does not match pool commitment")
    train = _select(tuple(records["train"]), split="train", count=TRAIN_GROUP_COUNT, pool_sha=pool_sha, locator_sha=locator_sha, occurrence_uid=occurrence_uid, protocol_uid=protocol_uid, protocol_version=protocol_version, protocol_sha=protocol_sha256)
    train_groups = {row.task_group_uid for row in train}
    valid_candidates = tuple(row for row in records["valid_seen"] if row.task_group_uid not in train_groups)
    valid_seen = _select(valid_candidates, split="valid_seen", count=VALID_SEEN_GROUP_COUNT, pool_sha=pool_sha, locator_sha=locator_sha, occurrence_uid=occurrence_uid, protocol_uid=protocol_uid, protocol_version=protocol_version, protocol_sha=protocol_sha256)
    if (len({x.task_group_uid for x in train}) != TRAIN_GROUP_COUNT
            or len({x.task_group_uid for x in valid_seen}) != VALID_SEEN_GROUP_COUNT
            or train_groups & {row.task_group_uid for row in valid_seen}
            or {row.opaque_uid for row in train} & {row.opaque_uid for row in valid_seen}):
        raise ExpelB2SelectionError("selection is not without replacement across splits")
    selected = {"train": [_row(x) for x in train], "valid_seen": [_row(x) for x in valid_seen]}
    return B2Selection(occurrence_uid, protocol_uid, protocol_version, protocol_sha256, sha256(Path(__file__).read_bytes()).hexdigest(), pool_sha, locator_sha, train, valid_seen, _canonical_sha(selected))


def verify_private_selection(receipt: Path, *, occurrence_uid: str, protocol_uid: str, protocol_version: str,
                             protocol_sha256: str, expected_pool_manifest_sha256: str,
                             expected_local_locator_sha256: str) -> tuple[b0.OpaqueGameSelection, ...]:
    """Verify a private B2 receipt before a future runner consumes its rows."""
    _identity(occurrence_uid=occurrence_uid, protocol_uid=protocol_uid, protocol_version=protocol_version, protocol_sha256=protocol_sha256)
    try:
        raw, value = b0._read_object(receipt, "private B2 selection receipt")
    except b0.AlfworldB0SelectionError as error:
        raise ExpelB2SelectionError(str(error)) from error
    if raw != canonical_bytes(value) + b"\n" or value.get("schema_version") != PRIVATE_SCHEMA:
        raise ExpelB2SelectionError("private B2 receipt must be canonical")
    digest = value.get("private_receipt_sha256")
    unsigned = {k: v for k, v in value.items() if k != "private_receipt_sha256"}
    if digest != _canonical_sha(unsigned):
        raise ExpelB2SelectionError("private B2 receipt digest drifted")
    if value.get("selection_identity") != {"occurrence_uid": occurrence_uid, "protocol_uid": protocol_uid, "protocol_version": protocol_version, "protocol_file_sha256": protocol_sha256}:
        raise ExpelB2SelectionError("private B2 receipt identity mismatch")
    if value.get("selection_identity_sha256") != _canonical_sha(value["selection_identity"]):
        raise ExpelB2SelectionError("private B2 receipt identity digest drifted")
    inputs = value.get("input_commitments")
    if inputs != {"pool_manifest_rendered_json_sha256": _sha(expected_pool_manifest_sha256, "expected_pool_manifest_sha256"), "local_locator_rendered_json_sha256": _sha(expected_local_locator_sha256, "expected_local_locator_sha256")}:
        raise ExpelB2SelectionError("private B2 receipt source commitment mismatch")
    selected = value.get("selected")
    if not isinstance(selected, dict) or set(selected) != {"train", "valid_seen"}:
        raise ExpelB2SelectionError("private B2 receipt selected rows drifted")
    result: list[b0.OpaqueGameSelection] = []
    selected_groups: set[str] = set()
    selected_games: set[str] = set()
    for split, count in (("train", TRAIN_GROUP_COUNT), ("valid_seen", VALID_SEEN_GROUP_COUNT)):
        rows = selected[split]
        if not isinstance(rows, list) or len(rows) != count:
            raise ExpelB2SelectionError("private B2 receipt allocation drifted")
        decoded = tuple(b0.OpaqueGameSelection(**row) for row in rows if isinstance(row, dict) and set(row) == {"split", "task_group_uid", "opaque_uid"})
        if (len(decoded) != count or any(row.split != split for row in decoded)
                or any(not isinstance(row.task_group_uid, str) or not row.task_group_uid
                       or not isinstance(row.opaque_uid, str) or not row.opaque_uid for row in decoded)
                or len({row.task_group_uid for row in decoded}) != count
                or len({row.opaque_uid for row in decoded}) != count
                or selected_groups & {row.task_group_uid for row in decoded}
                or selected_games & {row.opaque_uid for row in decoded}):
            raise ExpelB2SelectionError("private B2 receipt identities or groups are not unique")
        selected_groups.update(row.task_group_uid for row in decoded)
        selected_games.update(row.opaque_uid for row in decoded)
        result.extend(decoded)
    if value.get("selection_digest_sha256") != _canonical_sha({"train": [_row(x) for x in result[:TRAIN_GROUP_COUNT]], "valid_seen": [_row(x) for x in result[TRAIN_GROUP_COUNT:]]}):
        raise ExpelB2SelectionError("private B2 receipt selection digest drifted")
    return tuple(result)


def write_selection_receipts(*, selection: B2Selection, private_output: Path, public_output: Path, repository_root: Path) -> None:
    root, private, public = repository_root.resolve(), private_output.resolve(), public_output.resolve()
    if private.is_relative_to(root) or not public.is_relative_to((root / "manifests").resolve()) or private == public:
        raise ExpelB2SelectionError("private receipt must stay outside repository and public receipt under manifests")
    if private.exists() or public.exists() or private.is_symlink() or public.is_symlink() or not private.parent.is_dir() or not public.parent.is_dir():
        raise ExpelB2SelectionError("receipt outputs must be distinct absent files in existing directories")
    private_value = selection.private_receipt()
    private_bytes = canonical_bytes(private_value) + b"\n"
    public_bytes = canonical_bytes(selection.public_projection(private_receipt_sha256=sha256(private_bytes).hexdigest())) + b"\n"
    for path, payload in ((private, private_bytes), (public, public_bytes)):
        with path.open("xb") as handle:
            handle.write(payload)


def _write_receipt(path: Path, payload: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_wrapper_selection_receipts(*, selection: B2Selection, output_root: Path) -> tuple[Path, Path]:
    """Atomically create wrapper-owned, non-resumable B2 selection receipts."""
    if not output_root.is_absolute() or output_root.is_symlink() or not output_root.is_dir():
        raise ExpelB2SelectionError("HSWM_OUTPUT_ROOT must be an absolute regular directory")
    private, public = output_root / "selection.private.json", output_root / "selection.public.json"
    if any(path.exists() or path.is_symlink() for path in (private, public)):
        raise ExpelB2SelectionError("selection wrapper output cannot resume or overwrite receipts")
    private_bytes = canonical_bytes(selection.private_receipt()) + b"\n"
    public_bytes = canonical_bytes(selection.public_projection(private_receipt_sha256=sha256(private_bytes).hexdigest())) + b"\n"
    try:
        _write_receipt(private, private_bytes)
        _write_receipt(public, public_bytes)
        _fsync_directory(output_root)
    except Exception:
        # A prefix is intentionally retained; callers must not overwrite or resume it.
        raise
    return private, public


def _roots() -> tuple[Path, Path]:
    output_raw, cache_raw = os.environ.get("HSWM_OUTPUT_ROOT"), os.environ.get("HSWM_CACHE_ROOT")
    if not output_raw or not cache_raw:
        raise ExpelB2SelectionError("must run through wrapper with HSWM_OUTPUT_ROOT and HSWM_CACHE_ROOT")
    output, cache = Path(output_raw), Path(cache_raw)
    for label, path in (("HSWM_OUTPUT_ROOT", output), ("HSWM_CACHE_ROOT", cache)):
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            raise ExpelB2SelectionError(f"{label} must be an absolute regular directory")
    return output, cache


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write one frozen B2 selection receipt pair")
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--pool", required=True, type=Path)
    parser.add_argument("--locator", required=True, type=Path)
    args = parser.parse_args(argv)
    # Verification precedes selector import/use and rejects drafts before any locator read.
    from .expel_b2_protocol import verify_protocol
    protocol = verify_protocol(args.protocol)
    output, _cache = _roots()
    evidence = protocol["current_evidence"]
    selection = select_prospective_b2(
        pool_manifest=args.pool, local_locator=args.locator,
        occurrence_uid=str(protocol["occurrence_uid"]), protocol_uid=str(protocol["study_uid"]),
        protocol_version=str(protocol["protocol_version"]), protocol_sha256=sha256(args.protocol.read_bytes()).hexdigest(),
        expected_pool_manifest_sha256=str(evidence["pool_manifest"]["rendered_json_sha256"]),
        expected_local_locator_sha256=str(evidence["local_locator_rendered_json_sha256"]),
    )
    write_wrapper_selection_receipts(selection=selection, output_root=output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
