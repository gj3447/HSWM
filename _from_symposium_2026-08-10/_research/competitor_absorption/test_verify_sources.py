from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from verify_sources import validate


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE / "manifest.v1.json"


class SourceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def validate_mutation(self, mutate) -> list[str]:
        payload = copy.deepcopy(self.base)
        mutate(payload)
        with tempfile.TemporaryDirectory(prefix="hswm-source-gate-") as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return validate(ROOT, path)

    def test_locked_manifest_passes(self) -> None:
        self.assertEqual(validate(ROOT, MANIFEST), [])

    def test_active_candidate_is_rejected(self) -> None:
        issues = self.validate_mutation(
            lambda payload: payload["candidates"][0].update(
                {"deployment_default": "active"}
            )
        )
        self.assertTrue(any("forbidden deployment state" in issue for issue in issues))

    def test_restricted_source_requires_clean_room_policy(self) -> None:
        def mutate(payload) -> None:
            payload["candidates"][1]["implementation_policy"] = "direct_copy"

        issues = self.validate_mutation(mutate)
        self.assertTrue(any("restricted clone is not clean-room only" in issue for issue in issues))

    def test_code_anchor_drift_is_rejected(self) -> None:
        def mutate(payload) -> None:
            payload["candidates"][0]["code_refs"][0]["anchor"] = "missing_symbol"

        issues = self.validate_mutation(mutate)
        self.assertTrue(any("anchor drift" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
