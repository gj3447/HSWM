from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from hswm.experiments import g1_opaque_evaluator_process as evaluator
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


def _reveal(tmp_path: Path) -> tuple[Path, dict]:
    entries = []
    for ordinal in (1, 2):
        entries.append({
            "correct_action_code": f"act_{ordinal:08x}",
            "episode_uid": f"episode:opaque-{ordinal:08x}",
            "leakage_canary": f"canary_{ordinal:02d}",
            "ordinal": ordinal,
            "salt": f"salt_value_{ordinal:02d}",
        })
    root = canonical_sha256({"episode_commitments": [canonical_sha256(e) for e in entries]})
    reveal = {
        "episodes": entries,
        "protocol_canonical_sha256": "a" * 64,
        "reveal_commitment_root": root,
        "schema_version": evaluator.REVEAL_SCHEMA,
        "study_uid": "sym:ExploratoryStudy:test",
    }
    path = tmp_path / "reveal.json"
    path.write_bytes(canonical_json_bytes(reveal))
    return path, reveal


def test_evaluator_answers_once_per_episode_with_a_salt_keyed_receipt(tmp_path: Path) -> None:
    reveal_path, reveal = _reveal(tmp_path)
    ledger = tmp_path / "evaluator" / "ledger.jsonl"
    endpoint = evaluator.default_endpoint(reveal_path, ledger)
    feedback = endpoint.call(
        study_uid=reveal["study_uid"], protocol_sha256="a" * 64,
        episode_uid="episode:opaque-00000001", trajectory_sha256="b" * 64, action_code="act_00000001",
    )
    assert feedback["choice_was_correct"] is True
    assert feedback["evaluator_ledger_sequence"] == 1
    assert evaluator.EvaluatorEndpoint.separation(feedback) == "SAME_OS_USER"
    evaluator.verify_feedback(feedback, reveal=reveal)
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    assert len(rows) == 1 and rows[0]["feedback_receipt_sha256"] == feedback["receipt_sha256"]

    with pytest.raises(evaluator.EvaluatorRefusal, match="refused"):
        endpoint.call(
            study_uid=reveal["study_uid"], protocol_sha256="a" * 64,
            episode_uid="episode:opaque-00000001", trajectory_sha256="b" * 64, action_code="act_00000002",
        )
    assert len(ledger.read_bytes().splitlines()) == 1

    wrong = endpoint.call(
        study_uid=reveal["study_uid"], protocol_sha256="a" * 64,
        episode_uid="episode:opaque-00000002", trajectory_sha256="c" * 64, action_code="act_00000001",
    )
    assert wrong["choice_was_correct"] is False
    evaluator.verify_feedback(wrong, reveal=reveal)

    tampered = deepcopy(feedback)
    tampered["choice_was_correct"] = False
    unsigned = dict(tampered)
    unsigned.pop("receipt_sha256")
    tampered["receipt_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(evaluator.EvaluatorRefusal, match="MAC"):
        evaluator.verify_feedback(tampered, reveal=reveal)

    other_reveal = deepcopy(reveal)
    other_reveal["episodes"][0]["salt"] = "salt_value_99"
    with pytest.raises(evaluator.EvaluatorRefusal, match="MAC"):
        evaluator.verify_feedback(feedback, reveal=other_reveal)


def test_evaluator_refuses_foreign_study_and_leaks_nothing_but_the_bit(tmp_path: Path) -> None:
    reveal_path, reveal = _reveal(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    request = {
        "schema_version": evaluator.REQUEST_SCHEMA,
        "study_uid": "sym:ExploratoryStudy:other",
        "protocol_canonical_sha256": "a" * 64,
        "episode_uid": "episode:opaque-00000001",
        "trajectory_sha256": "b" * 64,
        "action_code": "act_00000001",
    }
    completed = subprocess.run(
        [sys.executable, "-m", "hswm.experiments.g1_opaque_evaluator_process", "--reveal", str(reveal_path), "--ledger", str(ledger)],
        input=canonical_json_bytes(request), capture_output=True, check=False, timeout=30,
    )
    assert completed.returncode == 2
    assert b"EvaluatorRefusal" in completed.stderr
    assert not ledger.exists()

    request["study_uid"] = reveal["study_uid"]
    completed = subprocess.run(
        [sys.executable, "-m", "hswm.experiments.g1_opaque_evaluator_process", "--reveal", str(reveal_path), "--ledger", str(ledger)],
        input=canonical_json_bytes(request), capture_output=True, check=False, timeout=30,
    )
    assert completed.returncode == 0
    reply = json.loads(completed.stdout)
    assert "salt" not in completed.stdout.decode() and "canary" not in completed.stdout.decode()
    assert set(reply) == evaluator._FEEDBACK_FIELDS
    assert reply["evaluator_os_uid"] == os.getuid()

    broken = deepcopy(reveal)
    broken["episodes"][1]["salt"] = "changed_salt"
    (tmp_path / "broken.json").write_bytes(canonical_json_bytes(broken))
    with pytest.raises(evaluator.EvaluatorRefusal, match="commitment root"):
        evaluator.load_reveal(tmp_path / "broken.json")
