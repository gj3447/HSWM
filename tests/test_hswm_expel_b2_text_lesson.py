from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from hswm.experiments.expel_b2_text_lesson import (
    ARM_ID, CLAIM_BOUNDARY, LESSON_WRAPPER_PREFIX_UTF8, LessonStore,
    ResourceLedger, ExpelB2TextLessonError, build_action_messages, render_lesson,
)


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def test_successful_sealed_terminal_creates_immutable_arm_private_revision(tmp_path: Path) -> None:
    root = tmp_path / "b2"; root.mkdir()
    store = LessonStore(root)
    ledger = store.admit_successful_terminal(
        episode_uid="train:001", terminal_seal_sha256=_digest("terminal"),
        trajectory_sha256=_digest("trajectory"), terminal_success=True,
        reflection_rule_utf8="Clean an object before placing it.",
        resource=ResourceLedger(), reflection_input_tokens=11, reflection_output_tokens=7,
    )
    assert ledger.canonical()["reflection_calls"] == 1
    assert len(store.revisions) == 1
    assert (root / "revision-01.json").is_file()
    lesson = render_lesson(store.revisions)
    assert lesson == LESSON_WRAPPER_PREFIX_UTF8 + "1. Clean an object before placing it.\nEND B2 LESSONS\n"
    messages = build_action_messages(lesson_utf8=lesson, episode_uid="heldout:001", step_index=0, history=[], observation="room")
    assert [item["role"] for item in messages] == ["system", "system", "user"]
    assert ARM_ID not in messages[2]["content"]


def test_failed_terminal_and_heldout_freeze_forbid_updates(tmp_path: Path) -> None:
    root = tmp_path / "b2"; root.mkdir(); store = LessonStore(root)
    with pytest.raises(ExpelB2TextLessonError, match="successful"):
        store.admit_successful_terminal(
            episode_uid="train:001", terminal_seal_sha256=_digest("terminal"), trajectory_sha256=_digest("traj"),
            terminal_success=False, reflection_rule_utf8="Never written.", resource=ResourceLedger(),
            reflection_input_tokens=1, reflection_output_tokens=1,
        )
    store.admit_successful_terminal(
        episode_uid="train:001", terminal_seal_sha256=_digest("terminal"), trajectory_sha256=_digest("traj"),
        terminal_success=True, reflection_rule_utf8="Inspect before acting.", resource=ResourceLedger(),
        reflection_input_tokens=1, reflection_output_tokens=1,
    )
    frozen = store.freeze_for_heldout()
    assert len(frozen) == 64 and (root / "heldout-freeze.json").is_file()
    assert store.frozen_lesson_utf8 == LESSON_WRAPPER_PREFIX_UTF8 + "1. Inspect before acting.\nEND B2 LESSONS\n"
    assert (root / "arm-private-genesis.json").is_file()
    with pytest.raises(ExpelB2TextLessonError, match="freeze"):
        store.admit_successful_terminal(
            episode_uid="heldout:001", terminal_seal_sha256=_digest("later"), trajectory_sha256=_digest("latertraj"),
            terminal_success=True, reflection_rule_utf8="Forbidden update.", resource=ResourceLedger(),
            reflection_input_tokens=1, reflection_output_tokens=1,
        )


def test_deduplication_is_deterministic_and_resource_accounting_is_exact(tmp_path: Path) -> None:
    root = tmp_path / "b2"; root.mkdir(); store = LessonStore(root)
    ledger = ResourceLedger().record_completed_pair(kind="action", input_tokens=5, output_tokens=2)
    ledger = store.admit_successful_terminal(
        episode_uid="train:001", terminal_seal_sha256=_digest("a"), trajectory_sha256=_digest("b"),
        terminal_success=True, reflection_rule_utf8="Inspect before acting.", resource=ledger,
        reflection_input_tokens=3, reflection_output_tokens=4,
    )
    ledger = store.admit_successful_terminal(
        episode_uid="train:002", terminal_seal_sha256=_digest("c"), trajectory_sha256=_digest("d"),
        terminal_success=True, reflection_rule_utf8="Inspect before acting.", resource=ledger,
        reflection_input_tokens=6, reflection_output_tokens=8,
    )
    assert len(store.revisions) == 1
    assert ledger.canonical() == {
        "schema_version": "hswm-expel-b2-text-lesson-resource-ledger/v1", "arm_id": ARM_ID,
        "tokenize_calls": 3, "completion_calls": 3, "input_tokens": 14, "output_tokens": 14,
        "reflection_calls": 2, "ledger_sha256": ledger.canonical()["ledger_sha256"],
    }


def test_rejects_unwrapped_lesson_and_keeps_noncanonical_claim_boundary(tmp_path: Path) -> None:
    with pytest.raises(ExpelB2TextLessonError, match="wrapper"):
        build_action_messages(lesson_utf8="rules", episode_uid="heldout:001", step_index=0, history=[], observation="room")
    assert "NOT_HSWM_CANONICAL" in CLAIM_BOUNDARY


def test_refuses_a_nonfresh_root_to_keep_arm_private_state_nonresumable(tmp_path: Path) -> None:
    root = tmp_path / "b2"; root.mkdir(); (root / "foreign.json").write_text("{}")
    with pytest.raises(ExpelB2TextLessonError, match="fresh arm-private"):
        LessonStore(root)


def test_invalid_resource_and_duplicate_terminal_leave_revision_state_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "b2"; root.mkdir(); store = LessonStore(root)
    before = sorted(path.name for path in root.iterdir())
    with pytest.raises(ExpelB2TextLessonError, match="token counts"):
        store.admit_successful_terminal(
            episode_uid="train:001", terminal_seal_sha256=_digest("a"), trajectory_sha256=_digest("b"),
            terminal_success=True, reflection_rule_utf8="Inspect before acting.", resource=ResourceLedger(),
            reflection_input_tokens=-1, reflection_output_tokens=1,
        )
    assert store.revisions == () and sorted(path.name for path in root.iterdir()) == before
    store.admit_successful_terminal(
        episode_uid="train:001", terminal_seal_sha256=_digest("a"), trajectory_sha256=_digest("b"),
        terminal_success=True, reflection_rule_utf8="Inspect before acting.", resource=ResourceLedger(),
        reflection_input_tokens=1, reflection_output_tokens=1,
    )
    with pytest.raises(ExpelB2TextLessonError, match="processed once"):
        store.admit_successful_terminal(
            episode_uid="train:001", terminal_seal_sha256=_digest("a"), trajectory_sha256=_digest("c"),
            terminal_success=True, reflection_rule_utf8="Different rule cannot reuse terminal.", resource=ResourceLedger(),
            reflection_input_tokens=1, reflection_output_tokens=1,
        )


def test_ledger_represents_preflight_only_and_failed_completion_accounting() -> None:
    ledger = ResourceLedger().record_tokenize(input_tokens=5)
    assert ledger.canonical()["tokenize_calls"] == 1
    assert ledger.canonical()["completion_calls"] == 0
    ledger = ledger.record_completion(kind="action", output_tokens=0)
    assert ledger.canonical()["tokenize_calls"] == ledger.canonical()["completion_calls"] == 1


@pytest.mark.parametrize("counters", [
    {"completion_calls": -1}, {"tokenize_calls": True},
    {"input_tokens": 0.5}, {"reflection_calls": 1},
])
def test_ledger_rejects_invalid_aggregate_construction(counters: dict) -> None:
    with pytest.raises(ExpelB2TextLessonError):
        ResourceLedger(**counters)


def test_rendered_byte_cap_is_checked_before_admission(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    for index in range(9):
        store.admit_successful_terminal(
            episode_uid=f"train:{index}", terminal_seal_sha256=_digest(f"seal:{index}"),
            trajectory_sha256=_digest(f"trace:{index}"), terminal_success=True,
            reflection_rule_utf8=chr(ord("A") + index) * 512,
            resource=ResourceLedger(), reflection_input_tokens=1, reflection_output_tokens=1,
        )
    with pytest.raises(ExpelB2TextLessonError, match="byte cap"):
        store.admit_successful_terminal(
            episode_uid="train:9", terminal_seal_sha256=_digest("seal:9"),
            trajectory_sha256=_digest("trace:9"), terminal_success=True,
            reflection_rule_utf8="Z" * 512, resource=ResourceLedger(),
            reflection_input_tokens=1, reflection_output_tokens=1,
        )
    assert len(store.revisions) == 9
    assert not (tmp_path / "revision-10.json").exists()
    assert store.freeze_for_heldout()
