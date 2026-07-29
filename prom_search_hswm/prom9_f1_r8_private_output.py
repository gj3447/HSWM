#!/usr/bin/env python3
"""Pre-call, fail-closed reservations for private HSWM r8 outputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_typed_ports import canonical_json


RESERVATION_SCHEMA = "hswm-prom9-f1-r8-private-output-reservation/v1"


class PrivateOutputRefusal(RuntimeError):
    """An output namespace or reserved inode is unsafe to publish into."""


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise PrivateOutputRefusal("private output write made no progress")
        offset += written


def _canonical_parent(path: Path) -> tuple[Path, str]:
    target = Path(path).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    current = Path(target.anchor)
    for part in target.parent.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            raise PrivateOutputRefusal("private output parent is unavailable") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise PrivateOutputRefusal("private output parent may not traverse a symlink")
    try:
        parent = target.parent.resolve(strict=True)
    except OSError as error:
        raise PrivateOutputRefusal("private output parent is unavailable") from error
    if not target.name or target.name in {".", ".."}:
        raise PrivateOutputRefusal("private output name is invalid")
    return parent, target.name


def canonical_output_path(path: Path) -> Path:
    parent, name = _canonical_parent(path)
    return parent / name


class PrivateOutputReservation:
    """Own one output path before network/model activity and commit on its inode."""

    def __init__(self, path: Path, *, run_id: str, role: str) -> None:
        if not isinstance(run_id, str) or not run_id or not isinstance(role, str) or not role:
            raise PrivateOutputRefusal("reservation run_id and role must be non-empty")
        self.path = canonical_output_path(path)
        self._parent_fd = os.open(
            self.path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
        )
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            self._fd = os.open(
                self.path.name, flags, 0o600, dir_fd=self._parent_fd
            )
        except FileExistsError as error:
            os.close(self._parent_fd)
            raise PrivateOutputRefusal("private output path is already occupied") from error
        except OSError:
            os.close(self._parent_fd)
            raise
        os.fchmod(self._fd, 0o600)
        opened = os.fstat(self._fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            self.close()
            raise PrivateOutputRefusal("private output reservation is not a unique regular file")
        self._identity = (opened.st_dev, opened.st_ino)
        marker_value = {
            "schema_version": RESERVATION_SCHEMA,
            "status": "RESERVED_NO_RESULT",
            "run_id": run_id,
            "role": role,
        }
        self._marker = (canonical_json(marker_value) + "\n").encode("utf-8")
        _write_all(self._fd, self._marker)
        os.fsync(self._fd)
        os.fsync(self._parent_fd)
        self._committed = False
        self._closed = False

    def _verify_owned_marker(self) -> None:
        try:
            path_info = os.stat(
                self.path.name, dir_fd=self._parent_fd, follow_symlinks=False
            )
            opened = os.fstat(self._fd)
        except OSError as error:
            raise PrivateOutputRefusal("reserved output path disappeared") from error
        if (
            not stat.S_ISREG(path_info.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or (path_info.st_dev, path_info.st_ino) != self._identity
            or (opened.st_dev, opened.st_ino) != self._identity
            or path_info.st_nlink != 1
            or opened.st_nlink != 1
            or stat.S_IMODE(path_info.st_mode) != 0o600
        ):
            raise PrivateOutputRefusal("reserved output inode ownership drifted")
        os.lseek(self._fd, 0, os.SEEK_SET)
        observed = bytearray()
        while block := os.read(self._fd, 1024 * 1024):
            observed.extend(block)
        if bytes(observed) != self._marker:
            raise PrivateOutputRefusal("reserved output marker drifted")

    def commit(self, value: Mapping[str, object]) -> str:
        if self._closed or self._committed:
            raise PrivateOutputRefusal("private output reservation is no longer writable")
        if not isinstance(value, Mapping):
            raise PrivateOutputRefusal("private output must be a JSON object")
        self._verify_owned_marker()
        payload = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        _write_all(self._fd, payload)
        os.fsync(self._fd)
        path_info = os.stat(
            self.path.name, dir_fd=self._parent_fd, follow_symlinks=False
        )
        opened = os.fstat(self._fd)
        if (
            (path_info.st_dev, path_info.st_ino) != self._identity
            or (opened.st_dev, opened.st_ino) != self._identity
            or path_info.st_nlink != 1
            or opened.st_nlink != 1
        ):
            raise PrivateOutputRefusal("reserved output inode changed during commit")
        os.fsync(self._parent_fd)
        os.lseek(self._fd, 0, os.SEEK_SET)
        observed = bytearray()
        while block := os.read(self._fd, 1024 * 1024):
            observed.extend(block)
        if bytes(observed) != payload:
            raise PrivateOutputRefusal("private output readback drifted")
        self._committed = True
        return hashlib.sha256(payload).hexdigest()

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        self._closed = True
        for descriptor in (getattr(self, "_fd", -1), getattr(self, "_parent_fd", -1)):
            if descriptor >= 0:
                os.close(descriptor)

    def __enter__(self) -> "PrivateOutputReservation":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


def reserve_private_outputs(
    outputs: Sequence[tuple[str, Path]],
    *,
    run_id: str,
    forbidden_paths: Sequence[Path] = (),
) -> dict[str, PrivateOutputReservation]:
    """Validate a closed output set, then reserve every path with O_EXCL."""

    if not outputs or any(not role for role, _path in outputs):
        raise PrivateOutputRefusal("at least one named output is required")
    normalized = [(role, canonical_output_path(path)) for role, path in outputs]
    paths = [path for _role, path in normalized]
    if len(set(paths)) != len(paths):
        raise PrivateOutputRefusal("private output paths collide")
    forbidden: set[Path] = set()
    for raw in forbidden_paths:
        try:
            forbidden.add(Path(raw).expanduser().resolve(strict=True))
        except OSError as error:
            raise PrivateOutputRefusal("forbidden input path is unavailable") from error
    if set(paths) & forbidden:
        raise PrivateOutputRefusal("private output aliases an input or database")
    reservations: dict[str, PrivateOutputReservation] = {}
    try:
        for role, path in normalized:
            if role in reservations:
                raise PrivateOutputRefusal("private output role repeats")
            reservations[role] = PrivateOutputReservation(
                path, run_id=run_id, role=role
            )
        return reservations
    except Exception:
        for reservation in reservations.values():
            reservation.close()
        raise


__all__ = [
    "PrivateOutputRefusal",
    "PrivateOutputReservation",
    "RESERVATION_SCHEMA",
    "canonical_output_path",
    "reserve_private_outputs",
]
