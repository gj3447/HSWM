"""Run a fresh P1v4 heldout through the frozen P1v3 measurement kernel.

The P1v3 measurement implementation remains byte-for-byte frozen. This wrapper
translates a P1v4 preregistration into its compatible input, runs the old kernel
against the new sealed cut, and reseals the grounded evidence with truthful
P1v4 provenance before any scientific judge is invoked.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256
from p1v3_calibration_preflight import file_sha256, write_once
from p1v4_replay_judge import P1V3_FROZEN_SCORER_SHA256


PREREG_SCHEMA_VERSION = "hswm-p1v4-preregistration/v1"
EVIDENCE_SCHEMA_VERSION = "hswm-p1v4-policy-heldout-evidence/v1"
COMPAT_PREREG_SCHEMA_VERSION = "hswm-p1v3-preregistration/v1"
CONJECTURE = (
    "The previously successful training-derived typed source-policy mechanism "
    "replicates on the fresh seed-5 R2 conflict cut, improving at least three of "
    "six frozen-model heldout answers versus no memory."
)


class P1V4HeldoutMeasurementError(RuntimeError):
    pass


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise P1V4HeldoutMeasurementError(f"{label} self-hash drifted")
    return declared


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def validate_preregistration(
    prereg: Mapping[str, object], *, here: Path
) -> str:
    if prereg.get("schema_version") != PREREG_SCHEMA_VERSION:
        raise P1V4HeldoutMeasurementError("P1v4 preregistration schema drifted")
    prereg_sha = _verify_self_hash(
        prereg, "preregistration_sha256", "P1v4 preregistration"
    )
    if (
        prereg.get("registration_state") != "SERVER_REGISTERED_FROZEN_UNRUN"
        or prereg.get("registered_before_measurement") is not True
        or prereg.get("prior_outcome_reuse") is not False
        or prereg.get("prior_outcome_artifacts") != []
    ):
        raise P1V4HeldoutMeasurementError("P1v4 registration boundary is invalid")
    judge = prereg.get("judge")
    modules = prereg.get("p1v4_module_sha256")
    if not isinstance(judge, Mapping) or not isinstance(modules, Mapping):
        raise P1V4HeldoutMeasurementError("P1v4 judge bindings are missing")
    expected_modules = {
        "p1v4_heldout_measure.py": file_sha256(here / "p1v4_heldout_measure.py"),
        "p1v4_replay_bundle.py": file_sha256(here / "p1v4_replay_bundle.py"),
        "p1v4_replay_judge.py": file_sha256(here / "p1v4_replay_judge.py"),
    }
    if dict(modules) != expected_modules:
        raise P1V4HeldoutMeasurementError("P1v4 module hash cut drifted")
    if (
        judge.get("script") != "p1v4_replay_judge.py"
        or judge.get("script_sha256") != expected_modules["p1v4_replay_judge.py"]
        or judge.get("frozen_scorer_contract_sha256")
        != P1V3_FROZEN_SCORER_SHA256
        or judge.get("server_replay_required") is not True
    ):
        raise P1V4HeldoutMeasurementError("P1v4 replay judge binding drifted")
    return prereg_sha


def compatible_p1v3_preregistration(
    prereg: Mapping[str, object]
) -> dict[str, object]:
    """Build the exact schema accepted by the frozen measurement kernel."""

    compat = deepcopy(dict(prereg))
    compat["schema_version"] = COMPAT_PREREG_SCHEMA_VERSION
    compat.pop("preregistration_sha256", None)
    compat["preregistration_sha256"] = canonical_sha256(compat)
    return compat


def build_p1v4_evidence(
    *,
    inner_evidence: Mapping[str, object],
    preregistration_sha256: str,
    wrapper_command: Sequence[str],
    wrapper_sha256: str,
) -> dict[str, object]:
    inner_sha = _verify_self_hash(
        inner_evidence, "evidence_sha256", "compatibility evidence"
    )
    if any(key.casefold() == "verdict" for key in _recursive_keys(inner_evidence)):
        raise P1V4HeldoutMeasurementError("measurement evidence contains a verdict key")
    if not wrapper_command or len(wrapper_sha256) != 64:
        raise P1V4HeldoutMeasurementError("P1v4 wrapper provenance is incomplete")
    evidence = deepcopy(dict(inner_evidence))
    evidence.pop("evidence_sha256", None)
    evidence.update({
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "branch": "p1v4-fresh-policy-replication",
        "conjecture": CONJECTURE,
        "preregistration_sha256": preregistration_sha256,
        "compatibility_execution": {
            "frozen_kernel": "p1v3_heldout_measure.py",
            "inner_evidence_sha256": inner_sha,
            "wrapper": "p1v4_heldout_measure.py",
            "wrapper_command": list(wrapper_command),
            "wrapper_sha256": wrapper_sha256,
        },
    })
    evidence["evidence_sha256"] = canonical_sha256(evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--prediction-receipt", type=Path, required=True)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--development-sidecar", type=Path, required=True)
    parser.add_argument("--heldout-sidecar", type=Path, required=True)
    parser.add_argument("--sidecar-separation-receipt", type=Path, required=True)
    parser.add_argument("--calibration-evidence", type=Path, required=True)
    parser.add_argument("--deployment-receipt", type=Path, required=True)
    parser.add_argument("--budget-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    parser.add_argument("--answer-db", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    prereg_sha = validate_preregistration(prereg, here=here)
    compat_prereg = compatible_p1v3_preregistration(prereg)
    with tempfile.TemporaryDirectory(prefix="hswm-p1v4-measure-") as raw_temp:
        temp = Path(raw_temp)
        compat_path = temp / "compat_preregistration.json"
        inner_evidence_path = temp / "inner_evidence.json"
        compat_path.write_text(
            json.dumps(compat_prereg, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            str(here / "p1v3_heldout_measure.py"),
            "--preregistration", str(compat_path),
            "--prediction-receipt", str(args.prediction_receipt),
            "--public-manifest", str(args.public_manifest),
            "--development-sidecar", str(args.development_sidecar),
            "--heldout-sidecar", str(args.heldout_sidecar),
            "--sidecar-separation-receipt", str(args.sidecar_separation_receipt),
            "--calibration-evidence", str(args.calibration_evidence),
            "--deployment-receipt", str(args.deployment_receipt),
            "--budget-manifest", str(args.budget_manifest),
            "--tokenizer-snapshot", str(args.tokenizer_snapshot),
            "--answer-db", str(args.answer_db),
            "--evidence-output", str(inner_evidence_path),
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            if completed.stdout:
                print(completed.stdout, end="", file=sys.stderr)
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            raise P1V4HeldoutMeasurementError(
                f"frozen measurement kernel exited {completed.returncode}"
            )
        inner = json.loads(inner_evidence_path.read_text(encoding="utf-8"))
    evidence = build_p1v4_evidence(
        inner_evidence=inner,
        preregistration_sha256=prereg_sha,
        wrapper_command=tuple(sys.argv),
        wrapper_sha256=file_sha256(Path(__file__).resolve()),
    )
    write_once(args.evidence_output, evidence)
    print(json.dumps({
        "evidence_output": str(args.evidence_output),
        "evidence_sha256": evidence["evidence_sha256"],
        "observation_count": len(evidence["observations"]),
        "prior_outcome_reuse": False,
        "scientific_judgment_emitted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1V4HeldoutMeasurementError",
    "build_p1v4_evidence",
    "compatible_p1v3_preregistration",
    "validate_preregistration",
]
