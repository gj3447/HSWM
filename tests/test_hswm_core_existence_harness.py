#!/usr/bin/env python3
"""Smoke tests for HSWM core existence concentration harness."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HSWM = REPO_ROOT
ROOT = REPO_ROOT
HARNESS = REPO_ROOT / "_research" / "harnesses" / "hswm_core_existence_harness.py"
CONFIG = REPO_ROOT / "manifests" / "hswm_core_existence_harness.v1.json"
CORE_DOCS = REPO_ROOT / "docs" / "research" / "core-development"


class CoreExistenceHarnessSmoke(unittest.TestCase):
    def test_config(self) -> None:
        d = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(d["schema_version"], "hswm-core-existence-harness-config/v1")
        self.assertEqual(d["speak_as"], "HSWM core 개발")
        self.assertIn("dual_pillars", d)
        self.assertIn("T_ELEVATE_PLAN_REVIEW", d["tracks"])
        self.assertEqual(d["concentration_rule"]["max_active_tracks"], 1)
        self.assertTrue(any(x["id"].startswith("X1") for x in d["existence_ladder"]))
        self.assertIn("333_committee_reconfig_as_main", d["hard_ban_until_x1_moves"])

    def test_name_command(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HARNESS), "name", "--symposium-root", str(ROOT)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("HSWM core 개발", proc.stdout)
        self.assertIn("BUILD", proc.stdout)
        self.assertIn("ELEVATE", proc.stdout)

    def test_core_dev_entry_exists(self) -> None:
        self.assertTrue((CORE_DOCS / "HSWM_CORE_DEV.md").is_file())

    def test_scoreboard_exists(self) -> None:
        sb = CORE_DOCS / "EXISTENCE_SCOREBOARD.v1.md"
        self.assertTrue(sb.is_file())
        t = sb.read_text(encoding="utf-8")
        self.assertIn("X1", t)
        self.assertIn("NOT_MEASURED", t)

    def test_status_blocked_without_focus(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HARNESS), "status", "--symposium-root", str(ROOT)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(proc.returncode, 3, msg=proc.stdout + proc.stderr)
        self.assertIn("X1", proc.stdout)

    def test_t1_readyish_with_focus_and_a2(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "status",
                "--symposium-root",
                str(ROOT),
                "--user-approved-focus",
                "--identity",
                "KEEP_A2",
                "--active-track",
                "T1_F1_TYPED_FUNCTION_NETWORK",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(proc.returncode, 4, msg=proc.stdout + proc.stderr)
        self.assertIn("FOCUS_OPEN", proc.stdout)

    def test_banned_claimed_main(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "status",
                "--symposium-root",
                str(ROOT),
                "--user-approved-focus",
                "--identity",
                "KEEP_A2",
                "--claimed-main",
                "333_committee_reconfig_as_main",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(proc.returncode, 3, msg=proc.stdout + proc.stderr)

    def test_model_call_query_forbidden(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(HARNESS),
                "status",
                "--symposium-root",
                str(ROOT),
                "--allow-model-call-query",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
