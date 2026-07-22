#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from hswm_absorption_fsm import CandidateConfig, TRANSITIONS, make_event, step


HERE = Path(__file__).resolve().parent
SPEC = HERE / "fsm" / "hswm_absorption_fsm.v1.json"


class AbsorptionFSMTest(unittest.TestCase):
    def initial(self, suffix: str = "x") -> CandidateConfig:
        return CandidateConfig(
            candidate_id=f"candidate-{suffix}",
            implementer_id="impl",
            base_version="base-v1",
            rollback_target_hash="base-v1",
            policy_min_unseen_gain=0.01,
            policy_max_retention_drop=-0.01,
        )

    def send(self, config: CandidateConfig, event_type: str, event_id: str, **payload):
        event = make_event(config, event_type, event_id, payload.pop("actor", "impl"), **payload)
        return step(config, event), event

    def to_frozen(self, config: CandidateConfig):
        (config, _), absorb = self.send(
            config, "ABSORB", "e0", source_manifest_hash="source-sha"
        )
        (config, commands), _ = self.send(
            config,
            "FREEZE",
            "e1",
            candidate_hash="candidate-sha",
            prereg_hash="prereg-sha",
            split_manifest_hash="split-sha",
        )
        self.assertEqual([command.kind for command in commands], ["FreezeCandidate"])
        return config, absorb

    def to_evaluating(self, config: CandidateConfig):
        config, _ = self.to_frozen(config)
        (config, commands), _ = self.send(
            config,
            "START_EVALUATION",
            "e2",
            actor="controller",
            candidate_hash="candidate-sha",
            holdout_epoch="fresh-epoch-1",
            fresh_holdout=True,
            evaluator_id="independent-evaluator",
        )
        self.assertEqual(config.state, "evaluating")
        self.assertEqual([command.kind for command in commands], ["RunEvaluation"])
        return config

    def evaluation_payload(self, **overrides):
        payload = {
            "actor": "independent-evaluator",
            "candidate_hash": "candidate-sha",
            "evidence_hash": "evidence-sha",
            "evidence_replayed": True,
            "equal_budget": True,
            "no_overlap": True,
            "unseen_delta": 0.02,
            "unseen_ci_low": 0.001,
            "retention_delta": 0.0,
            "independent_evaluator": True,
            "reason": "pre_registered_gate",
        }
        payload.update(overrides)
        return payload

    def to_canary(self, config: CandidateConfig):
        config = self.to_evaluating(config)
        (config, commands), _ = self.send(
            config, "EVALUATION_RECORDED", "e3", **self.evaluation_payload()
        )
        self.assertEqual(config.state, "canary")
        self.assertEqual([command.kind for command in commands], ["RecordEvaluationPass"])
        return config

    def to_active(self, config: CandidateConfig):
        config = self.to_canary(config)
        (config, _), _ = self.send(
            config,
            "CANARY_OBSERVATION",
            "e4",
            actor="canary",
            window_id="w1",
            no_regression=True,
            equal_budget=True,
        )
        (config, _), _ = self.send(
            config,
            "REQUEST_PROMOTION",
            "e5",
            actor="controller",
            request_id="activate-1",
        )
        (config, commands), _ = self.send(
            config,
            "ACTIVATION_COMMITTED",
            "e6",
            actor="registry",
            candidate_hash="candidate-sha",
            base_version="base-v1",
            receipt_hash="activation-receipt",
        )
        self.assertEqual(config.state, "active")
        self.assertEqual([command.kind for command in commands], ["RecordActivation"])
        return config

    def test_transition_inventory_conforms_to_spec(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        declared = {item["id"] for item in spec["machines"][0]["transitions"]}
        implemented = {item.id for item in TRANSITIONS}
        self.assertEqual(declared, implemented)

    def test_happy_path_reaches_active(self):
        config = self.to_active(self.initial("happy"))
        self.assertEqual(config.candidate_hash, "candidate-sha")
        self.assertEqual(config.evaluated_candidate_hash, "candidate-sha")
        self.assertEqual(config.canary_windows_passed, 1)

    def test_seen_only_gain_cannot_promote(self):
        config = self.to_evaluating(self.initial("memorization"))
        (config, commands), _ = self.send(
            config,
            "EVALUATION_RECORDED",
            "e3",
            **self.evaluation_payload(unseen_delta=0.0, unseen_ci_low=0.0, reason="seen_only_gain"),
        )
        self.assertEqual(config.state, "rejected")
        self.assertEqual([command.kind for command in commands], ["RecordRejection"])

    def test_invalid_evidence_is_quarantined_before_metric_choice(self):
        config = self.to_evaluating(self.initial("quarantine"))
        (config, commands), _ = self.send(
            config,
            "EVALUATION_RECORDED",
            "e3",
            **self.evaluation_payload(
                evidence_replayed=False,
                unseen_delta=1.0,
                unseen_ci_low=1.0,
                reason="replay_failed",
            ),
        )
        self.assertEqual(config.state, "quarantined")
        self.assertEqual([command.kind for command in commands], ["QuarantineCandidate"])

    def test_duplicate_tamper_and_reorder_are_full_noops(self):
        config = self.initial("order")
        (after, _), original = self.send(
            config, "ABSORB", "e0", source_manifest_hash="source-sha"
        )
        duplicate_config, commands = step(after, original)
        self.assertEqual(duplicate_config, after)
        self.assertEqual(commands[0].payload["reason"], "duplicate_noop")

        tampered = {**original, "source_manifest_hash": "different-sha"}
        tampered_config, commands = step(after, tampered)
        self.assertEqual(tampered_config, after)
        self.assertEqual(commands[0].payload["reason"], "conflicting_duplicate_tamper")

        reordered = make_event(
            after,
            "ABSORB",
            "e9",
            "impl",
            source_manifest_hash="late-sha",
        )
        reordered["seq"] += 1
        reordered_config, commands = step(after, reordered)
        self.assertEqual(reordered_config, after)
        self.assertTrue(commands[0].payload["reason"].startswith("reordered_expected_"))

    def test_freeze_and_late_absorption_fail_closed(self):
        config = self.initial("freeze")
        (unchanged, commands), _ = self.send(
            config,
            "FREEZE",
            "e0",
            candidate_hash="candidate-sha",
            prereg_hash="prereg-sha",
            split_manifest_hash="split-sha",
        )
        self.assertEqual(unchanged, config)
        self.assertEqual(commands[0].payload["reason"], "guard_false")

        frozen, _ = self.to_frozen(config)
        (unchanged, commands), _ = self.send(
            frozen, "ABSORB", "late", source_manifest_hash="late-sha"
        )
        self.assertEqual(unchanged, frozen)
        self.assertEqual(commands[0].payload["reason"], "invalid_state_event")

    def test_canary_failure_and_incomplete_promotion(self):
        canary = self.to_canary(self.initial("canary"))
        (unchanged, commands), _ = self.send(
            canary, "REQUEST_PROMOTION", "e4", actor="controller", request_id="too-early"
        )
        self.assertEqual(unchanged, canary)
        self.assertEqual(commands[0].payload["reason"], "guard_false")

        (rejected, commands), _ = self.send(
            canary, "CANARY_FAILED", "e4", actor="canary", reason="regression"
        )
        self.assertEqual(rejected.state, "rejected")
        self.assertEqual(commands[0].kind, "RecordRejection")

    def test_activation_retry_and_stale_base_branches(self):
        canary = self.to_canary(self.initial("activation"))
        (canary, _), _ = self.send(
            canary,
            "CANARY_OBSERVATION",
            "e4",
            actor="canary",
            window_id="w1",
            no_regression=True,
            equal_budget=True,
        )
        (pending, _), _ = self.send(
            canary, "REQUEST_PROMOTION", "e5", actor="controller", request_id="activate"
        )
        (retried, commands), _ = self.send(
            pending,
            "ACTIVATION_FAILED",
            "e6",
            actor="registry",
            failure_class="transient",
            reason="timeout",
        )
        self.assertEqual(retried.state, "canary")
        self.assertEqual(commands[0].kind, "RecordActivationFailure")

        (rejected, commands), _ = self.send(
            pending,
            "ACTIVATION_FAILED",
            "e6-stale",
            actor="registry",
            failure_class="stale_base",
            reason="base_changed",
        )
        self.assertEqual(rejected.state, "rejected")
        self.assertEqual(commands[0].kind, "RecordRejection")

    def test_exact_rollback_retry_success_and_concurrent_supersession(self):
        active = self.to_active(self.initial("rollback"))
        (pending, commands), _ = self.send(
            active,
            "REGRESSION_DETECTED",
            "e7",
            actor="monitor",
            confirmed=True,
            reason="retention_regression",
        )
        self.assertEqual(pending.state, "rollback_pending")
        self.assertEqual(commands[0].kind, "RequestRollback")

        (retry, commands), _ = self.send(
            pending, "ROLLBACK_FAILED", "e8", actor="registry", reason="transient"
        )
        self.assertEqual(retry.state, "rollback_pending")
        self.assertEqual(commands[0].kind, "RecordRollbackFailure")
        (rolled_back, commands), _ = self.send(
            retry,
            "ROLLBACK_COMMITTED",
            "e9",
            actor="registry",
            rollback_target_hash="base-v1",
            receipt_hash="rollback-receipt",
        )
        self.assertEqual(rolled_back.state, "rolled_back")
        self.assertEqual(commands[0].kind, "RecordRollback")

        (superseded, commands), _ = self.send(
            pending,
            "SUPERSESSION_COMMITTED",
            "e8-successor",
            actor="registry",
            successor_hash="newer-candidate",
            receipt_hash="successor-receipt",
        )
        self.assertEqual(superseded.state, "superseded")
        self.assertEqual(commands[0].kind, "RecordSupersession")

    def test_active_supersession_and_terminal_inputs(self):
        active = self.to_active(self.initial("supersede"))
        (superseded, commands), _ = self.send(
            active,
            "SUPERSESSION_COMMITTED",
            "e7",
            actor="registry",
            successor_hash="next-hash",
            receipt_hash="supersede-receipt",
        )
        self.assertEqual(superseded.state, "superseded")
        self.assertEqual(commands[0].kind, "RecordSupersession")
        (unchanged, commands), _ = self.send(
            superseded, "ABSORB", "terminal-event", source_manifest_hash="never"
        )
        self.assertEqual(unchanged, superseded)
        self.assertEqual(commands[0].payload["reason"], "terminal_state")


if __name__ == "__main__":
    unittest.main()
