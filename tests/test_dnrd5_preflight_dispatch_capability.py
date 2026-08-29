"""No-network adversarial tests for one DNRD-5 block dispatch capability."""

from __future__ import annotations

from pathlib import Path
import threading

import pytest
import _research.dnrd5.preflight_dispatch_capability as capability_module

from _research.dnrd5.canonical_json import canonical_bytes
from _research.dnrd5.preflight_dispatch_capability import (
    BLOCK_CRASH,
    BLOCK_DEFECT,
    BLOCK_SUCCESS,
    DispatchSlot,
    PreflightDispatchCapability,
    PreflightDispatchRefusal,
    read_dispatch_capability_ledger,
    validate_completed_dispatch_capability,
)


def _evidence() -> bytes:
    return canonical_bytes({"root": "fixture-evidence", "version": 1})


def _slots() -> tuple[DispatchSlot, ...]:
    classes = (
        "PRE_OUTCOME_TRAJECTORY",
        *("REVISION_PROPOSAL" for _ in range(4)),
        *("FRESH_PROBE" for _ in range(4)),
    )
    return tuple(DispatchSlot(f"opaque-call-{ordinal:02d}", call_class, f"{ordinal:064x}") for ordinal, call_class in enumerate(classes, 1))


def _cap(tmp_path: Path) -> PreflightDispatchCapability:
    return PreflightDispatchCapability.create(
        tmp_path / "capability",
        block_id="DNRD5-BLOCK-0001",
        evidence_root_bytes=_evidence(),
        slots=_slots(),
    )


def test_nine_no_network_transports_are_exactly_accounted_then_closed(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    observed: list[int] = []
    for ordinal, slot in enumerate(_slots(), 1):
        assert cap.dispatch(slot, lambda ordinal=ordinal: observed.append(ordinal) or ordinal) == ordinal
    assert observed == list(range(1, 10))
    rows = read_dispatch_capability_ledger(tmp_path / "capability")
    assert [row["record_type"] for row in rows] == [
        "START", *("CALL_START", "CALL_TERMINAL") * 9, "TERMINAL"
    ]
    assert rows[0]["terminal"] == "BLOCK_START_DURABLE_BEFORE_ANY_PROVIDER_DISPATCH"
    assert rows[-1]["terminal"] == BLOCK_SUCCESS
    assert rows[-1]["consumed_slots"] == 9
    with pytest.raises(PreflightDispatchRefusal, match="permanently closed"):
        cap.dispatch(_slots()[0], lambda: pytest.fail("closed capability invoked transport"))


def test_nine_test_double_returns_cannot_qualify_completed_provider_evidence(
    tmp_path: Path,
) -> None:
    cap = _cap(tmp_path)
    for slot in _slots():
        cap.dispatch(slot, lambda: "no-network-test-double")
    with pytest.raises(PreflightDispatchRefusal, match="non-provider"):
        validate_completed_dispatch_capability(tmp_path / "capability")


def test_slot_defect_is_terminal_before_fake_transport_runs(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    observed: list[str] = []
    wrong = DispatchSlot("opaque-call-02", "REVISION_PROPOSAL", f"{2:064x}")
    with pytest.raises(PreflightDispatchRefusal, match="next evidence-bound"):
        cap.dispatch(wrong, lambda: observed.append("network") )
    assert observed == []
    rows = read_dispatch_capability_ledger(tmp_path / "capability")
    assert rows[-1]["terminal"] == BLOCK_DEFECT
    assert rows[-1]["consumed_slots"] == 0
    with pytest.raises(PreflightDispatchRefusal, match="permanently closed"):
        cap.dispatch(_slots()[0], lambda: observed.append("second"))
    assert observed == []


def test_transport_failure_consumes_the_block_without_retry(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    attempts = 0

    def failing_fake() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("fake transport failure")

    with pytest.raises(RuntimeError, match="fake transport failure"):
        cap.dispatch(_slots()[0], failing_fake)
    assert attempts == 1
    rows = read_dispatch_capability_ledger(tmp_path / "capability")
    assert rows[-1]["terminal"] == BLOCK_DEFECT
    assert rows[-1]["defect"] == "POST_CALL_START_FAILURE"
    with pytest.raises(PreflightDispatchRefusal, match="permanently closed"):
        cap.dispatch(_slots()[0], failing_fake)
    assert attempts == 1


def test_result_evidence_property_failure_cannot_resume_same_live_capability(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    attempts: list[str] = []

    class HostileResult:
        @property
        def dispatch_evidence(self) -> object:
            raise OSError("evidence accessor fault")

    with pytest.raises(OSError, match="accessor"):
        cap.dispatch(_slots()[0], lambda: attempts.append("first") or HostileResult())
    with pytest.raises(PreflightDispatchRefusal, match="permanently closed|unmatched"):
        cap.dispatch(_slots()[0], lambda: attempts.append("second"))
    assert attempts == ["first"]


def test_call_terminal_append_failure_cannot_resume_same_live_capability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _cap(tmp_path)
    attempts: list[str] = []
    real_append = capability_module._append

    def fail_call_terminal(path: Path, core: dict[str, object]) -> dict[str, object]:
        if core.get("record_type") == "CALL_TERMINAL":
            raise OSError("injected terminal append failure")
        return real_append(path, core)  # type: ignore[arg-type]

    monkeypatch.setattr(capability_module, "_append", fail_call_terminal)
    with pytest.raises(OSError, match="terminal append"):
        cap.dispatch(_slots()[0], lambda: attempts.append("first") or "fake")
    with pytest.raises(PreflightDispatchRefusal, match="permanently closed|unmatched"):
        cap.dispatch(_slots()[0], lambda: attempts.append("second"))
    assert attempts == ["first"]
    rows = read_dispatch_capability_ledger(tmp_path / "capability")
    assert rows[-1]["terminal"] == BLOCK_DEFECT
    assert rows[-1]["defect"] == "POST_CALL_START_FAILURE"


def test_concurrent_same_slot_has_one_fake_transport_dispatch(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    calls: list[str] = []
    outcomes: list[str] = []

    def invoke() -> None:
        try:
            cap.dispatch(_slots()[0], lambda: calls.append("one"))
            outcomes.append("returned")
        except PreflightDispatchRefusal:
            outcomes.append("refused")

    first = threading.Thread(target=invoke)
    second = threading.Thread(target=invoke)
    first.start(); second.start()
    first.join(timeout=5); second.join(timeout=5)
    assert calls == ["one"]
    assert sorted(outcomes) == ["refused", "returned"]
    rows = read_dispatch_capability_ledger(tmp_path / "capability")
    assert rows[-1]["terminal"] == BLOCK_DEFECT


def test_reopen_of_unterminated_start_terminalizes_as_crash_without_transport(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    root = tmp_path / "capability"
    # This reconstructs the durable state left by a process death immediately
    # after START.  The second process may only close it, never resume it.
    del cap
    reopened = PreflightDispatchCapability(root, _evidence())
    rows = read_dispatch_capability_ledger(root)
    assert rows[-1]["terminal"] == BLOCK_CRASH
    with pytest.raises(PreflightDispatchRefusal, match="permanently closed"):
        reopened.dispatch(_slots()[0], lambda: pytest.fail("crash recovery dispatched"))


def test_evidence_root_binding_and_nine_slot_grammar_are_fail_closed(tmp_path: Path) -> None:
    cap = _cap(tmp_path)
    with pytest.raises(PreflightDispatchRefusal, match="not capability-bound"):
        PreflightDispatchCapability(tmp_path / "capability", canonical_bytes({"root": "other"}))
    with pytest.raises(PreflightDispatchRefusal, match="exactly nine slots"):
        PreflightDispatchCapability.create(
            tmp_path / "bad", block_id="DNRD5-BLOCK-0002", evidence_root_bytes=_evidence(), slots=_slots()[:-1]
        )
    assert read_dispatch_capability_ledger(tmp_path / "capability")[-1]["record_type"] == "START"
    # The first capability remains open; merely inspecting it through a
    # mismatched evidence root cannot consume or reopen it.
    assert cap.block_id == "DNRD5-BLOCK-0001"
