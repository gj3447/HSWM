from __future__ import annotations

import json
import os
from pathlib import Path
import stat

import pytest

from prom_search_hswm.prom9_f1_r8_private_output import (
    PrivateOutputRefusal,
    PrivateOutputReservation,
    reserve_private_outputs,
)


def test_reservation_is_0600_marker_then_same_inode_commit(tmp_path: Path) -> None:
    output = tmp_path / "private" / "suite.json"
    with PrivateOutputReservation(output, run_id="run", role="suite") as reservation:
        before = output.stat()
        marker = json.loads(output.read_text(encoding="utf-8"))
        assert marker["status"] == "RESERVED_NO_RESULT"
        assert stat.S_IMODE(before.st_mode) == 0o600
        reservation.commit({"schema_version": "suite/v1", "receipt_sha256": "a" * 64})
        after = output.stat()
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
        assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == "suite/v1"


def test_existing_or_colliding_paths_refuse_without_replacement(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied.json"
    occupied.write_bytes(b"foreign")
    occupied.chmod(0o600)
    with pytest.raises(PrivateOutputRefusal, match="occupied"):
        PrivateOutputReservation(occupied, run_id="run", role="suite")
    assert occupied.read_bytes() == b"foreign"

    same = tmp_path / "same.json"
    with pytest.raises(PrivateOutputRefusal, match="collide"):
        reserve_private_outputs(
            [("suite", same), ("preflight", same)], run_id="run"
        )
    assert not same.exists()


def test_input_alias_and_reserved_inode_replacement_are_refused(tmp_path: Path) -> None:
    input_path = tmp_path / "manifest.json"
    input_path.write_bytes(b"input")
    input_path.chmod(0o600)
    with pytest.raises(PrivateOutputRefusal, match="aliases"):
        reserve_private_outputs(
            [("suite", input_path)], run_id="run", forbidden_paths=[input_path]
        )
    assert input_path.read_bytes() == b"input"

    output = tmp_path / "suite.json"
    reservation = PrivateOutputReservation(output, run_id="run", role="suite")
    output.unlink()
    output.write_bytes(b"foreign replacement")
    output.chmod(0o600)
    try:
        with pytest.raises(PrivateOutputRefusal, match="ownership drifted"):
            reservation.commit({"schema_version": "suite/v1"})
        assert output.read_bytes() == b"foreign replacement"
    finally:
        reservation.close()


def test_hardlinked_reservation_is_refused_at_commit(tmp_path: Path) -> None:
    output = tmp_path / "suite.json"
    alias = tmp_path / "suite.alias"
    reservation = PrivateOutputReservation(output, run_id="run", role="suite")
    os.link(output, alias)
    try:
        with pytest.raises(PrivateOutputRefusal, match="ownership drifted"):
            reservation.commit({"schema_version": "suite/v1"})
    finally:
        reservation.close()
