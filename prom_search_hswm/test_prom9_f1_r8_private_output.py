from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys

import pytest

import prom_search_hswm.prom9_f1_r8_private_output as private_output
from prom_search_hswm.prom9_f1_r8_private_output import (
    JOURNAL_SCHEMA,
    PrivateOutputRefusal,
    RESERVATION_SCHEMA,
    reserve_private_outputs,
)


def _journal(
    tmp_path: Path,
    outputs: list[tuple[str, Path]],
    *,
    resume: bool = False,
    run_id: str = "run",
):
    return reserve_private_outputs(
        outputs,
        run_id=run_id,
        journal_path=tmp_path / "reservation.sqlite3",
        resume=resume,
    )


def _row(path: Path, role: str = "suite") -> sqlite3.Row:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM reservations WHERE role=?", (role,)
        ).fetchone()
        assert row is not None
        return row
    finally:
        connection.close()


def _resume_prefix(run_id: str = "run") -> dict[str, object]:
    unsigned = {
        "schema_version": private_output.RESUME_PREFIX_SCHEMA,
        "run_id": run_id,
        "db_genesis_sha256": "1" * 64,
        "attempt_integrity": "ok",
        "spool_integrity": "ok",
        "attempt_db_identity": {},
        "spool_db_identity": {},
        "ordered_job_root_sha256": "2" * 64,
        "job_count": 0,
        "max_workers": 1,
        "frontier_batch": -1,
        "call_positions": [],
        "call_count": 0,
        "item_run_count": 0,
        "attempt_event_count": 0,
        "spool_call_count": 0,
        "event_chain_tip_sha256": "0" * 64,
        "attempt_event_root_sha256": "3" * 64,
        "attempt_live_audit": {},
        "spool_live_audit": {},
        "zero_count_genesis": True,
    }
    return {
        **unsigned,
        "resume_prefix_sha256": private_output.canonical_sha256(unsigned),
    }


def test_v2_marker_journal_binding_and_same_inode_commit(tmp_path: Path) -> None:
    output = tmp_path / "private" / "suite.json"
    journal_path = tmp_path / "reservation.sqlite3"
    with _journal(tmp_path, [("suite", output)]) as journal:
        reservation = journal["suite"]
        before = output.stat()
        marker_bytes = output.read_bytes()
        marker = json.loads(marker_bytes)
        row = _row(journal_path)
        journal_stat = journal_path.stat()
        assert marker["schema_version"] == RESERVATION_SCHEMA
        assert marker["status"] == "RESERVED_NO_RESULT"
        assert marker["journal"] == {
            "resolved_path": str(journal_path),
            "st_dev": journal_stat.st_dev,
            "st_ino": journal_stat.st_ino,
        }
        assert marker["reservation_nonce"] == row["reservation_nonce"]
        assert row["marker_bytes"] == marker_bytes
        assert row["marker_sha256"] == hashlib.sha256(marker_bytes).hexdigest()
        assert (row["output_dev"], row["output_ino"]) == (
            before.st_dev,
            before.st_ino,
        )
        assert row["state"] == "RESERVED"
        assert stat.S_IMODE(before.st_mode) == 0o600
        assert stat.S_IMODE(journal_stat.st_mode) == 0o600
        payload = {"schema_version": "suite/v1", "receipt_sha256": "a" * 64}
        digest = reservation.commit(payload)
        after = output.stat()
        assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
        assert reservation.state == "COMMITTED"
        assert reservation.committed_value() == payload
        meta = sqlite3.connect(journal_path).execute(
            "SELECT schema_version FROM journal_meta WHERE singleton=1"
        ).fetchone()
        assert meta == (JOURNAL_SCHEMA,)


def test_existing_colliding_alias_and_locked_journal_refuse(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied.json"
    occupied.write_bytes(b"foreign")
    occupied.chmod(0o600)
    with pytest.raises(PrivateOutputRefusal, match="occupied"):
        _journal(tmp_path, [("suite", occupied)])
    assert occupied.read_bytes() == b"foreign"

    same = tmp_path / "same.json"
    with pytest.raises(PrivateOutputRefusal, match="collide"):
        _journal(tmp_path, [("suite", same), ("preflight", same)])
    assert not same.exists()

    input_path = tmp_path / "manifest.json"
    input_path.write_bytes(b"input")
    input_path.chmod(0o600)
    with pytest.raises(PrivateOutputRefusal, match="aliases"):
        reserve_private_outputs(
            [("suite", input_path)],
            run_id="run",
            journal_path=tmp_path / "journal.sqlite3",
            forbidden_paths=[input_path],
        )

    lock_root = tmp_path / "lock"
    first = _journal(lock_root, [("suite", lock_root / "suite.json")])
    try:
        with pytest.raises(PrivateOutputRefusal, match="another runner"):
            _journal(
                lock_root,
                [("suite", lock_root / "suite.json")],
                resume=True,
            )
    finally:
        first.close()


def test_inode_hardlink_marker_and_journal_drift_refuse(tmp_path: Path) -> None:
    output = tmp_path / "suite.json"
    journal = _journal(tmp_path, [("suite", output)])
    try:
        alias = tmp_path / "suite.alias"
        os.link(output, alias)
        with pytest.raises(PrivateOutputRefusal, match="ownership drifted"):
            journal["suite"].commit({"schema_version": "suite/v1"})
    finally:
        journal.close()


def test_lock_inode_is_persisted_and_replacement_never_refences(
    tmp_path: Path,
) -> None:
    output = tmp_path / "suite.json"
    journal_path = tmp_path / "reservation.sqlite3"
    lock_path = Path(f"{journal_path}.lock")
    with _journal(tmp_path, [("suite", output)]):
        pass
    lock_path.unlink()
    lock_path.write_bytes(b"replacement")
    lock_path.chmod(0o600)
    with pytest.raises(PrivateOutputRefusal, match="binding"):
        _journal(tmp_path, [("suite", output)], resume=True)

    live_root = tmp_path / "live"
    live_output = live_root / "suite.json"
    live_journal_path = live_root / "reservation.sqlite3"
    live_lock_path = Path(f"{live_journal_path}.lock")
    owner = _journal(live_root, [("suite", live_output)])
    try:
        live_lock_path.unlink()
        live_lock_path.write_bytes(b"replacement")
        live_lock_path.chmod(0o600)
        with pytest.raises(PrivateOutputRefusal, match="binding"):
            _journal(live_root, [("suite", live_output)], resume=True)
        with pytest.raises(PrivateOutputRefusal, match="identity drifted"):
            owner["suite"].commit({"schema_version": "suite/v1"})
    finally:
        owner.close()


@pytest.mark.parametrize("suffix", ("-wal", "-shm"))
def test_fresh_refuses_preexisting_journal_family_without_mutation(
    tmp_path: Path,
    suffix: str,
) -> None:
    journal_path = tmp_path / "reservation.sqlite3"
    occupied = Path(f"{journal_path}{suffix}")
    occupied.write_bytes(b"foreign-family-member")
    occupied.chmod(0o640)
    before = (occupied.read_bytes(), stat.S_IMODE(occupied.stat().st_mode))
    with pytest.raises(PrivateOutputRefusal, match="occupied"):
        reserve_private_outputs(
            [("suite", tmp_path / "suite.json")],
            run_id="run",
            journal_path=journal_path,
        )
    assert (occupied.read_bytes(), stat.S_IMODE(occupied.stat().st_mode)) == before


def test_existing_prepared_output_is_never_chmodded_or_prefix_adopted(
    tmp_path: Path,
) -> None:
    output = tmp_path / "suite.json"
    journal_path = tmp_path / "reservation.sqlite3"
    with _journal(tmp_path, [("suite", output)]):
        pass
    connection = sqlite3.connect(journal_path)
    connection.execute(
        "UPDATE reservations SET state='RESERVATION_PREPARED',"
        "marker_bytes=NULL,marker_sha256=NULL,output_dev=NULL,output_ino=NULL "
        "WHERE role='suite'"
    )
    connection.commit()
    connection.close()
    output.write_bytes(b"{")
    output.chmod(0o600)
    with pytest.raises(PrivateOutputRefusal, match="cannot be adopted"):
        _journal(tmp_path, [("suite", output)], resume=True)
    assert output.read_bytes() == b"{"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    mode_root = tmp_path / "mode"
    mode_output = mode_root / "suite.json"
    mode_journal = mode_root / "reservation.sqlite3"
    with _journal(mode_root, [("suite", mode_output)]):
        pass
    connection = sqlite3.connect(mode_journal)
    connection.execute(
        "UPDATE reservations SET state='RESERVATION_PREPARED',"
        "marker_bytes=NULL,marker_sha256=NULL,output_dev=NULL,output_ino=NULL "
        "WHERE role='suite'"
    )
    connection.commit()
    connection.close()
    mode_output.write_bytes(b"foreign")
    mode_output.chmod(0o640)
    with pytest.raises(PrivateOutputRefusal, match="cannot be adopted"):
        _journal(mode_root, [("suite", mode_output)], resume=True)
    assert mode_output.read_bytes() == b"foreign"
    assert stat.S_IMODE(mode_output.stat().st_mode) == 0o640


def test_resume_rejects_semantic_journal_and_audit_tampering(
    tmp_path: Path,
) -> None:
    output = tmp_path / "suite.json"
    journal_path = tmp_path / "reservation.sqlite3"
    with _journal(tmp_path, [("suite", output)]) as journal:
        journal.record_resume_audit(_resume_prefix())
    connection = sqlite3.connect(journal_path)
    connection.execute(
        "UPDATE resume_audits SET receipt_sha256=? WHERE ordinal=0",
        ("f" * 64,),
    )
    connection.commit()
    connection.close()
    with pytest.raises(PrivateOutputRefusal, match="resume audit binding"):
        _journal(tmp_path, [("suite", output)], resume=True)

    trigger_root = tmp_path / "trigger"
    trigger_output = trigger_root / "suite.json"
    trigger_journal = trigger_root / "reservation.sqlite3"
    with _journal(trigger_root, [("suite", trigger_output)]):
        pass
    connection = sqlite3.connect(trigger_journal)
    connection.execute(
        "CREATE TRIGGER forbidden_update BEFORE UPDATE ON reservations "
        "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
    )
    connection.commit()
    connection.close()
    with pytest.raises(PrivateOutputRefusal, match="executable schema"):
        _journal(trigger_root, [("suite", trigger_output)], resume=True)

    drift_root = tmp_path / "drift"
    output = drift_root / "suite.json"
    journal_path = drift_root / "reservation.sqlite3"
    journal = _journal(drift_root, [("suite", output)])
    try:
        journal_path.unlink()
        journal_path.write_bytes(b"replacement")
        journal_path.chmod(0o600)
        with pytest.raises(PrivateOutputRefusal, match="journal identity drifted"):
            journal["suite"].commit({"schema_version": "suite/v1"})
    finally:
        journal.close()


@pytest.mark.parametrize("fault", ["after_truncate", "mid_write", "after_fsync"])
def test_commit_prepared_crash_reconciles_exact_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    output = tmp_path / "suite.json"
    payload = {
        "schema_version": "suite/v1",
        "receipt_sha256": "b" * 64,
        "rows": list(range(32)),
    }
    journal = _journal(tmp_path, [("suite", output)])
    if fault in {"after_truncate", "mid_write"}:
        original = private_output._write_all

        def interrupted(descriptor: int, raw: bytes) -> None:
            if fault == "mid_write":
                original(descriptor, raw[: max(1, len(raw) // 3)])
            raise RuntimeError("simulated crash")

        monkeypatch.setattr(private_output, "_write_all", interrupted)
    else:
        original_transition = journal._transition

        def interrupted_transition(
            role: str, *, expected: str, target: str, effect_verifier
        ) -> None:
            if expected == "COMMIT_PREPARED" and target == "COMMITTED":
                raise RuntimeError("simulated crash")
            original_transition(
                role,
                expected=expected,
                target=target,
                effect_verifier=effect_verifier,
            )

        monkeypatch.setattr(journal, "_transition", interrupted_transition)
    try:
        with pytest.raises(RuntimeError, match="simulated crash"):
            journal["suite"].commit(payload)
        assert journal["suite"].state == "COMMIT_PREPARED"
    finally:
        journal.close()
    monkeypatch.undo()

    with _journal(
        tmp_path, [("suite", output)], resume=True
    ) as resumed:
        assert resumed["suite"].state == "COMMIT_PREPARED"
        assert resumed["suite"].prepared_value() == payload
        assert resumed["suite"].state == "COMMIT_PREPARED"
        assert resumed["suite"].committed_value() == payload
        assert resumed["suite"].state == "COMMITTED"


def test_prepared_unexpected_bytes_and_divergent_recommit_refuse(
    tmp_path: Path,
) -> None:
    output = tmp_path / "suite.json"
    journal = _journal(tmp_path, [("suite", output)])
    payload = {"schema_version": "suite/v1", "value": "prepared"}
    raw = private_output._json_payload(payload)
    digest = hashlib.sha256(raw).hexdigest()
    journal._prepare_commit("suite", raw, digest)
    descriptor = journal["suite"]._fd
    os.ftruncate(descriptor, 0)
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.write(descriptor, b"foreign-not-a-prefix")
    os.fsync(descriptor)
    journal.close()
    with _journal(tmp_path, [("suite", output)], resume=True) as reopened:
        with pytest.raises(PrivateOutputRefusal, match="unexpected byte"):
            reopened["suite"].prepared_value()

    committed_root = tmp_path / "committed"
    committed_output = committed_root / "suite.json"
    with _journal(
        committed_root, [("suite", committed_output)]
    ) as owner:
        owner["suite"].commit(payload)
    with _journal(
        committed_root, [("suite", committed_output)], resume=True
    ) as resumed:
        assert resumed["suite"].commit(payload) == hashlib.sha256(
            private_output._json_payload(payload)
        ).hexdigest()
        with pytest.raises(PrivateOutputRefusal, match="recommit differs"):
            resumed["suite"].commit(
                {"schema_version": "suite/v1", "value": "different"}
            )


def test_resume_identity_schema_permissions_and_audit_ledger(
    tmp_path: Path,
) -> None:
    output = tmp_path / "suite.json"
    with _journal(tmp_path, [("suite", output)]) as journal:
        receipt = _resume_prefix()
        first = journal.record_resume_audit(receipt)
        assert journal.record_resume_audit(receipt) == first
        malformed_unsigned = {
            "schema_version": private_output.RESUME_PREFIX_SCHEMA,
            "value": 1,
        }
        with pytest.raises(PrivateOutputRefusal, match="semantic binding"):
            journal.record_resume_audit(
                {
                    **malformed_unsigned,
                    "resume_prefix_sha256": private_output.canonical_sha256(
                        malformed_unsigned
                    ),
                }
            )
        with pytest.raises(PrivateOutputRefusal, match="semantic binding"):
            journal.record_resume_audit(_resume_prefix("foreign-run"))
    connection = sqlite3.connect(tmp_path / "reservation.sqlite3")
    assert connection.execute("SELECT COUNT(*) FROM resume_audits").fetchone() == (
        1,
    )
    connection.close()

    with pytest.raises(PrivateOutputRefusal, match="identity binding"):
        _journal(
            tmp_path,
            [("different-role", output)],
            resume=True,
        )
    os.chmod(tmp_path / "reservation.sqlite3", 0o644)
    with pytest.raises(PrivateOutputRefusal, match="not private|identity drifted"):
        _journal(tmp_path, [("suite", output)], resume=True)


def test_symlink_parent_refuses_without_mutating_its_target(tmp_path: Path) -> None:
    victim = tmp_path / "victim"
    victim.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(victim, target_is_directory=True)
    with pytest.raises(PrivateOutputRefusal, match="symlink"):
        private_output.canonical_output_path(link / "created" / "suite.json")
    assert not (victim / "created").exists()


def test_output_parent_rename_refuses_false_canonical_commit(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir(mode=0o700)
    journal_root = tmp_path / "journal"
    output = output_root / "suite.json"
    journal = private_output.reserve_private_outputs(
        [("suite", output)],
        run_id="run",
        journal_path=journal_root / "reservation.sqlite3",
    )
    moved = tmp_path / "output-moved"
    output_root.rename(moved)
    output_root.mkdir(mode=0o700)
    try:
        with pytest.raises(PrivateOutputRefusal, match="parent.*identity"):
            journal["suite"].commit({"schema_version": "suite/v1"})
        assert journal["suite"].state == "RESERVED"
        assert not output.exists()
        assert (moved / "suite.json").exists()
    finally:
        journal.close()


def test_intermediate_parent_symlink_swap_refuses_even_same_target(
    tmp_path: Path,
) -> None:
    ancestor = tmp_path / "ancestor"
    output_root = ancestor / "output"
    output_root.mkdir(parents=True, mode=0o700)
    output = output_root / "suite.json"
    journal = private_output.reserve_private_outputs(
        [("suite", output)],
        run_id="run",
        journal_path=tmp_path / "journal" / "reservation.sqlite3",
    )
    moved = tmp_path / "ancestor-moved"
    ancestor.rename(moved)
    ancestor.symlink_to(moved, target_is_directory=True)
    try:
        with pytest.raises(PrivateOutputRefusal, match="parent.*unavailable"):
            journal["suite"].commit({"schema_version": "suite/v1"})
        assert journal["suite"].state == "RESERVED"
    finally:
        journal.close()


def test_leaf_replacement_before_state_commit_rolls_back_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "suite.json"
    journal = _journal(tmp_path, [("suite", output)])
    original = journal._transition
    aside = tmp_path / "suite-original.json"

    def replace_then_transition(*args, **kwargs):
        output.rename(aside)
        output.write_bytes(b"foreign\n")
        output.chmod(0o600)
        return original(*args, **kwargs)

    monkeypatch.setattr(journal, "_transition", replace_then_transition)
    try:
        with pytest.raises(PrivateOutputRefusal, match="ownership drifted"):
            journal["suite"].commit({"schema_version": "suite/v1"})
        assert journal["suite"].state == "COMMIT_PREPARED"
        assert output.read_bytes() == b"foreign\n"
    finally:
        journal.close()


def test_leaf_replacement_during_final_parent_sync_never_returns_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "suite.json"
    journal = _journal(tmp_path, [("suite", output)])
    original_fsync_parent = private_output._fsync_parent
    aside = tmp_path / "suite-durable-inode.json"
    swapped = False

    def swap_after_fsync(path: Path, *, parent_fd=None) -> None:
        nonlocal swapped
        original_fsync_parent(path, parent_fd=parent_fd)
        if (
            not swapped
            and Path(path) == output
            and journal["suite"].state == "COMMITTED"
        ):
            output.rename(aside)
            output.write_bytes(b"foreign\n")
            output.chmod(0o600)
            swapped = True

    monkeypatch.setattr(private_output, "_fsync_parent", swap_after_fsync)
    try:
        with pytest.raises(PrivateOutputRefusal, match="ownership drifted"):
            journal["suite"].commit({"schema_version": "suite/v1"})
        assert swapped is True
        assert output.read_bytes() == b"foreign\n"
    finally:
        journal.close()


def test_journal_parent_rename_during_sqlite_connect_refuses_split_brain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "outputs"
    output_root.mkdir(mode=0o700)
    journal_root = tmp_path / "journal"
    moved = tmp_path / "journal-moved"
    journal_path = journal_root / "reservation.sqlite3"
    original_connect = sqlite3.connect
    swapped = False

    def swapping_connect(database, *args, **kwargs):
        nonlocal swapped
        if not swapped and str(database).startswith(journal_path.as_uri()):
            journal_root.rename(moved)
            journal_root.mkdir(mode=0o700)
            swapped = True
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(private_output.sqlite3, "connect", swapping_connect)
    with pytest.raises(PrivateOutputRefusal, match="parent identity"):
        private_output.reserve_private_outputs(
            [("suite", output_root / "suite.json")],
            run_id="run",
            journal_path=journal_path,
        )
    assert swapped is True
    assert (moved / "reservation.sqlite3.lock").exists()


def test_postcommit_sync_failure_is_retried_before_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "suite.json"
    payload = {"schema_version": "suite/v1", "value": "durable"}
    journal = _journal(tmp_path, [("suite", output)])
    original = journal._sync_journal
    failed = False

    def fail_once() -> None:
        nonlocal failed
        if not failed and journal["suite"].state == "COMMITTED":
            failed = True
            raise OSError("simulated final sync failure")
        original()

    monkeypatch.setattr(journal, "_sync_journal", fail_once)
    with pytest.raises(OSError, match="final sync failure"):
        journal["suite"].commit(payload)
    assert journal["suite"].state == "COMMITTED"
    monkeypatch.setattr(journal, "_sync_journal", original)
    assert journal["suite"].commit(payload) == hashlib.sha256(
        private_output._json_payload(payload)
    ).hexdigest()
    journal.close()


def test_close_failure_is_retry_safe_and_keeps_the_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = _journal(
        tmp_path,
        [("first", tmp_path / "first.json"), ("second", tmp_path / "second.json")],
    )
    failed_fd = journal["first"]._fd
    second_fd = journal["second"]._fd
    original_close = os.close
    failed = False

    def fail_once(descriptor: int) -> None:
        nonlocal failed
        if descriptor == failed_fd and not failed:
            failed = True
            raise OSError("simulated close failure")
        original_close(descriptor)

    monkeypatch.setattr(private_output.os, "close", fail_once)
    with pytest.raises(OSError, match="close failure"):
        journal.close()
    assert journal.closed is False
    os.fstat(failed_fd)
    with pytest.raises(OSError):
        os.fstat(second_fd)
    journal.close()
    assert journal.closed is True
    with pytest.raises(OSError):
        os.fstat(failed_fd)


@pytest.mark.parametrize(
    ("fault", "returncodes"),
    [
        ("after_prepare", {74}),
        ("mid_write", {75}),
        ("before_transition", {76}),
        ("after_committed", {77}),
        ("wal_unlink", {78, 79}),
    ],
)
def test_abrupt_process_exit_recovers_exact_prepared_payload(
    tmp_path: Path, fault: str, returncodes: set[int]
) -> None:
    output = tmp_path / "suite.json"
    journal_path = tmp_path / "reservation.sqlite3"
    payload = {
        "schema_version": "suite/v1",
        "receipt_sha256": "d" * 64,
        "rows": list(range(64)),
    }
    script = r'''
import os
from pathlib import Path
import sys
import prom_search_hswm.prom9_f1_r8_private_output as module

output = Path(sys.argv[1])
journal_path = Path(sys.argv[2])
fault = sys.argv[3]
payload = {"schema_version":"suite/v1","receipt_sha256":"d"*64,"rows":list(range(64))}
journal = module.reserve_private_outputs(
    [("suite", output)], run_id="run", journal_path=journal_path
)
if fault == "after_prepare":
    original_sync = journal._sync_journal
    def crash_after_prepare():
        if journal["suite"].state == "COMMIT_PREPARED":
            os._exit(74)
        original_sync()
    journal._sync_journal = crash_after_prepare
elif fault == "mid_write":
    original_write = module._write_all
    def crash_mid_write(descriptor, raw):
        original_write(descriptor, raw[:max(1, len(raw)//3)])
        os.fsync(descriptor)
        os._exit(75)
    module._write_all = crash_mid_write
elif fault == "before_transition":
    def crash_before_transition(*_args, **_kwargs):
        os._exit(76)
    journal._transition = crash_before_transition
else:
    original_sync = journal._sync_journal
    def crash_after_committed():
        if journal["suite"].state != "COMMITTED":
            original_sync()
            return
        if fault == "wal_unlink":
            wal = Path(f"{journal.path}-wal")
            if wal.exists():
                wal.unlink()
                os.fsync(journal._journal_parent_fd)
            try:
                original_sync()
            except BaseException:
                os._exit(79)
            os._exit(78)
        os._exit(77)
    journal._sync_journal = crash_after_committed
journal["suite"].commit(payload)
raise SystemExit(99)
'''
    completed = subprocess.run(
        [sys.executable, "-c", script, str(output), str(journal_path), fault],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    )
    assert completed.returncode in returncodes
    with _journal(tmp_path, [("suite", output)], resume=True) as resumed:
        assert resumed["suite"].state in {"COMMIT_PREPARED", "COMMITTED"}
        assert resumed["suite"].prepared_value() == payload
        assert resumed["suite"].committed_value() == payload
        assert resumed["suite"].state == "COMMITTED"
