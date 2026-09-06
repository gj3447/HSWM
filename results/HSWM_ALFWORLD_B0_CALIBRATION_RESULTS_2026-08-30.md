# ALFWorld B0 calibration — recovered 2026-08-30 occurrence

Status: `INCONCLUSIVE_MEASUREMENT_NOT_READY`.
Occurred **2026-08-30 22:49:08–22:55:47 UTC**; recovered and reverified on
**2026-09-06**. This is the first checked-in account of an already consumed
occurrence, not a new run or a successful comparator.

The sealed B0 selection was attempted on DGX at source commit
`aa75984a19e65eb8de7c3b6cd3d3b404fdf09e39`. The first train episode failed
before an actor call or environment action. The aggregate failure class is
`AlfworldTextRuntimeError`. The attempted prefix was sealed and the occurrence
ended; the remaining eleven episodes were not attempted.

| Measurement | Observed |
|---|---:|
| Selected train / valid_seen groups | 8 / 4 |
| Attempted train / valid_seen episodes | 1 / 0 |
| Invalid train / valid_seen episodes | 1 / 0 |
| Completed episodes | 0 |
| Actor calls / environment actions | 0 / 0 |
| Completion / tokenizer HTTP POSTs | 0 / 0 |
| Input / output tokens | 0 / 0 |
| Selected valid_unseen groups | 0 |

**Success rate, confidence intervals and model headroom are not estimable.**
The aggregate's zero success counters are not a 0% success result: there were
no completed episodes. The failed outer execution has exit code 2; the later
projection's exit code 0 means only that the sealed evidence could be read and
validated. It does not change the occurrence terminal.

The frozen surface was `B0_STATELESS_NO_LEARNING`, Qwen3.6-35B-A3B-FP8 revision
`95a723d08a9490559dae23d0cff1d9466213d989`, vLLM 0.25.1 image digest
`e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089`, and the
declared NVIDIA GB10. No learning, lesson, revision, or Permit was exercised.

The original live public receipt omitted the nested calibration totals. Its
unchanged bytes are retained alongside the aggregate projection made on
2026-08-30 at `c65bb2a2adf24ce0795a76d5ec2dbbde438599e7`. On 2026-09-06 the
checked-in projector was run again through `hswm-run` against the original
153,600-byte archive on data-01. It revalidated the source, private/public
receipt, selection, start-marker and lease-content joins. All projected
observations and commitments match; only the projection execution identity
and its resulting digest differ. This is same-owner verification.

- [Original frozen protocol](../_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/protocol.v1.json)
- [Prospective selection commitment](../manifests/HSWM_ALFWORLD_B0_SELECTION_2026-08-30.json)
- [Content-addressed evidence receipt](../evidence/EVIDENCE_HSWM_ALFWORLD_B0_CALIBRATION_2026-08-30.json)
- [Original aggregate projection](raw/hswm_alfworld_b0_calibration_2026-08-30/posthoc.public.json)
- [2026-09-06 verification projection](raw/hswm_alfworld_b0_calibration_2026-08-30/reverified.public.json)

The original archive SHA-256 is
`31299aa5061c1cf9e8f2a3ab517c41c9f40ad28426b80c0a46546f1f9740dd9f`.
Private game identities, task contents, traces and the private archive remain
outside Git. Only aggregate projections and wrapper receipts are checked in.
The frozen protocol forbids retry or resume of this occurrence. Any successor
must preserve this failure and bind its changes prospectively before running.

S-5 now has its B0 attempted-occurrence result file, but a usable B0 comparator
ceiling remains unavailable and the B2 result is still absent. S-5 is not
complete. D-3's secondary-comparator status does not reopen the G1 estimand.
G0 remains `NOT_PASSED`; G1 and D-4 held-out behavior were not evaluated.
This is an instrument failure, not evidence for or against HSWM efficacy.
