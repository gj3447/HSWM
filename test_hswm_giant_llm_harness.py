#!/usr/bin/env python3
"""Smoke and contract tests for the HSWM giant-LLM research harness."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HSWM = Path(__file__).resolve().parent
ROOT = HSWM.parent
HARNESS = HSWM / "hswm_giant_llm_harness.py"
CONFIG = HSWM / "hswm_giant_llm_harness.v1.json"
DUMP = (
    ROOT
    / "FINDINGS"
    / "hswm-giant-llm-harness-2026-08-06"
    / "RESEARCH_DUMP.v1.json"
)


def run_harness(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            *args,
            "--symposium-root",
            str(root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class GiantLlmHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.source_dump = json.loads(DUMP.read_text(encoding="utf-8"))

    def test_config_preserves_user_primary_and_gates(self) -> None:
        self.assertEqual(
            self.config["schema_version"],
            "hswm-giant-llm-harness-config/v1",
        )
        self.assertEqual(
            self.config["authority"]["classification"],
            "SECONDARY_AI_OPERATIONALIZATION_OF_USER_PRIMARY",
        )
        self.assertIn("거대 llm", self.config["authority"]["user_primary"]["utterance"])
        self.assertEqual(len(self.config["gates"]), 8)
        self.assertEqual(
            set(self.config["priority_order"]),
            {gate["id"] for gate in self.config["gates"]},
        )
        self.assertEqual(len(self.config["primary_identity_gate_ids"]), 3)

    def test_source_dump_is_metadata_paraphrase_only(self) -> None:
        self.assertEqual(
            self.source_dump["schema_version"], "hswm-research-source-dump/v1"
        )
        records = self.source_dump["records"]
        self.assertEqual(self.source_dump["source_count"], 24)
        self.assertEqual(len(records), 24)
        self.assertFalse(self.source_dump["copyright_scope"]["fulltext_included"])
        self.assertTrue(all(record["fulltext_stored"] is False for record in records))
        self.assertTrue(
            all(
                record["content_mode"]
                == "METADATA_AND_ORIGINAL_PARAPHRASE_ONLY"
                for record in records
            )
        )

    def test_all_four_fields_meet_minimums(self) -> None:
        counts: dict[str, int] = {}
        for record in self.source_dump["records"]:
            counts[record["field"]] = counts.get(record["field"], 0) + 1
        self.assertEqual(
            set(counts), {"mathematics", "philosophy", "science", "modern_ai"}
        )
        for field_name, minimum in self.config["minimum_sources_per_field"].items():
            self.assertGreaterEqual(counts[field_name], minimum)

    def test_every_gate_is_falsifiable_and_sourced(self) -> None:
        source_ids = {record["source_id"] for record in self.source_dump["records"]}
        for gate in self.config["gates"]:
            self.assertTrue(gate["operational_test"])
            self.assertTrue(gate["strongest_baselines"])
            self.assertTrue(gate["falsifier"])
            self.assertTrue(gate["next_action"])
            self.assertTrue(set(gate["required_source_ids"]).issubset(source_ids))

    def test_thesis_command(self) -> None:
        result = run_harness("thesis")
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("giant LLM", result.stdout)
        self.assertIn("EXECUTABLE_HYPERGRAPH_WORLD_MODEL", result.stdout)
        self.assertIn("USER_PRIMARY", result.stdout)

    def test_status_command_is_diagnostic_not_scientific_judge(self) -> None:
        result = run_harness("status")
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("UNJUDGED_BY_THIS_HARNESS", result.stdout)
        self.assertIn("metadata + original paraphrase; no fulltext", result.stdout)
        for axis in ("INFORM", "CONSTRAIN", "VERIFY", "CORRECT"):
            self.assertIn(f"[PASS] {axis}", result.stdout)
        self.assertIn("G1_HSWM_LAYER_CAUSALITY", result.stdout)
        self.assertIn("KILLED_ON_CURRENT_BED", result.stdout)

    def test_sources_filter(self) -> None:
        result = run_harness("sources", "--field", "philosophy")
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("PHIL-LIST-GROUP-AGENCY-2021", result.stdout)
        self.assertNotIn("AI-MOA-2024", result.stdout)
        self.assertIn("fulltext_stored=false", result.stdout)

    def test_json_and_receipt_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt_path = Path(temporary_directory) / "receipt.json"
            result = run_harness(
                "json", "--write-receipt", str(receipt_path)
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            stdout_receipt = json.loads(result.stdout)
            file_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(stdout_receipt, file_receipt)
            self.assertEqual(stdout_receipt["source_count"], 24)
            self.assertFalse(stdout_receipt["model_call_allowed_by_this_harness"])
            self.assertFalse(stdout_receipt["network_fetch_allowed_by_this_harness"])
            self.assertEqual(len(stdout_receipt["config_sha256"]), 64)
            self.assertEqual(len(stdout_receipt["source_dump_sha256"]), 64)

    def test_rejects_any_fulltext_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            bad_dump = json.loads(json.dumps(self.source_dump))
            bad_dump["records"][0]["fulltext_stored"] = True
            bad_path = Path(temporary_directory) / "bad-dump.json"
            bad_path.write_text(
                json.dumps(bad_dump, ensure_ascii=False), encoding="utf-8"
            )
            result = run_harness("check", "--source-dump", str(bad_path))
            self.assertEqual(result.returncode, 2, msg=result.stdout + result.stderr)
            self.assertIn("SOURCE_DUMP_ERROR", result.stderr)

    def test_missing_local_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            temporary_hswm = temporary_root / "HSWM"
            temporary_dump_dir = (
                temporary_root
                / "FINDINGS"
                / "hswm-giant-llm-harness-2026-08-06"
            )
            temporary_hswm.mkdir(parents=True)
            temporary_dump_dir.mkdir(parents=True)
            (temporary_hswm / CONFIG.name).write_text(
                CONFIG.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (temporary_dump_dir / DUMP.name).write_text(
                DUMP.read_text(encoding="utf-8"), encoding="utf-8"
            )
            result = run_harness("check", root=temporary_root)
            self.assertEqual(result.returncode, 3, msg=result.stdout + result.stderr)
            self.assertIn("LOCAL_EVIDENCE_ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
