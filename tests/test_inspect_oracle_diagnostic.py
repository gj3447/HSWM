from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_DIR = ROOT / "_research" / "inspect_comparison_v1"
sys.path.insert(0, str(DIAGNOSTIC_DIR))
spec = importlib.util.spec_from_file_location(
    "oracle_single_diagnostic", DIAGNOSTIC_DIR / "oracle_single_diagnostic.py"
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def prepared_fixture(tmp_path: Path) -> Path:
    destination = tmp_path / "fixture"
    subprocess.run(
        ["node", str(DIAGNOSTIC_DIR / "prepare_oracle_diagnostic.mts"), str(destination)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return destination


def bridge_result(answer: str | None, *, valid: bool = True) -> dict[str, object]:
    return {
        "valid": valid,
        "answer": answer,
        "error_kind": None if valid else "MODEL_FORMAT",
        "request_sha256": "a" * 64,
        "response_sha256": "b" * 64,
        "usage": {"total_tokens": 3},
        "latency_ms": 2,
        "model_calls": 1,
        "model_calls_upper_bound": 1,
    }


def fake_log(cases, answer_for):
    return SimpleNamespace(
        samples=[
            SimpleNamespace(
                id=case.id,
                output=SimpleNamespace(metadata={"hswm_bridge": bridge_result(answer_for(case))}),
            )
            for case in cases
        ],
        location=Path("fake.eval"),
    )


def test_generator_fixture_builds_all_families_and_pins_bytes(tmp_path):
    plan = module.build(prepared_fixture(tmp_path))
    assert plan["planned_attempts"] == 64
    assert [len(item["selected"]) for item in plan["families"]] == [8, 8, 8, 8]
    assert plan["screening"]["noEfficacyOrPopulationClaim"] is True


def test_hash_drift_in_later_family_rejects_before_callback(tmp_path, monkeypatch):
    fixture = prepared_fixture(tmp_path)
    target = fixture / "family-3" / "oracle.txt"
    target.write_text(target.read_text(encoding="utf-8") + "drift", encoding="utf-8")
    called = False

    def callback(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not call a model")

    monkeypatch.setattr(module, "run_live", callback)
    with pytest.raises(ValueError, match="hash"):
        module.build(fixture)
    assert called is False


def test_shared_loader_receives_hashed_train_snapshot_not_a_second_file_read(tmp_path, monkeypatch):
    fixture = prepared_fixture(tmp_path)
    original_loader = module.load_live_jsonl

    def mutate_after_hash(path, split):
        # family-2 has already been read and hashed before this shared-loader call.
        if "family-2" in str(path):
            train = fixture / "family-2" / "train.jsonl"
            train.write_text("corrupted after hash\n", encoding="utf-8")
        return original_loader(path, split)

    monkeypatch.setattr(module, "load_live_jsonl", mutate_after_hash)
    plan = module.build(fixture)
    assert len(plan["families"][2]["selected"]) == 8


def test_full_64_call_screen_separates_environment_and_frozen_rule(tmp_path, monkeypatch):
    plan = module.build(prepared_fixture(tmp_path))

    def callback(cases, baseline, oracle, execution, log_dir, **kwargs):
        baseline_log = fake_log(
            cases,
            lambda case: str(int(case.target) ^ case.input["fields"]["context"]["pel"]),
        )
        oracle_log = fake_log(cases, lambda case: case.target)
        return baseline_log, oracle_log

    monkeypatch.setattr(module, "run_live", callback)
    summary = module.run(plan, tmp_path / "run", "http://127.0.0.1:8001", "fixture-model")
    assert summary["all_valid"] == 64
    assert summary["oracle_environment_correct"] == 32
    assert summary["baseline_frozen_rule_consistent"] == 32
    assert summary["baseline_environment_correct"] == 16
    assert summary["screen_passed"] is True
    assert [item["oracle"]["correct"] for item in summary["results"]] == [8, 8, 8, 8]


def test_invalid_bridge_rows_are_retained_and_fail_the_all_valid_screen(tmp_path, monkeypatch):
    plan = module.build(prepared_fixture(tmp_path))

    def callback(cases, baseline, oracle, execution, log_dir, **kwargs):
        baseline_log = fake_log(cases, lambda case: case.target)
        oracle_log = fake_log(cases, lambda case: case.target)
        oracle_log.samples[0].output.metadata["hswm_bridge"] = bridge_result(None, valid=False)
        oracle_log.samples[0].output.metadata["hswm_bridge"]["model_calls"] = None
        oracle_log.samples[0].output.metadata["hswm_bridge"]["latency_ms"] = None
        return baseline_log, oracle_log

    monkeypatch.setattr(module, "run_live", callback)
    summary = module.run(plan, tmp_path / "invalid", "http://127.0.0.1:8001", "fixture-model")
    assert summary["all_valid"] == 60
    assert summary["screen_passed"] is False
    first_oracle = summary["results"][0]["oracle"]
    assert first_oracle["unknown_call_attempts"] == 1
    assert first_oracle["rows"][0]["error_kind"] == "MODEL_FORMAT"


@pytest.mark.parametrize("bad_samples", ["duplicate", "foreign", "missing"])
def test_malformed_inspect_logs_are_rejected(tmp_path, bad_samples):
    plan = module.build(prepared_fixture(tmp_path))
    cases = plan["families"][0]["selected"]
    examples = [module.LiveExample(case["id"], "train", case["input"], case["target"]) for case in cases]
    log = fake_log(examples, lambda case: case.target)
    if bad_samples == "duplicate":
        log.samples[-1].id = log.samples[0].id
    elif bad_samples == "foreign":
        log.samples[-1].id = "foreign-id"
    else:
        log.samples.pop()
    with pytest.raises(RuntimeError):
        module.summarize(log, fake_log(examples, lambda case: case.target), cases)


def test_failed_family_keeps_completed_receipt_and_marks_incomplete(tmp_path, monkeypatch):
    plan = module.build(prepared_fixture(tmp_path))
    calls = 0

    def callback(cases, baseline, oracle, execution, log_dir, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("loopback failure")
        return fake_log(cases, lambda case: case.target), fake_log(cases, lambda case: case.target)

    monkeypatch.setattr(module, "run_live", callback)
    output = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="loopback"):
        module.run(plan, output, "http://127.0.0.1:8001", "fixture-model")
    assert (output / "family-0.json").is_file()
    failed = json.loads((output / "failed.json").read_text(encoding="utf-8"))
    assert failed["status"] == "INCOMPLETE"
    assert failed["completed_family_attempts"] == 16
    assert failed["current_family_attempts"] == "UNKNOWN_UP_TO_16"
    assert failed["remaining_unattempted"] == 32
