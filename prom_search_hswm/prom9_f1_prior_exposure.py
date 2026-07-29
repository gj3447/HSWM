#!/usr/bin/env python3
"""Build a private, fail-closed receipt for every prior HSWM F1 exposure.

The four historical Dataset Viewer pages are explicit offline inputs.  Their
opaque bytes remain embedded for audit, while item/source/component identity
is derived only from the allowlisted ``id``, ``question``, ``context``, and
``type`` fields.  Gold and judgment artifacts are inventoried as opaque bytes
and are never JSON-decoded by this module.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_r8_source import (
    COMPONENT_SCHEMA,
    SOURCE_ENTITY_SCHEMA,
    source_entity_id,
)


SCHEMA = "hswm-prom9-f1-prior-exposure/v1"
ABORTED_ATTEMPT_EXPOSURE_SCHEMA = (
    "hswm-prom9-f1-aborted-attempt-exposure/v1"
)
ABORTED_ATTEMPT_STATUS = "ABORTED_QUARANTINED"
DATASET_SERVER = "https://datasets-server.huggingface.co"
EXPECTED_PAGE_SPECS = ((0, 1), (0, 4), (0, 8), (4, 100))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROW_KEYS = {
    "id", "question", "answer", "context", "supporting_facts",
    "evidences", "type",
}

_ABORTED_ATTEMPT_SOURCE_ENTITY_IDS = [
    "62fae3c7206b92e5cbfae10a7df751ed8b6eba4979ce4d84a76173f777183705",
    "6f19a0c33d2b426c8085d17852acf6937779dbc049011284b8f8cc3e5757ef00",
    "78f42b260a62927800e2687fa02737af665ceebb15568b57df8c46fe88cec5a3",
    "7e0d80aaa85e7abf8ce30eb5ec2d426a6eefd28ce03e98845625577a27a57061",
    "8782a4cd6735509620fec41955d215431cde0a540fbb81d300ff0a42c4be26aa",
    "9ad0fd8fc2099664ed27019406df882bb284d9de79b2c271b3813d0201a71439",
    "a50a0b75cd71cef497203b5aebee7575c40d633f60835f29721af4e4e952efab",
    "b88446ef6e3f2cbf409287424ed9a56a701e09df49177c5c99437303df39e341",
    "bb4bcb851ccb6ed900fe21ed833855862ec4f6096143e191bca6c5150a291598",
    "bfc5f3085983a56df3bf226480dcdbd918687a5f0a15a8493e2af374c05af5d8",
]
_ABORTED_ATTEMPT_RUN_IDENTITY = {
    "run_id": "f1-2wiki-development-r8-try3",
    "job_name": "hswm-f1-r8-v8-development-825",
    "stage_path": "/data/kjra/PROJECT/PI/hswm_f1_r8_try3_v8_20260729",
    "host": "airobotics-Precision-7960-Tower",
    "started_at": "2026-07-29T23:15:22+09:00",
    "ended_at": "2026-07-29T23:15:34+09:00",
    "implementation_commit": "63a03623d98220800e9921527510d02971b882dc",
    "carrier_commit": "4da21495ed52d8c85ae112fdf5cf732c14fabaf9",
    "model": "qwen3.6-27b",
    "model_revision": "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9",
}
_ABORTED_ATTEMPT_TERMINATION = {"signal": "SIGBUS", "exit_code": 135}
_ABORTED_ATTEMPT_ACCEPTED_CALL = {
    "arm_id": "typed_hswm_three_function_network",
    "cohort": "development",
    "function_id": "QF_QUERY_COMPILER",
    "state": "ACCEPTED",
    "physical_call_id": (
        "3c9261a5e38c986c54e6c0bde7321baa4d9f7d2ef2052d407e864b4ee61a1f04"
    ),
    "item_id": "04a544a40bde11eba7f7acde48001122",
    "dataset_row_index": 124,
    "component_id": (
        "4a7e6b4488685b62049c278cc7adedceb0fa2bafc436ff2eda23050e80835539"
    ),
    "source_entity_ids": _ABORTED_ATTEMPT_SOURCE_ENTITY_IDS,
    "query_sha256": (
        "24aecf4cf1485f6775e83ae43052009a3e1d96c936b8de69edc0da01f3638ca8"
    ),
    "intent_sha256": (
        "d3771fe7aea13ad923371223af0f1babec3401f4b89daa2e5a232b82fcef3cf2"
    ),
    "request_sha256": (
        "fcc073995e29847e208dd40630a1b12cccd83d0c5ff34be19a647d97d69441fe"
    ),
    "response_sha256": (
        "cabaeec1ce8959202a64c3e998bb723be4daeedd1831627581b6cf5028a6ad87"
    ),
    "model_response_sha256": (
        "65dc7bc71a3dc5ce20767da5898ce1f5f904d74d45eee776d5613c2d38329189"
    ),
    "call_receipt_sha256": (
        "9da3704cb0034c8ef8d7c93c3648f3aae32bee56f3ee417bbc4e49a63c04e820"
    ),
}
_ABORTED_ATTEMPT_LOCAL_ONLY_CALL = {
    "arm_id": "typed_hswm_three_function_network",
    "cohort": "development",
    "function_id": "BF_BOND_PROPOSER",
    "state": "SENT_NOT_UPSTREAM",
    "physical_call_id": (
        "4cb5b7fcd108999198249a1561ba258a8cd510864693817891148f98706d08d7"
    ),
    "request_sha256": (
        "3d962fa008bcf9348eff7a68f82d30ebb61374cc1155715052c585b5cc5a8f52"
    ),
}
_ABORTED_ATTEMPT_NON_EXPOSURE = {
    "confirmatory_upstream_calls": 0,
    "requests_containing_gold_or_evaluator": 0,
    "runner_gold_opened": False,
    "evaluator_invoked": False,
    "scientific_verdict": False,
}
_ABORTED_ATTEMPT_EVIDENCE = {
    "causative_session": {
        "path": (
            "/Users/lagyeongjun/.codex/sessions/2026/07/29/"
            "rollout-2026-07-29T21-48-40-019fadeb-8269-7fc3-927c-"
            "e276c1b8fb93.jsonl"
        ),
        "hash_scope": "prefix",
        "prefix_bytes": 5681835,
        "prefix_lines": 1545,
        "prefix_sha256": (
            "9e917e0d0231e99457a4eefc0c7022deac5b8a5f733d00d8e315023659f34e97"
        ),
        "observed_file_bytes": 6216544,
        "observed_file_lines": 1620,
        "observed_file_sha256": (
            "0eccb877232d257dd983ed564d73e7f7916a99db07c278a86a8041d0165071e1"
        ),
    },
    "remote_command_file": {
        "path": "/data/kjra/.dt/jobs/hswm-f1-r8-v8-development-825/cmd.sh",
        "bytes": 3292,
        "sha256": (
            "569f64b8572c0831f93a00f17d861a8ff28533d1fa5e2ad0c1061495eed10eff"
        ),
    },
    "remote_job_log": {
        "path": "/data/kjra/.dt/jobs/hswm-f1-r8-v8-development-825/log",
        "bytes": 1606,
        "sha256": (
            "4f2d36b3b738c6920134573d9b1d555c33720436694067060e3d7633d82aba64"
        ),
        "rc": 135,
    },
    "vllm_access_log_snapshot": {
        "path": "/data/kjra/.dt/jobs/hswm-f1-r8-vllm-canary-triton/log",
        "snapshot_bytes": 46713,
        "snapshot_mtime": "2026-07-29T23:47:25.362464813+09:00",
        "snapshot_sha256": (
            "376a14d9e70c67a794a716fef4c967aa19848c47eafdbbe754bc81bf0971ad58"
        ),
        "post_count": 1,
        "server_pid": 1025995,
        "time_anchor_line": 423,
        "time_anchor_at": "2026-07-29T23:15:31+09:00",
        "time_anchor_running_requests": 1,
        "time_anchor_relation": "immediately_precedes_access_line",
        "access_line": 424,
        "source": "127.0.0.1:58622",
        "method": "POST",
        "request_path": "/v1/chat/completions",
        "protocol": "HTTP/1.1",
        "http_status": 200,
    },
    "attempt_database_family": {
        "attempt.sqlite3": (
            "360ae284913fbe7ea8ab58a3cce397e9cc11a4f39800896031676c80ba3f8005"
        ),
        "attempt.sqlite3-shm": (
            "cf62d20f247f7db7abf7f6d3ad7b11b5ac204b4e827fd616d3be679dd24d9d98"
        ),
        "attempt.sqlite3-wal": (
            "a1d43f941d6b7c8ac72b70fdf57ba7ae4d2344d2e74ed7273145cf337ef584ce"
        ),
    },
    "spool_database_family": {
        "spool.sqlite3": (
            "43e43c30c91c34ccf5e82019b9d4c6d6858e770702fe39e6c71c602c8c272ace"
        ),
        "spool.sqlite3-shm": (
            "8c2cb0e866accb47d8502501158dbe5774e9252ccce46baad47deceac7d27f14"
        ),
        "spool.sqlite3-wal": (
            "2038f2f362d69201e2ae20ab27557e4ec78414d3e7063de60437c0fb97035750"
        ),
    },
    "suite_draft_reservation_sha256": (
        "2cafa2404b8ac5b7e5f3b625e29a887bef4e87111201ce816c3ec51ee955429d"
    ),
}


class PriorExposureRefusal(RuntimeError):
    """The historical exposure boundary is incomplete or mutable."""


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise PriorExposureRefusal("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise PriorExposureRefusal("non-finite JSON number")


def _exact_json_equal(actual: object, expected: object) -> bool:
    """Compare JSON values without Python's bool/int/float equality aliases."""
    if isinstance(expected, dict):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(
                _exact_json_equal(actual[key], expected[key])
                for key in expected
            )
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _exact_json_equal(left, right)
                for left, right in zip(actual, expected, strict=True)
            )
        )
    return type(actual) is type(expected) and actual == expected


def _read_private_bytes(path: Path) -> bytes:
    target = Path(path)
    try:
        info = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("private input is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PriorExposureRefusal("private input must be a regular non-symlink file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PriorExposureRefusal("private input must not be group/world accessible")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise PriorExposureRefusal("private input cannot be opened") from error
    payload = bytearray()
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != info.st_dev
            or opened.st_ino != info.st_ino
            or stat.S_IMODE(opened.st_mode) & 0o077
        ):
            raise PriorExposureRefusal("private input changed before being read")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("private input cannot be restated") from error
    identity = lambda value: (  # noqa: E731 - compact immutable projection
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if (
        identity(info) != identity(after_fd)
        or identity(info) != identity(after_path)
        or len(payload) != info.st_size
    ):
        raise PriorExposureRefusal("private input changed while being read")
    return bytes(payload)


def _strict_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except PriorExposureRefusal:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PriorExposureRefusal(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise PriorExposureRefusal(f"{label} must be an object")
    return value


def _page_projection(
    page: Mapping[str, object], *, offset: int, length: int
) -> list[dict[str, object]]:
    wrapped_rows = page.get("rows")
    if not isinstance(wrapped_rows, list) or len(wrapped_rows) != length:
        raise PriorExposureRefusal("legacy page length drifted")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for position, wrapped in enumerate(wrapped_rows):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("row"), dict):
            raise PriorExposureRefusal("legacy page row is malformed")
        row = wrapped["row"]
        if set(row) != _ROW_KEYS:
            raise PriorExposureRefusal("legacy page row schema drifted")
        item_id = row.get("id")
        question = row.get("question")
        question_type = row.get("type")
        context = row.get("context")
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in seen
            or not isinstance(question, str)
            or not question
            or not isinstance(question_type, str)
            or not isinstance(context, dict)
            or set(context) != {"title", "sentences"}
        ):
            raise PriorExposureRefusal("legacy page allowlisted identity drifted")
        titles = context.get("title")
        sentence_groups = context.get("sentences")
        if (
            not isinstance(titles, list)
            or not isinstance(sentence_groups, list)
            or not titles
            or len(titles) != len(sentence_groups)
        ):
            raise PriorExposureRefusal("legacy page context arrays drifted")
        entities: list[str] = []
        normalized_context = {"title": [], "sentences": []}
        for title, sentences in zip(titles, sentence_groups):
            if (
                not isinstance(title, str)
                or not title
                or not isinstance(sentences, list)
                or any(not isinstance(sentence, str) for sentence in sentences)
            ):
                raise PriorExposureRefusal("legacy page paragraph drifted")
            normalized_sentences = [str(sentence) for sentence in sentences]
            normalized_context["title"].append(title)
            normalized_context["sentences"].append(normalized_sentences)
            entities.append(source_entity_id(title, normalized_sentences))
        seen.add(item_id)
        result.append(
            {
                "dataset_row_index": offset + position,
                "item_id": item_id,
                "question": question,
                "context": normalized_context,
                "question_type": question_type,
                "question_sha256": canonical_sha256({"question": question}),
                "context_sha256": canonical_sha256({"context": normalized_context}),
                "source_entity_ids": sorted(set(entities)),
                "component_id": None,
            }
        )
    return result


def _assign_components(items: list[dict[str, object]]) -> list[dict[str, object]]:
    parent = {str(item["item_id"]): str(item["item_id"]) for item in items}

    def find(item_id: str) -> str:
        while parent[item_id] != item_id:
            parent[item_id] = parent[parent[item_id]]
            item_id = parent[item_id]
        return item_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    owner: dict[str, str] = {}
    for item in items:
        item_id = str(item["item_id"])
        for entity_id in item["source_entity_ids"]:
            prior = owner.setdefault(str(entity_id), item_id)
            union(item_id, prior)
    component_entities: dict[str, set[str]] = {}
    for item in items:
        component_entities.setdefault(find(str(item["item_id"])), set()).update(
            str(value) for value in item["source_entity_ids"]
        )
    component_ids = {
        root: canonical_sha256(
            {
                "schema_version": COMPONENT_SCHEMA,
                "source_entity_ids": sorted(entities),
            }
        )
        for root, entities in component_entities.items()
    }
    components: dict[str, dict[str, object]] = {}
    for item in items:
        item_id = str(item["item_id"])
        component_id = component_ids[find(item_id)]
        item["component_id"] = component_id
        component = components.setdefault(
            component_id,
            {
                "component_id": component_id,
                "item_ids": [],
                "source_entity_ids": sorted(component_entities[find(item_id)]),
            },
        )
        component["item_ids"].append(item_id)
    for component in components.values():
        component["item_ids"].sort()
    return [components[key] for key in sorted(components)]


def _tree_entries(root: Path) -> list[tuple[str, int, int, int, int]]:
    result: list[tuple[str, int, int, int, int]] = []
    for path in sorted(Path(root).rglob("*"), key=lambda value: value.as_posix()):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise PriorExposureRefusal("artifact tree contains a symlink")
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise PriorExposureRefusal("artifact tree contains a special file")
        result.append(
            (relative, info.st_size, stat.S_IMODE(info.st_mode), info.st_mtime_ns, info.st_ino)
        )
    return result


def _hash_file_stable(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise PriorExposureRefusal("artifact changed while hashing")
    return digest.hexdigest()


def inventory_stable_tree(alias: str, root: Path) -> list[dict[str, object]]:
    if not alias or "/" in alias or "=" in alias:
        raise PriorExposureRefusal("artifact alias is invalid")
    resolved = Path(root).resolve(strict=True)
    if not resolved.is_dir():
        raise PriorExposureRefusal("artifact root must be a directory")
    before = _tree_entries(resolved)
    inventory = [
        {
            "root_alias": alias,
            "path": relative,
            "size_bytes": size,
            "mode": mode,
            "sha256": _hash_file_stable(resolved / relative),
        }
        for relative, size, mode, _mtime, _inode in before
    ]
    after = _tree_entries(resolved)
    if before != after:
        raise PriorExposureRefusal("artifact tree changed while hashing")
    return inventory


def _extract_item_ids(document: Mapping[str, object], kind: str) -> list[str]:
    if kind == "manifest":
        rows = document.get("items")
        key = "item_id"
    elif kind == "suite":
        rows = document.get("item_runs")
        key = "item_id"
    elif kind == "source_receipt":
        rows = document.get("rows")
        key = "item_id"
    else:
        raise PriorExposureRefusal("unsupported identity artifact kind")
    if not isinstance(rows, list) or not rows:
        raise PriorExposureRefusal("identity artifact has no rows")
    values = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str):
            raise PriorExposureRefusal("identity artifact row drifted")
        values.append(str(row[key]))
    unique = sorted(set(values))
    if kind != "suite" and len(unique) != len(values):
        raise PriorExposureRefusal("identity artifact repeats an item")
    return unique


def _identity_kind(path: Path) -> str | None:
    name = path.name
    if name.startswith("manifest") and name.endswith(".json"):
        return "manifest"
    if name == "suite.json":
        return "suite"
    if "source.receipt" in name and name.endswith(".json"):
        return "source_receipt"
    return None


def _legacy_bindings(
    roots: Mapping[str, Path],
    page_items: Mapping[tuple[int, int], set[str]],
    page_hashes: Mapping[tuple[int, int], str],
    aggregate_items: set[str],
) -> tuple[list[dict[str, object]], dict[str, int], int]:
    bindings: list[dict[str, object]] = []
    counts = {"manifest": 0, "suite": 0, "source_receipt": 0}
    run_dirs: set[tuple[str, str]] = set()
    for alias, root in roots.items():
        resolved = Path(root).resolve(strict=True)
        for directory in sorted(
            (path for path in resolved.rglob("f1-2wiki-*") if path.is_dir()),
            key=lambda value: value.as_posix(),
        ):
            identity_paths = [
                path for path in directory.glob("*.json") if _identity_kind(path)
            ]
            if not identity_paths:
                raise PriorExposureRefusal("F1 run directory lacks an identity artifact")
            run_dirs.add((alias, directory.relative_to(resolved).as_posix()))
            run_sets: list[set[str]] = []
            for path in sorted(identity_paths):
                kind = _identity_kind(path)
                assert kind is not None
                raw = _read_private_bytes(path) if stat.S_IMODE(path.stat().st_mode) & 0o077 == 0 else path.read_bytes()
                document = _strict_object(raw, kind)
                item_ids = _extract_item_ids(document, kind)
                item_set = set(item_ids)
                if not item_set <= aggregate_items:
                    raise PriorExposureRefusal("historical artifact contains an unbound item")
                matches = [spec for spec, values in page_items.items() if values == item_set]
                if len(matches) != 1:
                    raise PriorExposureRefusal("historical artifact does not match one frozen page")
                if kind == "source_receipt":
                    declared = document.get("source_receipt_sha256")
                    unsigned = dict(document)
                    unsigned.pop("source_receipt_sha256", None)
                    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
                        raise PriorExposureRefusal("legacy source receipt self-hash drifted")
                    matched_spec = matches[0]
                    if (
                        document.get("offset") != matched_spec[0]
                        or document.get("length") != matched_spec[1]
                        or document.get("viewer_response_sha256")
                        != page_hashes[matched_spec]
                    ):
                        raise PriorExposureRefusal(
                            "legacy source receipt page binding drifted"
                        )
                counts[kind] += 1
                run_sets.append(item_set)
                bindings.append(
                    {
                        "root_alias": alias,
                        "path": path.relative_to(resolved).as_posix(),
                        "kind": kind,
                        "raw_sha256": hashlib.sha256(raw).hexdigest(),
                        "internal_sha256": document.get("source_receipt_sha256"),
                        "page_id": f"validation-o{matches[0][0]}-n{matches[0][1]}",
                        "item_set_sha256": canonical_sha256(item_ids),
                    }
                )
            if any(values != run_sets[0] for values in run_sets[1:]):
                raise PriorExposureRefusal("identity artifacts disagree within an F1 run")
    return sorted(bindings, key=lambda value: (str(value["root_alias"]), str(value["path"]))), counts, len(run_dirs)


def build_prior_exposure_receipt(
    *,
    page_files: Mapping[tuple[int, int], tuple[Path, str]],
    artifact_roots: Mapping[str, Path],
    dataset: str,
    config: str,
    split: str,
    expected_run_dirs: int,
    expected_legacy_source_receipts: int,
    expected_manifests: int,
    expected_suites: int,
) -> dict[str, object]:
    if set(page_files) != set(EXPECTED_PAGE_SPECS):
        raise PriorExposureRefusal("the exact four legacy pages are required")
    pages: list[dict[str, object]] = []
    projections_by_spec: dict[tuple[int, int], list[dict[str, object]]] = {}
    aggregate_by_index: dict[int, dict[str, object]] = {}
    for offset, length in EXPECTED_PAGE_SPECS:
        path, expected_sha = page_files[(offset, length)]
        if not _SHA256.fullmatch(expected_sha):
            raise PriorExposureRefusal("legacy page expectation is not a SHA-256")
        raw = _read_private_bytes(path)
        page = _strict_object(raw, "legacy Dataset Viewer page")
        canonical_page_sha = canonical_sha256(page)
        if canonical_page_sha != expected_sha:
            raise PriorExposureRefusal("legacy Dataset Viewer page hash drifted")
        projection = _page_projection(page, offset=offset, length=length)
        projections_by_spec[(offset, length)] = projection
        for item in projection:
            index = int(item["dataset_row_index"])
            prior = aggregate_by_index.setdefault(index, item)
            if prior != item:
                raise PriorExposureRefusal("overlapping legacy pages disagree")
        pages.append(
            {
                "page_id": f"validation-o{offset}-n{length}",
                "offset": offset,
                "length": length,
                "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                "canonical_viewer_response_sha256": canonical_page_sha,
                "payload_base64": base64.b64encode(raw).decode("ascii"),
                "whitelisted_projection_sha256": canonical_sha256(projection),
            }
        )
    if sorted(aggregate_by_index) != list(range(104)):
        raise PriorExposureRefusal("legacy page union is not exactly validation rows 0..103")
    items = [aggregate_by_index[index] for index in sorted(aggregate_by_index)]
    if len({str(item["item_id"]) for item in items}) != 104:
        raise PriorExposureRefusal("legacy page union does not contain 104 unique items")
    components = _assign_components(items)
    aggregate_items = {str(item["item_id"]) for item in items}
    page_items = {
        spec: {str(item["item_id"]) for item in projection}
        for spec, projection in projections_by_spec.items()
    }
    roots = {alias: Path(path).resolve(strict=True) for alias, path in artifact_roots.items()}
    inventory = [
        item
        for alias in sorted(roots)
        for item in inventory_stable_tree(alias, roots[alias])
    ]
    bindings, identity_counts, run_dir_count = _legacy_bindings(
        roots,
        page_items,
        {spec: page_files[spec][1] for spec in EXPECTED_PAGE_SPECS},
        aggregate_items,
    )
    if (
        run_dir_count != expected_run_dirs
        or identity_counts["source_receipt"] != expected_legacy_source_receipts
        or identity_counts["manifest"] != expected_manifests
        or identity_counts["suite"] != expected_suites
    ):
        raise PriorExposureRefusal("historical artifact completeness counts drifted")
    item_ids = sorted(aggregate_items)
    source_entities = sorted(
        {str(entity) for item in items for entity in item["source_entity_ids"]}
    )
    component_ids = sorted(str(component["component_id"]) for component in components)
    roots_block = {
        "pages": canonical_sha256(pages),
        "items": canonical_sha256(items),
        "source_entities": canonical_sha256(source_entities),
        "components": canonical_sha256(components),
        "legacy_receipts": canonical_sha256(bindings),
        "artifact_inventory": canonical_sha256(inventory),
    }
    unsigned = {
        "schema_version": SCHEMA,
        "dataset_identity": {
            "dataset": dataset,
            "config": config,
            "split": split,
            "dataset_server": DATASET_SERVER,
        },
        "privacy_policy": {
            "derived_fields": ["id", "question", "context", "type"],
            "opaque_only_fields": ["answer", "supporting_facts", "evidences"],
            "answers_disclosed_to_stdout": False,
            "private_mode": "0600",
        },
        "page_specs": [
            {"offset": offset, "length": length, "expected_sha256": page_files[(offset, length)][1]}
            for offset, length in EXPECTED_PAGE_SPECS
        ],
        "pages": pages,
        "items": items,
        "components": components,
        "legacy_source_receipts": bindings,
        "artifact_roots": [
            {"alias": alias, "resolved_path": str(roots[alias])}
            for alias in sorted(roots)
        ],
        "artifact_inventory": inventory,
        "roots": roots_block,
        "counts": {
            "pages": len(pages),
            "items": len(item_ids),
            "source_entities": len(source_entities),
            "components": len(component_ids),
            "run_directories": run_dir_count,
            "manifests": identity_counts["manifest"],
            "suites": identity_counts["suite"],
            "legacy_source_receipts": identity_counts["source_receipt"],
            "artifact_files": len(inventory),
        },
        "aggregate": {
            "prior_item_ids": item_ids,
            "prior_source_entity_ids": source_entities,
            "prior_component_ids": component_ids,
            "item_root_sha256": canonical_sha256(item_ids),
            "source_entity_root_sha256": canonical_sha256(source_entities),
            "component_root_sha256": canonical_sha256(component_ids),
        },
        "complete": True,
    }
    return {**unsigned, "prior_exposure_receipt_sha256": canonical_sha256(unsigned)}


def verify_prior_exposure_receipt(value: Mapping[str, object]) -> str:
    if value.get("schema_version") != SCHEMA or value.get("complete") is not True:
        raise PriorExposureRefusal("prior-exposure receipt is incomplete")
    unsigned = dict(value)
    declared = unsigned.pop("prior_exposure_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise PriorExposureRefusal("prior-exposure receipt self-hash drifted")
    aggregate = value.get("aggregate")
    if not isinstance(aggregate, dict):
        raise PriorExposureRefusal("prior-exposure aggregate is absent")
    for key, root_key in (
        ("prior_item_ids", "item_root_sha256"),
        ("prior_source_entity_ids", "source_entity_root_sha256"),
        ("prior_component_ids", "component_root_sha256"),
    ):
        values = aggregate.get(key)
        if not isinstance(values, list) or canonical_sha256(values) != aggregate.get(root_key):
            raise PriorExposureRefusal("prior-exposure aggregate root drifted")
    return declared


def _strict_boundary_values(
    aggregate: Mapping[str, object], key: str, label: str
) -> list[str]:
    values = aggregate.get(key)
    if (
        not isinstance(values, list)
        or any(not isinstance(item, str) or not item for item in values)
        or values != sorted(set(values))
    ):
        raise PriorExposureRefusal(f"{label} are not a sorted unique string list")
    return values


def verify_aborted_attempt_exposure_receipt(
    value: Mapping[str, object],
) -> str:
    """Verify the immutable public boundary for the quarantined r8/v8 attempt."""
    expected_top_level = {
        "schema_version",
        "status",
        "run_identity",
        "termination",
        "accepted_upstream_calls",
        "local_only_calls",
        "non_exposure_boundary",
        "evidence",
        "evidence_roots",
        "counts",
        "aggregate",
        "complete",
        "aborted_attempt_exposure_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected_top_level:
        raise PriorExposureRefusal("aborted-attempt receipt shape drifted")
    if (
        value.get("schema_version") != ABORTED_ATTEMPT_EXPOSURE_SCHEMA
        or value.get("status") != ABORTED_ATTEMPT_STATUS
        or value.get("complete") is not True
    ):
        raise PriorExposureRefusal("aborted-attempt receipt is not quarantined and complete")

    unsigned = dict(value)
    declared = unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    try:
        computed = canonical_sha256(unsigned)
    except Exception as error:
        raise PriorExposureRefusal(
            "aborted-attempt receipt is not canonical JSON"
        ) from error
    if (
        not isinstance(declared, str)
        or not _SHA256.fullmatch(declared)
        or computed != declared
    ):
        raise PriorExposureRefusal("aborted-attempt receipt self-hash drifted")

    run_identity = value.get("run_identity")
    termination = value.get("termination")
    accepted_calls = value.get("accepted_upstream_calls")
    local_calls = value.get("local_only_calls")
    non_exposure = value.get("non_exposure_boundary")
    evidence = value.get("evidence")
    evidence_roots = value.get("evidence_roots")
    counts = value.get("counts")
    aggregate = value.get("aggregate")
    if not _exact_json_equal(run_identity, _ABORTED_ATTEMPT_RUN_IDENTITY):
        raise PriorExposureRefusal("aborted-attempt run identity drifted")
    if not _exact_json_equal(termination, _ABORTED_ATTEMPT_TERMINATION):
        raise PriorExposureRefusal("aborted-attempt termination drifted")
    if (
        not isinstance(accepted_calls, list)
        or len(accepted_calls) != 1
        or not _exact_json_equal(
            accepted_calls[0], _ABORTED_ATTEMPT_ACCEPTED_CALL
        )
    ):
        raise PriorExposureRefusal("accepted upstream exposure drifted")
    if (
        not isinstance(local_calls, list)
        or len(local_calls) != 1
        or not _exact_json_equal(
            local_calls[0], _ABORTED_ATTEMPT_LOCAL_ONLY_CALL
        )
    ):
        raise PriorExposureRefusal("local-only call boundary drifted")
    if not _exact_json_equal(non_exposure, _ABORTED_ATTEMPT_NON_EXPOSURE):
        raise PriorExposureRefusal("non-exposure boundary drifted")
    if not _exact_json_equal(evidence, _ABORTED_ATTEMPT_EVIDENCE):
        raise PriorExposureRefusal("aborted-attempt evidence drifted")

    expected_evidence_roots = {
        "attempt_database_family_root_sha256": canonical_sha256(
            _ABORTED_ATTEMPT_EVIDENCE["attempt_database_family"]
        ),
        "spool_database_family_root_sha256": canonical_sha256(
            _ABORTED_ATTEMPT_EVIDENCE["spool_database_family"]
        ),
    }
    if not _exact_json_equal(evidence_roots, expected_evidence_roots):
        raise PriorExposureRefusal("aborted-attempt evidence root drifted")

    expected_counts = {
        "accepted_development_upstream_calls": len(accepted_calls),
        "local_only_calls": len(local_calls),
        "confirmatory_upstream_calls": non_exposure[
            "confirmatory_upstream_calls"
        ],
        "requests_containing_gold_or_evaluator": non_exposure[
            "requests_containing_gold_or_evaluator"
        ],
        "items": 1,
        "source_entities": len(_ABORTED_ATTEMPT_SOURCE_ENTITY_IDS),
        "components": 1,
    }
    if not _exact_json_equal(counts, expected_counts):
        raise PriorExposureRefusal("aborted-attempt exposure counts drifted")
    if not isinstance(aggregate, Mapping) or set(aggregate) != {
        "prior_item_ids",
        "prior_source_entity_ids",
        "prior_component_ids",
        "item_root_sha256",
        "source_entity_root_sha256",
        "component_root_sha256",
    }:
        raise PriorExposureRefusal("aborted-attempt aggregate shape drifted")
    item_ids = _strict_boundary_values(aggregate, "prior_item_ids", "item ids")
    source_entity_ids = _strict_boundary_values(
        aggregate, "prior_source_entity_ids", "source entity ids"
    )
    component_ids = _strict_boundary_values(
        aggregate, "prior_component_ids", "component ids"
    )
    accepted = accepted_calls[0]
    if (
        item_ids != [accepted["item_id"]]
        or source_entity_ids != accepted["source_entity_ids"]
        or component_ids != [accepted["component_id"]]
        or canonical_sha256(
            {
                "schema_version": COMPONENT_SCHEMA,
                "source_entity_ids": source_entity_ids,
            }
        )
        != component_ids[0]
    ):
        raise PriorExposureRefusal("aborted-attempt aggregate exposure drifted")
    for values, root_key in (
        (item_ids, "item_root_sha256"),
        (source_entity_ids, "source_entity_root_sha256"),
        (component_ids, "component_root_sha256"),
    ):
        if canonical_sha256(values) != aggregate.get(root_key):
            raise PriorExposureRefusal("aborted-attempt aggregate root drifted")
    if (
        counts["items"] != len(item_ids)
        or counts["source_entities"] != len(source_entity_ids)
        or counts["components"] != len(component_ids)
    ):
        raise PriorExposureRefusal("aborted-attempt aggregate count drifted")
    return declared


def merge_exposure_boundaries(
    prior: Mapping[str, object], incident: Mapping[str, object]
) -> dict[str, object]:
    """Return the canonical union of historical and aborted-attempt exposure."""
    prior_sha = verify_prior_exposure_receipt(prior)
    incident_sha = verify_aborted_attempt_exposure_receipt(incident)
    prior_aggregate = prior.get("aggregate")
    incident_aggregate = incident.get("aggregate")
    if not isinstance(prior_aggregate, Mapping) or not isinstance(
        incident_aggregate, Mapping
    ):
        raise PriorExposureRefusal("exposure aggregate is absent")

    def merged(key: str, label: str) -> list[str]:
        historical = _strict_boundary_values(prior_aggregate, key, label)
        aborted = _strict_boundary_values(incident_aggregate, key, label)
        return sorted(set(historical).union(aborted))

    item_ids = merged("prior_item_ids", "item ids")
    source_entity_ids = merged("prior_source_entity_ids", "source entity ids")
    component_ids = merged("prior_component_ids", "component ids")
    return {
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": incident_sha,
        "item_ids": item_ids,
        "source_entity_ids": source_entity_ids,
        "component_ids": component_ids,
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entity_ids),
        "component_root_sha256": canonical_sha256(component_ids),
    }


def write_private_once(path: Path, value: Mapping[str, object]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.partial-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise PriorExposureRefusal("refusing to replace prior-exposure receipt") from error
        directory = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _page_arg(value: str) -> tuple[tuple[int, int], tuple[Path, str]]:
    try:
        offset_text, length_text, expected_sha, path_text = value.split(":", 3)
        spec = (int(offset_text), int(length_text))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(
            "page must be OFFSET:LENGTH:EXPECTED_SHA256:PATH"
        ) from error
    return spec, (Path(path_text), expected_sha)


def _root_arg(value: str) -> tuple[str, Path]:
    try:
        alias, path = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("artifact root must be ALIAS=PATH") from error
    return alias, Path(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", action="append", type=_page_arg, required=True)
    parser.add_argument("--artifact-root", action="append", type=_root_arg, required=True)
    parser.add_argument("--dataset", default="framolfese/2WikiMultihopQA")
    parser.add_argument("--config", default="default")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--expect-run-dirs", type=int, required=True)
    parser.add_argument("--expect-legacy-source-receipts", type=int, required=True)
    parser.add_argument("--expect-manifests", type=int, required=True)
    parser.add_argument("--expect-suites", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        pages = dict(args.page)
        roots = dict(args.artifact_root)
        if len(pages) != len(args.page) or len(roots) != len(args.artifact_root):
            raise PriorExposureRefusal("duplicate page or artifact-root argument")
        receipt = build_prior_exposure_receipt(
            page_files=pages,
            artifact_roots=roots,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            expected_run_dirs=args.expect_run_dirs,
            expected_legacy_source_receipts=args.expect_legacy_source_receipts,
            expected_manifests=args.expect_manifests,
            expected_suites=args.expect_suites,
        )
        verify_prior_exposure_receipt(receipt)
        write_private_once(args.output, receipt)
        print(
            json.dumps(
                {
                    "status": "COMPLETE_NO_ANSWERS_DISCLOSED",
                    **receipt["counts"],
                    "prior_exposure_receipt_sha256": receipt[
                        "prior_exposure_receipt_sha256"
                    ],
                    "roots": receipt["roots"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ABORTED_ATTEMPT_EXPOSURE_SCHEMA",
    "ABORTED_ATTEMPT_STATUS",
    "EXPECTED_PAGE_SPECS",
    "PriorExposureRefusal",
    "SCHEMA",
    "build_prior_exposure_receipt",
    "inventory_stable_tree",
    "merge_exposure_boundaries",
    "verify_aborted_attempt_exposure_receipt",
    "verify_prior_exposure_receipt",
    "write_private_once",
]
