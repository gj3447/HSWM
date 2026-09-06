"""Engineering fixtures only: real Lean admission and fresh Node recovery.

Build effect-runtime first; set HSWM_D4_LEAN_EXECUTABLE when the pinned build
is outside this checkout. These fixtures are not selected study instances.
"""
from __future__ import annotations

from pathlib import Path
import os
import shutil

import pytest

from hswm.experiments.d4_heldout_task import (
    TaskContract, derive_credit, independently_evaluate, make_disposition,
    make_instance, sealed_train,
)
from hswm.experiments.d4_study_bridge import D4StudyBridgeError, D4StudyProcess
from hswm.selfmod.contracts import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bridge() -> D4StudyProcess:
    node = shutil.which("node")
    lean = Path(os.environ.get("HSWM_D4_LEAN_EXECUTABLE", str(ROOT / "formal/.lake/build/bin/HSWMAdmissionKernelCli")))
    script = ROOT / "src/hswm/effect-runtime/dist/canonical-atom-v2-d4-study-process.js"
    if not node or not lean.is_file() or not script.is_file():
        pytest.skip("build the D4 Node process and Lean admission CLI for process integration")
    return D4StudyProcess(Path(node).resolve(), script, lean.resolve())


def _payloads(theta: int):
    contract = TaskContract("1" * 64, "2" * 64)
    instance = make_instance(seed=b"fixture-no-study-selection-v1...."[:32],
                             occurrence_uid=f"fixture-d4-interop-{theta}", split="TRAIN",
                             selector_bit=0, candidate_order=0)
    seal = sealed_train(instance, contract, canonical_json_bytes({"action_id": instance.action_codes[0]}))
    outcome = independently_evaluate(instance=instance, contract=contract, seal=seal, theta=theta)
    credit = derive_credit(contract=contract, instance=instance, seal=seal, outcome=outcome)
    return contract, instance, {"task": contract.payload(), "instance": instance.payload(contract),
                              "trajectory": seal, "outcome": outcome, "credit": credit,
                              "disposition": make_disposition(contract=contract, credit=credit)}


@pytest.mark.parametrize("theta", [0, 1])
def test_real_lean_commit_and_fresh_node_recovery_bind_the_compiler(
    bridge: D4StudyProcess, tmp_path: Path, theta: int,
) -> None:
    contract, instance, payloads = _payloads(theta)
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    trust = root / "trust-snapshot.json"
    receipt = bridge.commit(root=root, trust=trust, occurrence_uid=instance.occurrence_uid, payloads=payloads)
    assert "compiledDispositionBase64Url" not in receipt
    recovered = bridge.recover(root=root, trust=trust, occurrence_uid=instance.occurrence_uid,
                               contract=contract, expected_post_state_sha256=receipt["postStateSha256"])
    assert recovered.compiled["latent_bit"] == theta
    assert recovered.receipt["head"] == receipt["head"]
    assert set(recovered.compiled) == {"compiler_source_sha256", "latent_bit", "task_contract_sha256"}
    with pytest.raises(D4StudyBridgeError):
        bridge.recover(root=root, trust=trust, occurrence_uid="fixture-wrong-occurrence",
                       contract=contract, expected_post_state_sha256=receipt["postStateSha256"])
    with pytest.raises(D4StudyBridgeError):
        bridge.commit(root=root, trust=trust, occurrence_uid=instance.occurrence_uid, payloads=payloads)


def test_forged_training_action_is_rejected_before_any_trust_or_commit(
    bridge: D4StudyProcess, tmp_path: Path,
) -> None:
    _, instance, payloads = _payloads(1)
    payloads["trajectory"] = {**payloads["trajectory"], "action_id": instance.action_codes[1]}
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    with pytest.raises(D4StudyBridgeError):
        bridge.commit(root=root, trust=root / "trust-snapshot.json",
                      occurrence_uid=instance.occurrence_uid, payloads=payloads)
    assert list(root.iterdir()) == []
