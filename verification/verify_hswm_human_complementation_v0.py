#!/usr/bin/env python3
"""Fail-closed verifier for the HSWM human-complementation v0 artifact set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


# 2026-08-10: HSWM left SYMPOSIUM; ROOT is this repository, so bound
# artefacts sit at the root rather than under HSWM/.
ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md"
BENCHMARK = ROOT / "HSWM_HUMAN_OUTCOME_BENCHMARK_V0_2026-07-29.md"
MANIFEST = ROOT / "LONGINUS_HSWM_HUMAN_COMPLEMENTATION_BINDING_2026-07-29.json"


class VerificationError(RuntimeError):
    """Raised when one invariant is absent or contradicted."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _require_once(text: str, token: str, label: str) -> None:
    count = text.count(token)
    if count != 1:
        raise VerificationError(f"{label}: expected exactly one {token!r}, got {count}")


def check_charter_text(text: str) -> list[str]:
    checks: list[str] = []
    for token in (
        "PROPOSED / RATIFICATION_REQUIRED",
        "user_ratified**: `false`",
        "scientific_status**: `UNJUDGED`",
        "SECONDARY_AI_PROPOSED",
        "goal-hswm-human-complementation-knowledge-program-20260729",
    ):
        if token not in text:
            raise VerificationError(f"charter missing authority marker: {token}")
        checks.append(f"charter:{token}")

    for number in range(1, 13):
        token = f"### HC-{number:02d} —"
        _require_once(text, token, "charter clause")
        checks.append(f"charter:HC-{number:02d}")

    for level in ("HCC0", "HCC1", "HCC2", "HCC3"):
        if f"**{level}**" not in text:
            raise VerificationError(f"charter missing claim level: {level}")
        checks.append(f"charter:{level}")

    for nonclaim in ("강제 융합", "업로드", "불멸", "1인칭 주체의 연속성"):
        if nonclaim not in text:
            raise VerificationError(f"charter missing nonclaim boundary: {nonclaim}")
        checks.append(f"charter:nonclaim:{nonclaim}")
    return checks


def check_benchmark_text(text: str) -> list[str]:
    checks: list[str] = []
    for token in (
        "DRAFT_UNRATIFIED_NO_MEASUREMENT",
        "user_ratified**: `false`",
        "measurement_authorized**: `false`",
        "scientific_status**: `UNJUDGED`",
        "human_subjects_approval**: `NOT_OBTAINED`",
    ):
        if token not in text:
            raise VerificationError(f"benchmark missing authority marker: {token}")
        checks.append(f"benchmark:{token}")

    for arm in ("**H**", "**A**", "**G**", "**H+A**", "**H+HSWM_FULL**", "**H+HSWM_REMOVED**", "**H+HSWM_SHUFFLED**"):
        if arm not in text:
            raise VerificationError(f"benchmark missing arm: {arm}")
        checks.append(f"benchmark:arm:{arm}")

    for family in ("TF-GEN", "TF-JUD", "TF-SOC", "TF-ACT", "TF-MEM"):
        if f"**{family}**" not in text:
            raise VerificationError(f"benchmark missing task family: {family}")
        checks.append(f"benchmark:family:{family}")

    for guardrail in range(1, 9):
        token = f"**GR-{guardrail:02d}**"
        if token not in text:
            raise VerificationError(f"benchmark missing guardrail: {token}")
        checks.append(f"benchmark:{token}")

    for level in range(6):
        token = f"**HOB-C{level}**"
        if token not in text:
            raise VerificationError(f"benchmark missing claim level: {token}")
        checks.append(f"benchmark:{token}")

    for equation_marker in ("b_f^*", "\\Delta_f", "LCB95(Δ_f) > δ_f"):
        if equation_marker not in text:
            raise VerificationError(f"benchmark missing primary equation marker: {equation_marker}")
        checks.append(f"benchmark:equation:{equation_marker}")
    return checks


def check_manifest() -> list[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema") != "longinus-hswm-human-complementation-binding/v1":
        raise VerificationError("manifest schema mismatch")
    if manifest.get("status") != "PROPOSED":
        raise VerificationError("manifest status must remain PROPOSED")
    if manifest.get("canonical_tier") != "SECONDARY_AI":
        raise VerificationError("manifest authority must remain SECONDARY_AI")

    bindings = manifest.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != 5:
        raise VerificationError("manifest must contain exactly five file bindings")

    checks: list[str] = []
    seen: set[str] = set()
    for binding in bindings:
        rel = binding["repo_relative_path"]
        if rel in seen:
            raise VerificationError(f"duplicate binding path: {rel}")
        seen.add(rel)
        path = ROOT / rel
        if not path.is_file():
            raise VerificationError(f"bound file missing: {rel}")
        if binding.get("binding_mode") == "HISTORICAL_DIGEST_ONLY":
            if rel != "INDEX.md" or binding.get("category") != "INDEX_DOC":
                raise VerificationError(
                    f"historical digest mode is restricted to the moving index: {rel}"
                )
            # A programme index is a moving catalogue, not evidence owned by this
            # 2026-07-29 proposal. Preserve its then-current digest without making
            # every future index edit re-ratify an unrelated Longinus packet.
            digest = binding.get("sha256")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise VerificationError(f"invalid historical SHA: {rel}")
            if (
                binding.get("lineStart") != 1
                or not isinstance(binding.get("lineCount"), int)
                or binding["lineCount"] <= 0
                or binding.get("lineEnd") != binding["lineCount"]
            ):
                raise VerificationError(f"invalid historical line range: {rel}")
        else:
            if binding["sha256"] != sha256(path):
                raise VerificationError(f"SHA mismatch: {rel}")
            count = line_count(path)
            if binding["lineCount"] != count:
                raise VerificationError(f"line count mismatch: {rel}")
            if binding["lineStart"] != 1 or binding["lineEnd"] != count:
                raise VerificationError(f"line range mismatch: {rel}")
        if binding["semantic_authority"] != "SECONDARY_AI_PROPOSED":
            raise VerificationError(f"authority drift: {rel}")
        if binding["crateVerifier"] != "python3 verification/verify_hswm_human_complementation_v0.py":
            raise VerificationError(f"verifier binding drift: {rel}")
        checks.append(f"manifest:{rel}")
    return checks


def verify() -> dict[str, object]:
    charter_text = CHARTER.read_text(encoding="utf-8")
    benchmark_text = BENCHMARK.read_text(encoding="utf-8")
    checks = check_charter_text(charter_text)
    checks.extend(check_benchmark_text(benchmark_text))
    checks.extend(check_manifest())

    injected = benchmark_text.replace(
        "measurement_authorized**: `false`",
        "measurement_authorized**: `true`",
        1,
    )
    negative_rejected = False
    try:
        check_benchmark_text(injected)
    except VerificationError:
        negative_rejected = True
    if not negative_rejected:
        raise VerificationError("injected-negative authority mutation was not rejected")

    return {
        "schema": "hswm-human-complementation-verification/v1",
        "status": "PASS",
        "metric": 1.0,
        "checks": len(checks),
        "negative_rejected": negative_rejected,
        "charter_sha256": sha256(CHARTER),
        "benchmark_sha256": sha256(BENCHMARK),
        "manifest_sha256": sha256(MANIFEST),
    }


def main() -> int:
    try:
        result = verify()
    except (KeyError, OSError, ValueError, VerificationError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
