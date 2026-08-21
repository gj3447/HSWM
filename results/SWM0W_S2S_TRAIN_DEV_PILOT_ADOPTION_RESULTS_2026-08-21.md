# SWM-0W-S2S train/dev pilot adoption

Date: 2026-08-21

Status: `ENGINEERING_ADOPTION_CANDIDATE_ONLY_UNJUDGED`
Scientific verdict: `NO_EFFICACY_OR_CHRONOLOGY_VERDICT`

## Outcome

The fixed public train/dev roster completed once on GitHub Actions at source
commit `75686549b1f6c65aea87ebd0f912a6e62909445a`. All 27 stage-two cells were
fit and exactly replayed before the deterministic selector ran. The adopted
learning rates are:

| arm | selected learning rate | selection basis |
|---|---:|---|
| T16 | `0.003` | lowest exact mean normalized dev loss, then worst draw, then numeric rate |
| P_CAP18 | `0.001` | all three rates tied at epoch zero; fixed lower-rate tie-break |
| DS870 | `0.001` | all three rates tied at epoch zero; fixed lower-rate tie-break |

Every adopted arm keeps initializer seed `0`, `max_updates=300`, patience `50`,
`min_delta=1e-9`, gradient clip `5`, and the frozen Adam constants. The exact
protocol-config receipt is
`a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb`.
Pilot draws `0..2` under seed commitment
`0370316c9f9388a5f37ba26c934a5efaed08b828789f392bf702da600cc88dce`
are excluded from future evidence. A future task with the same semantic law is
still retained when its seed provenance differs.

This result used only complete train/dev partitions. It did not open a future
beacon, construct confirmatory tasks, enumerate a confirmatory test split, or
produce an efficacy verdict.

## Important control boundary

P_CAP18 returning epoch zero is consistent with the exact recipient-star
pair-null construction. DS870 also returned epoch zero for every draw and every
candidate rate: post-update dev loss never beat the zero-output checkpoint.
Therefore the future essential `Q/B/R` gate remains admissible, but the optional
DS-derived “matched-budget compact competitive” phrase is prohibited for this
protocol. A meaningful DS comparison would require a new disclosed pilot and a
new adoption; it cannot be rescued after confirmatory outcomes are visible.

Two of the three selected T16 draws reached the common update cap. The adopted
configuration is consequently a fixed-budget estimator, not a convergence or
globally optimal learning-rate claim.

## Runtime projection

The successful job ran for `1,361 s`. The exact runtime projection records:

- stage-one 27-cell fit+replay: `132,795,963,591 ns`;
- admission projection: `3,983,878,907,730 ns`, below the fixed
  `7,200,000,000,000 ns` pilot admission limit;
- stage-two 27-cell fit+replay: `1,204,235,087,351 ns`;
- selected-rate nine-cell fit+replay: `424,904,259,742 ns`;
- observed process high-water RSS: `171,108 KiB`.

These are nondeterministic telemetry bound for provenance only. They do not
change task count, thresholds, optimizer updates, or the scientific reducer.
The confirmatory timeout/archive policy remains `PENDING_NOT_CHOSEN` and must be
frozen before source commit A and preregistration.

## Operational attempts

Run `32441694463` at commit `2242ed6` failed before task preparation because
the exact managed Python interpreter had not yet been materialized. Its strict
artifact was `RUN_NOT_COMPLETED` with zero tasks, cells, selections, or future
randomness, so it is a disclosed pre-fit operational `VOID`, not scientific
evidence. Commit `7568654` added the explicit managed-Python installation.

Run `32442437970` was attempt 1 and the sole workflow-dispatch run for that
repaired source SHA. Job `96655652099` and artifact `9433344546` completed
successfully. The GitHub-hosted runner/control plane remains an operational
trust boundary; the offline receipt alone does not authenticate GitHub.

## Durable evidence

The five-file replay bundle is at
[`artifacts/swm0w_s2s/pilot_adoption/32442437970/`](../artifacts/swm0w_s2s/pilot_adoption/32442437970/).

| file | SHA-256 |
|---|---|
| `pilot_artifact.zip` | `b5a29cab118737f48083613f45a34212ae73f15a1321a597947d838c077f63c5` |
| `github_run.json` | `80246cfdcdaa47c603c66d51d1d6dbaf5ef385d31474aa2ce0a8d624d03d049a` |
| `github_job.json` | `e3ea8f05f4aa2b9c8199f6c30d60df9ee70c11f6e41abb9f3c69e0fcde701a3b` |
| `github_artifact.json` | `772f53455dc5ea82f07bb8add15d56a2c117ce36a053ebabdb90a120d069a12d` |
| `pilot_adoption_receipt.json` | `fb34e5e9533409810f616815edc8565b244b5067a9bb70f643eb42d8bd044a78` |

The adoption receipt self-hash is
`97a752fea5ae45a311a2e8cf2376b391d76a8269dbab20f60688f543bcc5dea1`.
Validation requires all five exact files: the receipt is not independently
authoritative. The gate design remains
[`HSWM_SWM0W_S2S_GATE_2026-08-20.md`](../docs/research/HSWM_SWM0W_S2S_GATE_2026-08-20.md).
