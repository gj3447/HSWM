"""Separate-process outcome evaluator for the opaque G1 instrument (G0-local).

The evaluator is a process boundary that owns the evaluator reveal (correct
action code, salt, and canary per episode).  The actor/proposer instrument
never reads that file: it seals a trajectory, then asks this process exactly
once per episode whether the sealed action code was correct.  The reply
carries a salt-keyed HMAC so a post-run verifier holding the reveal can prove
which process produced every feedback bit, and an append-only ledger that
the evaluator writes before replying makes a second question about the same
episode impossible.

Run it under a separate OS user whose reveal file is unreadable by the
instrument; the reply reports the evaluator's uid so the runtime binding can
record ``SEPARATE_OS_USER`` or ``SAME_OS_USER``.  This satisfies the G0-local
single-owner criterion only.  It is not an independently owned outcome
custodian, not G0-external, and not evidence of causal credit, learning, or
efficacy.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hmac
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


REQUEST_SCHEMA = "hswm-g1-opaque-evaluator-request/v1"
FEEDBACK_SCHEMA = "hswm-g1-opaque-evaluator-feedback/v1"
LEDGER_SCHEMA = "hswm-g1-opaque-evaluator-ledger-row/v1"
REVEAL_SCHEMA = "hswm-g1-opaque-evaluator-reveal/v1"
EVALUATOR_BOUNDARY = (
    "SEPARATE_PROCESS_SALT_KEYED_ONE_SHOT_EVALUATOR_G0_LOCAL_ONLY_NOT_INDEPENDENTLY_"
    "OWNED_NOT_G0_EXTERNAL_NOT_CF07"
)
MAX_REQUEST_BYTES = 65_536
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ACTION_CODE = re.compile(r"act_[0-9a-f]{8}\Z")
_REQUEST_FIELDS = {
    "schema_version", "study_uid", "protocol_canonical_sha256", "episode_uid",
    "trajectory_sha256", "action_code",
}
_ENTRY_FIELDS = {"correct_action_code", "episode_uid", "leakage_canary", "ordinal", "salt"}
_REVEAL_FIELDS = {
    "episodes", "protocol_canonical_sha256", "reveal_commitment_root", "schema_version", "study_uid",
}
_FEEDBACK_FIELDS = {
    "schema_version", "study_uid", "protocol_canonical_sha256", "episode_uid",
    "trajectory_sha256", "action_code", "choice_was_correct", "evaluator_os_uid",
    "evaluator_os_gid", "evaluator_ledger_sequence", "evaluator_boundary", "feedback_mac",
    "receipt_sha256",
}


class EvaluatorRefusal(ValueError):
    """The request, reveal, ledger, or boundary does not satisfy the evaluator API."""


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EvaluatorRefusal(f"{label} must be a SHA-256 hex digest")
    return value


def _parse_canonical(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_REQUEST_BYTES:
        raise EvaluatorRefusal("request exceeds the bounded byte limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluatorRefusal("request is not UTF-8 JSON") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise EvaluatorRefusal("request is not a canonical JSON object")
    return value


def load_reveal(path: Path) -> dict[str, Any]:
    """Load and commitment-validate the evaluator reveal; never return it to a caller process."""

    raw = path.read_bytes()
    try:
        reveal = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluatorRefusal("reveal is not UTF-8 JSON") from error
    if not isinstance(reveal, dict) or set(reveal) != _REVEAL_FIELDS or reveal["schema_version"] != REVEAL_SCHEMA:
        raise EvaluatorRefusal("reveal shape or schema drifted")
    _sha(reveal["protocol_canonical_sha256"], "reveal protocol digest")
    _sha(reveal["reveal_commitment_root"], "reveal commitment root")
    if not isinstance(reveal["study_uid"], str) or not reveal["study_uid"]:
        raise EvaluatorRefusal("reveal study uid is invalid")
    entries = reveal["episodes"]
    if not isinstance(entries, list) or not entries:
        raise EvaluatorRefusal("reveal entries are invalid")
    commitments: list[str] = []
    seen: set[str] = set()
    for ordinal, entry in enumerate(entries, start=1):
        if (
            not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS or entry["ordinal"] != ordinal
            or not isinstance(entry["episode_uid"], str) or entry["episode_uid"] in seen
            or not isinstance(entry["correct_action_code"], str)
            or not _ACTION_CODE.fullmatch(entry["correct_action_code"])
            or not isinstance(entry["salt"], str) or len(entry["salt"]) < 8
            or not isinstance(entry["leakage_canary"], str) or not entry["leakage_canary"]
        ):
            raise EvaluatorRefusal("reveal entry drifted")
        seen.add(entry["episode_uid"])
        commitments.append(canonical_sha256(entry))
    if canonical_sha256({"episode_commitments": commitments}) != reveal["reveal_commitment_root"]:
        raise EvaluatorRefusal("reveal commitment root does not reconstruct")
    return reveal


def _ledger_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_bytes().splitlines():
        if not line:
            continue
        row = _parse_canonical(line)
        if row.get("schema_version") != LEDGER_SCHEMA:
            raise EvaluatorRefusal("evaluator ledger row schema drifted")
        rows.append(row)
    return rows


def feedback_mac(fields: Mapping[str, Any], *, salt: str) -> str:
    return hmac.new(salt.encode("utf-8"), canonical_json_bytes(fields), sha256).hexdigest()


def handle_request(
    *, reveal: Mapping[str, Any], ledger_path: Path, request: Mapping[str, Any]
) -> dict[str, Any]:
    """Answer exactly one sealed-trajectory question per episode; log before replying."""

    if set(request) != _REQUEST_FIELDS or request["schema_version"] != REQUEST_SCHEMA:
        raise EvaluatorRefusal("request field set or schema drifted")
    if request["study_uid"] != reveal["study_uid"]:
        raise EvaluatorRefusal("request study uid differs from the reveal")
    if _sha(request["protocol_canonical_sha256"], "request protocol digest") != reveal["protocol_canonical_sha256"]:
        raise EvaluatorRefusal("request protocol digest differs from the reveal")
    trajectory_sha = _sha(request["trajectory_sha256"], "request trajectory digest")
    action_code = request["action_code"]
    if not isinstance(action_code, str) or not _ACTION_CODE.fullmatch(action_code):
        raise EvaluatorRefusal("request action code is invalid")
    entry = next((item for item in reveal["episodes"] if item["episode_uid"] == request["episode_uid"]), None)
    if entry is None:
        raise EvaluatorRefusal("request episode is not in the reveal")
    rows = _ledger_rows(ledger_path)
    if any(row["episode_uid"] == entry["episode_uid"] for row in rows):
        raise EvaluatorRefusal("evaluator already answered this episode; no second question is allowed")
    fields = {
        "schema_version": FEEDBACK_SCHEMA,
        "study_uid": reveal["study_uid"],
        "protocol_canonical_sha256": reveal["protocol_canonical_sha256"],
        "episode_uid": entry["episode_uid"],
        "trajectory_sha256": trajectory_sha,
        "action_code": action_code,
        "choice_was_correct": action_code == entry["correct_action_code"],
        "evaluator_os_uid": os.getuid(),
        "evaluator_os_gid": os.getgid(),
        "evaluator_ledger_sequence": len(rows) + 1,
        "evaluator_boundary": EVALUATOR_BOUNDARY,
    }
    fields["feedback_mac"] = feedback_mac(fields, salt=entry["salt"])
    feedback = {**fields, "receipt_sha256": canonical_sha256(fields)}
    row = {
        "schema_version": LEDGER_SCHEMA,
        "episode_uid": entry["episode_uid"],
        "trajectory_sha256": trajectory_sha,
        "action_code": action_code,
        "feedback_receipt_sha256": feedback["receipt_sha256"],
        "sequence": len(rows) + 1,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(ledger_path, flags, 0o600)
    try:
        os.write(descriptor, canonical_json_bytes(row) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return feedback


def verify_feedback(feedback: Mapping[str, Any], *, reveal: Mapping[str, Any]) -> None:
    """Post-run check with the attached reveal: the feedback was keyed by the episode salt."""

    if not isinstance(feedback, Mapping) or set(feedback) != _FEEDBACK_FIELDS:
        raise EvaluatorRefusal("feedback field set drifted")
    if feedback["schema_version"] != FEEDBACK_SCHEMA or feedback["evaluator_boundary"] != EVALUATOR_BOUNDARY:
        raise EvaluatorRefusal("feedback schema or boundary drifted")
    unsigned = dict(feedback)
    receipt = unsigned.pop("receipt_sha256")
    if receipt != canonical_sha256(unsigned):
        raise EvaluatorRefusal("feedback receipt digest mismatch")
    mac = unsigned.pop("feedback_mac")
    entry = next((item for item in reveal["episodes"] if item["episode_uid"] == feedback["episode_uid"]), None)
    if entry is None:
        raise EvaluatorRefusal("feedback episode is not in the reveal")
    if not hmac.compare_digest(mac, feedback_mac(unsigned, salt=entry["salt"])):
        raise EvaluatorRefusal("feedback MAC was not keyed by the evaluator salt")
    if feedback["choice_was_correct"] is not (feedback["action_code"] == entry["correct_action_code"]):
        raise EvaluatorRefusal("feedback verdict disagrees with the reveal")
    if feedback["study_uid"] != reveal["study_uid"] or feedback["protocol_canonical_sha256"] != reveal["protocol_canonical_sha256"]:
        raise EvaluatorRefusal("feedback study or protocol binding drifted")


@dataclass(frozen=True)
class EvaluatorEndpoint:
    """Instrument-side client: one subprocess per question, no shell, no reveal access."""

    argv_prefix: tuple[str, ...]
    reveal_path: str
    ledger_path: str
    timeout_seconds: float = 30.0

    def argv(self) -> list[str]:
        return [
            *self.argv_prefix, "--reveal", self.reveal_path, "--ledger", self.ledger_path,
        ]

    def call(
        self, *, study_uid: str, protocol_sha256: str, episode_uid: str,
        trajectory_sha256: str, action_code: str,
    ) -> dict[str, Any]:
        request = {
            "schema_version": REQUEST_SCHEMA,
            "study_uid": study_uid,
            "protocol_canonical_sha256": protocol_sha256,
            "episode_uid": episode_uid,
            "trajectory_sha256": trajectory_sha256,
            "action_code": action_code,
        }
        try:
            completed = subprocess.run(
                self.argv(), input=canonical_json_bytes(request), capture_output=True,
                timeout=self.timeout_seconds, check=False, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise EvaluatorRefusal(f"evaluator process could not complete: {type(error).__name__}") from error
        if completed.returncode != 0:
            raise EvaluatorRefusal("evaluator process refused the question")
        feedback = _parse_canonical(completed.stdout.strip())
        if set(feedback) != _FEEDBACK_FIELDS or feedback["schema_version"] != FEEDBACK_SCHEMA:
            raise EvaluatorRefusal("evaluator reply shape drifted")
        if any(feedback[key] != request[key] for key in ("study_uid", "protocol_canonical_sha256", "episode_uid", "trajectory_sha256", "action_code")):
            raise EvaluatorRefusal("evaluator reply does not echo the sealed question")
        if type(feedback["choice_was_correct"]) is not bool:
            raise EvaluatorRefusal("evaluator verdict must be a boolean")
        unsigned = dict(feedback)
        if unsigned.pop("receipt_sha256") != canonical_sha256(unsigned):
            raise EvaluatorRefusal("evaluator reply receipt digest mismatch")
        _sha(feedback["feedback_mac"], "feedback mac")
        return feedback

    @staticmethod
    def separation(feedback: Mapping[str, Any]) -> str:
        return "SEPARATE_OS_USER" if feedback["evaluator_os_uid"] != os.getuid() else "SAME_OS_USER"


def default_endpoint(reveal_path: str | Path, ledger_path: str | Path) -> EvaluatorEndpoint:
    return EvaluatorEndpoint(
        argv_prefix=(sys.executable, "-m", "hswm.experiments.g1_opaque_evaluator_process"),
        reveal_path=str(Path(reveal_path)), ledger_path=str(Path(ledger_path)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reveal", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = _parse_canonical(sys.stdin.buffer.read())
        reveal = load_reveal(args.reveal)
        feedback = handle_request(reveal=reveal, ledger_path=args.ledger, request=request)
        sys.stdout.buffer.write(canonical_json_bytes(feedback) + b"\n")
    except (OSError, ValueError) as error:
        sys.stderr.write(f"G1_OPAQUE_EVALUATOR_REFUSAL:{type(error).__name__}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
