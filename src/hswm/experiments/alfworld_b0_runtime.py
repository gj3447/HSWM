"""B0-only streaming local-game binding that keeps ``valid_unseen`` opaque.

This module deliberately sits beside, rather than changes, the hash-bound G0
runtime instrument.  It reuses its game-binding type and validation rules while
parsing a large local locator only far enough to bind a selected train or
valid-seen row.  Final-holdout rows are scanned for their split token only.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterator, Mapping

from .alfworld_text_runtime import AlfworldTextRuntimeError, LocalGameBinding


def _read_regular_bytes(path: Path, field: str) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise AlfworldTextRuntimeError(f"{field} must be an absolute non-symlink regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise AlfworldTextRuntimeError(f"{field} is unreadable") from error


def _read_json_object(path: Path, field: str) -> tuple[bytes, Mapping[str, object]]:
    raw = _read_regular_bytes(path, field)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldTextRuntimeError(f"{field} is unreadable JSON") from error
    if not isinstance(value, dict):
        raise AlfworldTextRuntimeError(f"{field} must be a JSON object")
    return raw, value


def _skip_json_whitespace(raw: bytes, index: int) -> int:
    while index < len(raw) and raw[index] in b" \t\r\n":
        index += 1
    return index


def _scan_json_string(raw: bytes, index: int) -> int:
    if index >= len(raw) or raw[index] != ord('"'):
        raise AlfworldTextRuntimeError("local locator JSON string is malformed")
    index += 1
    escaped = False
    while index < len(raw):
        char = raw[index]
        if escaped:
            escaped = False
        elif char == ord("\\"):
            escaped = True
        elif char == ord('"'):
            return index + 1
        elif char < 0x20:
            raise AlfworldTextRuntimeError("local locator JSON string has a control byte")
        index += 1
    raise AlfworldTextRuntimeError("local locator JSON string is unterminated")


def _records_bounds(raw: bytes) -> tuple[int, int]:
    """Find the top-level records array without decoding record payloads."""
    index = _skip_json_whitespace(raw, 0)
    if index >= len(raw) or raw[index] != ord("{"):
        raise AlfworldTextRuntimeError("local locator must be a JSON object")
    index += 1
    while index < len(raw):
        index = _skip_json_whitespace(raw, index)
        if index < len(raw) and raw[index] == ord("}"):
            break
        key_start, key_end = index, _scan_json_string(raw, index)
        index = _skip_json_whitespace(raw, key_end)
        if index >= len(raw) or raw[index] != ord(":"):
            raise AlfworldTextRuntimeError("local locator key lacks a colon")
        index = _skip_json_whitespace(raw, index + 1)
        if raw[key_start:key_end] == b'"records"':
            if index >= len(raw) or raw[index] != ord("["):
                raise AlfworldTextRuntimeError("local locator records must be an array")
            start, cursor, quoted, escaped, array_depth = index, index + 1, False, False, 1
            while cursor < len(raw):
                char = raw[cursor]
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == ord("\\"):
                        escaped = True
                    elif char == ord('"'):
                        quoted = False
                elif char == ord('"'):
                    quoted = True
                elif char == ord("["):
                    array_depth += 1
                elif char == ord("]"):
                    array_depth -= 1
                    if array_depth == 0:
                        return start, cursor + 1
                cursor += 1
            raise AlfworldTextRuntimeError("local locator records array is unterminated")
        if index >= len(raw):
            raise AlfworldTextRuntimeError("local locator value is absent")
        quoted, escaped, nested = False, False, 0
        while index < len(raw):
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
            elif char in (ord("{"), ord("[")):
                nested += 1
            elif char in (ord("}"), ord("]")):
                if nested == 0:
                    break
                nested -= 1
            elif char == ord(",") and nested == 0:
                index += 1
                break
            index += 1
    raise AlfworldTextRuntimeError("local locator records are absent")


def _locator_metadata_and_record_bytes(raw: bytes) -> tuple[Mapping[str, object], bytes]:
    start, end = _records_bounds(raw)
    metadata_raw = raw[:start] + b"[]" + raw[end:]
    try:
        metadata = json.loads(metadata_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldTextRuntimeError("local locator metadata is unreadable JSON") from error
    if not isinstance(metadata, dict) or not isinstance(metadata.get("records"), list) or metadata["records"]:
        raise AlfworldTextRuntimeError("local locator metadata contract drifted")
    return metadata, raw[start + 1:end - 1]


def _minified_json_bytes(raw: bytes) -> bytes:
    output = bytearray()
    quoted = escaped = False
    for char in raw:
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == ord("\\"):
                escaped = True
            elif char == ord('"'):
                quoted = False
        elif char == ord('"'):
            quoted = True
            output.append(char)
        elif char not in b" \t\r\n":
            output.append(char)
    if quoted or escaped:
        raise AlfworldTextRuntimeError("local locator JSON string is unterminated")
    return bytes(output)


def _iter_record_slices(raw: bytes) -> Iterator[bytes]:
    index = 0
    while True:
        index = _skip_json_whitespace(raw, index)
        while index < len(raw) and raw[index] == ord(","):
            index = _skip_json_whitespace(raw, index + 1)
        if index >= len(raw):
            return
        if raw[index] != ord("{"):
            raise AlfworldTextRuntimeError("local locator record must be an object")
        start, depth, quoted, escaped = index, 0, False, False
        while index < len(raw):
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
            raise AlfworldTextRuntimeError("local locator record is unterminated")


_SPLIT_TOKEN = re.compile(rb'"split"\s*:\s*"([a-z_]+)"')


def _record_split(record_raw: bytes) -> str:
    match = _SPLIT_TOKEN.search(record_raw)
    if match is None:
        raise AlfworldTextRuntimeError("local locator record split is absent")
    try:
        return match.group(1).decode("ascii")
    except UnicodeDecodeError as error:
        raise AlfworldTextRuntimeError("local locator record split is invalid") from error


def _matches_opaque_uid(record_raw: bytes, opaque_uid: str) -> bool:
    encoded = json.dumps(opaque_uid, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return re.search(rb'"opaque_uid"\s*:\s*' + re.escape(encoded) + rb"(?=\s*[,}])", record_raw) is not None


def load_local_game_binding(*, pool_manifest: Path, local_locator: Path, asset_root: Path,
                            opaque_uid: str) -> tuple[str, str, LocalGameBinding, Path]:
    """Bind one train/valid-seen record without decoding valid-unseen rows."""
    manifest_raw, manifest = _read_json_object(pool_manifest, "pool manifest")
    locator_raw = _read_regular_bytes(local_locator, "local locator")
    locator, record_bytes = _locator_metadata_and_record_bytes(locator_raw)
    if manifest.get("schema_version") != "hswm-alfworld-text-clean-pool/v2":
        raise AlfworldTextRuntimeError("pool manifest schema drifted")
    if locator.get("schema_version") != "hswm-alfworld-text-clean-pool-local-locator/v1":
        raise AlfworldTextRuntimeError("local locator schema drifted")
    aggregate = manifest.get("aggregate_commitment")
    if not isinstance(aggregate, dict):
        raise AlfworldTextRuntimeError("pool aggregate commitment is absent")
    if (aggregate.get("local_locator_rendered_json_sha256") != sha256(locator_raw).hexdigest()
            or aggregate.get("local_locator_canonical_json_sha256") != sha256(_minified_json_bytes(locator_raw)).hexdigest()):
        raise AlfworldTextRuntimeError("local locator commitment mismatch")
    if locator.get("pool_commitment") != {
        key: aggregate.get(key)
        for key in (
            "selected_game_counts",
            "selected_game_bytes_by_split",
            "selected_task_group_counts",
            "task_group_overlap_counts",
            "selected_game_total",
        )
    }:
        raise AlfworldTextRuntimeError("local locator pool counts mismatch")
    source = manifest.get("source_binding")
    locator_source = locator.get("source_binding")
    if not isinstance(source, dict) or not isinstance(locator_source, dict):
        raise AlfworldTextRuntimeError("pool source binding is absent")
    if locator_source.get("repository_commit") != source.get("repository_commit") or locator_source.get("assets") != source.get("official_release_assets"):
        raise AlfworldTextRuntimeError("local locator source binding mismatch")
    selected_raw: bytes | None = None
    for record_raw in _iter_record_slices(record_bytes):
        split = _record_split(record_raw)
        if split == "valid_unseen":
            continue
        if split not in {"train", "valid_seen"}:
            raise AlfworldTextRuntimeError("local locator record split is undeclared")
        if _matches_opaque_uid(record_raw, opaque_uid):
            if selected_raw is not None:
                raise AlfworldTextRuntimeError("opaque UID must select exactly one local game")
            selected_raw = record_raw
    if selected_raw is None:
        raise AlfworldTextRuntimeError("opaque UID must select exactly one local game")
    try:
        record = json.loads(selected_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldTextRuntimeError("selected local locator record is unreadable JSON") from error
    expected = {"bytes", "file_sha256", "opaque_uid", "relative_path", "relative_path_sha256", "split", "task_group_uid"}
    if (not isinstance(record, dict) or set(record) != expected or record.get("opaque_uid") != opaque_uid
            or record.get("split") not in {"train", "valid_seen"}
            or not isinstance(record["relative_path"], str)
            or sha256(record["relative_path"].encode("utf-8")).hexdigest() != record["relative_path_sha256"]):
        raise AlfworldTextRuntimeError("local locator record contract drifted")
    binding = LocalGameBinding(record["opaque_uid"], record["relative_path"], record["file_sha256"], record["bytes"])
    binding.validate()
    if not asset_root.is_absolute() or not asset_root.is_dir() or asset_root.is_symlink():
        raise AlfworldTextRuntimeError("asset_root must be an absolute non-symlink directory")
    return sha256(manifest_raw).hexdigest(), sha256(locator_raw).hexdigest(), binding, asset_root / binding.relative_path
