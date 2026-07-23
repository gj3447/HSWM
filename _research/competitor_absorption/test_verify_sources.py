from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from verify_sources import validate


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "manifest.v1.json"


class SourceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def validate_mutation(
        self,
        mutate: Callable[[dict[str, Any]], None],
    ) -> list[str]:
        payload = copy.deepcopy(self.base)
        mutate(payload)
        with tempfile.TemporaryDirectory(prefix="hswm-source-gate-") as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return validate(ROOT, path)

    def test_locked_manifest_passes_without_external_bundle(self) -> None:
        self.assertEqual(validate(ROOT, MANIFEST), [])

    def test_manifest_contains_no_user_absolute_path(self) -> None:
        serialized = MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", serialized)
        self.assertEqual(self.base["hswm_baseline"]["repository"], ".")

    def test_active_candidate_is_rejected(self) -> None:
        issues = self.validate_mutation(
            lambda payload: payload["candidates"][0].update(
                {"deployment_default": "active"}
            )
        )
        self.assertTrue(any("forbidden deployment state" in issue for issue in issues))

    def test_restricted_source_requires_clean_room_policy(self) -> None:
        def mutate(payload: dict[str, Any]) -> None:
            payload["candidates"][1]["implementation_policy"] = "direct_copy"

        issues = self.validate_mutation(mutate)
        self.assertTrue(
            any("restricted clone is not clean-room only" in issue for issue in issues)
        )

    def test_malformed_code_anchor_is_rejected_without_bundle(self) -> None:
        def mutate(payload: dict[str, Any]) -> None:
            payload["candidates"][0]["code_refs"][0]["anchor"] = ""

        issues = self.validate_mutation(mutate)
        self.assertTrue(any("anchor must be non-empty" in issue for issue in issues))

    def test_absolute_baseline_repository_is_rejected(self) -> None:
        def mutate(payload: dict[str, Any]) -> None:
            payload["hswm_baseline"]["repository"] = "/tmp/private-hswm"

        issues = self.validate_mutation(mutate)
        self.assertTrue(
            any("hswm_baseline.repository must be relative" in issue for issue in issues)
        )

    def test_noncanonical_lock_path_is_rejected(self) -> None:
        def mutate(payload: dict[str, Any]) -> None:
            payload["locks"]["repositories"] = "../repos.lock.tsv"

        issues = self.validate_mutation(mutate)
        self.assertTrue(any("locks.repositories must be" in issue for issue in issues))

    def test_baseline_ancestry_is_enforced(self) -> None:
        def mutate(payload: dict[str, Any]) -> None:
            payload["hswm_baseline"]["commit"] = "0" * 40

        issues = self.validate_mutation(mutate)
        self.assertTrue(any("baseline ancestry failed" in issue for issue in issues))

    def test_explicit_missing_bundle_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hswm-missing-bundle-") as tmp:
            missing = Path(tmp) / "not-present"
            issues = validate(ROOT, MANIFEST, missing)
        self.assertTrue(any("explicit bundle root is missing" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
