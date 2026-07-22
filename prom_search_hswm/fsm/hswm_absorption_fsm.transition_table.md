# HSWM immutable absorption candidate — transition table

Semantic authority: [`hswm_absorption_fsm.v1.json`](hswm_absorption_fsm.v1.json). This table and the Mermaid view are derived review surfaces, not independent specifications.

| From | Event | Guard / priority | To | Command |
|---|---|---|---|---|
| `collecting` | `ABSORB` | — | `collecting` | `RecordAbsorption` |
| `collecting` | `FREEZE` | `freeze_allowed` | `frozen` | `FreezeCandidate` |
| `frozen` | `START_EVALUATION` | `evaluation_allowed` | `evaluating` | `RunEvaluation` |
| `evaluating` | `EVALUATION_RECORDED` | `evidence_invalid` / 1 | `quarantined` | `QuarantineCandidate` |
| `evaluating` | `EVALUATION_RECORDED` | `promotion_allowed` / 2 | `canary` | `RecordEvaluationPass` |
| `evaluating` | `EVALUATION_RECORDED` | `evaluation_rejected` / 3 | `rejected` | `RecordRejection` |
| `canary` | `CANARY_OBSERVATION` | `canary_observation_pass` | `canary` | `RecordCanary` |
| `canary` | `CANARY_FAILED` | — | `rejected` | `RecordRejection` |
| `canary` | `REQUEST_PROMOTION` | `canary_complete` | `promotion_pending` | `RequestActivation` |
| `promotion_pending` | `ACTIVATION_COMMITTED` | `activation_receipt_matches` | `active` | `RecordActivation` |
| `promotion_pending` | `ACTIVATION_FAILED` | `activation_transient` / 1 | `canary` | `RecordActivationFailure` |
| `promotion_pending` | `ACTIVATION_FAILED` | `activation_stale` / 2 | `rejected` | `RecordRejection` |
| `active` | `REGRESSION_DETECTED` | `regression_confirmed` | `rollback_pending` | `RequestRollback` |
| `active` | `SUPERSESSION_COMMITTED` | `supersession_receipt_matches` | `superseded` | `RecordSupersession` |
| `rollback_pending` | `ROLLBACK_COMMITTED` | `rollback_receipt_matches` | `rolled_back` | `RecordRollback` |
| `rollback_pending` | `ROLLBACK_FAILED` | — | `rollback_pending` | `RecordRollbackFailure` |
| `rollback_pending` | `SUPERSESSION_COMMITTED` | `supersession_receipt_matches` | `superseded` | `RecordSupersession` |

All unknown events, wrong-state events, false guards, duplicate IDs, conflicting duplicates, sequence gaps, and terminal-state inputs are rejected with `AuditInvalidTransition`; they do not mutate the configuration. A failed candidate is never revived. Repair starts a new `candidate_id` from the current active immutable snapshot.
