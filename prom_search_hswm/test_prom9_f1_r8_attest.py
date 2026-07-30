from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_r8_attest import AttestationRefusal, verify_attestation


def test_attestation_cli_hashes_exact_file_and_writes_private_receipt(
    tmp_path: Path,
) -> None:
    dependency = tmp_path / "dependency.py"
    dependency.write_bytes(b"print('frozen')\n")
    dependency.chmod(0o600)
    output = tmp_path / "attestation.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "prom_search_hswm.prom9_f1_r8_attest",
            "--kind",
            "dependencies",
            "--observed-at",
            "2026-07-29T00:00:00Z",
            "--file",
            f"runner={dependency}",
            "--value",
            "model_revision=frozen-revision",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(output.read_text(encoding="utf-8"))
    unsigned = dict(receipt)
    declared = unsigned.pop("receipt_sha256")
    assert declared == canonical_sha256(unsigned)
    assert receipt["files"]["runner"]["sha256"] == hashlib.sha256(
        dependency.read_bytes()
    ).hexdigest()
    assert os.stat(output).st_mode & 0o777 == 0o600
    assert verify_attestation(
        receipt,
        kind="dependencies",
        required_files=("runner",),
        required_values=("model_revision",),
        verify_live_files=True,
    ) == receipt["receipt_sha256"]
    dependency.write_bytes(b"print('drifted')\n")
    with pytest.raises(AttestationRefusal, match="differs"):
        verify_attestation(
            receipt,
            kind="dependencies",
            required_files=("runner",),
            required_values=("model_revision",),
            verify_live_files=True,
        )
