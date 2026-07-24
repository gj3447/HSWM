from __future__ import annotations

import json
import subprocess
import sys


def test_refreeze_refuses_non_abort_receipt_before_tokenizer_load(tmp_path):
    prior = tmp_path / "prior.json"
    abort = tmp_path / "abort.json"
    prior.write_text(json.dumps({"model": {"max_output_tokens": 256}}))
    abort.write_text(json.dumps({
        "disposition": "NOT_AN_ABORT",
        "measurement_evidence_created": False,
        "physical_model_calls_started": 1,
    }))
    result = subprocess.run(
        [
            sys.executable,
            "p1v2_l0_refreeze.py",
            "--prior-budget", str(prior),
            "--abort-receipt", str(abort),
            "--public-manifest", "missing",
            "--sealed-gold", "missing",
            "--articles", "missing",
            "--deployment-receipt", "missing",
            "--generation-receipt", "missing",
            "--tokenizer-snapshot", "missing",
            "--new-max-output-tokens", "512",
            "--budget-output", str(tmp_path / "budget.json"),
            "--refreeze-output", str(tmp_path / "refreeze.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "does not authorize" in result.stderr
