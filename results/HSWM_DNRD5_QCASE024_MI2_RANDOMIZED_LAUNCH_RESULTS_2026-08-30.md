# HSWM-DNRD-5 QCASE-024 MI-2 randomized-launch result

- Date: `2026-08-30`
- Machine: DGX execution host `edgexpert-e229`
- Served model: `qwen3.6-35b-a3b`
  (`Qwen/Qwen3.6-35B-A3B-FP8`, revision
  `95a723d08a9490559dae23d0cff1d9466213d989`)
- Runtime: vLLM `0.25.1`, NVIDIA GB10, compute capability `12.1`
- Frozen terminal:
  `LIVE_COMPLETE_DGX_QCASE024_MI2_RANDOMIZED_LAUNCH_EXPERIMENT`
- Frozen family label: `FINITE_RANDOMIZED_NO_ARM_ASSOCIATION_DETECTED`
- DNRD-5 causal effect: `NOT_EVALUATED`
- Source-A disposition: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`
- Retry, resume, replacement, refill, or reuse of this plan: forbidden

## Result first

MI-2 completed its frozen twelve-pair, twenty-four-fresh-launch randomized
design. Each launch made exactly two serial requests: `R001` was the registered
fresh-launch outcome and `R002` was a within-process diagnostic only. All 48
POSTs succeeded, no retry occurred, all 24 service incarnations were distinct,
and all 24 launches were torn down and sealed before the next launch.

Neither registered endpoint rejected at the Bonferroni endpoint threshold
`0.025`:

| Registered endpoint | Observed statistic | Exact inclusive tail | Decision |
|---|---:|---:|---|
| Exact-content total variation | `5` | `120/400 = 0.30` | Do not reject |
| Fixed row-20 branch-margin sum difference | `1.1249996423721318` | `236/400 = 0.59` | Do not reject |

The resulting family label is
`FINITE_RANDOMIZED_NO_ARM_ASSOCIATION_DETECTED`. This is a finite randomized
non-detection. It is **not** evidence that the async setting has exactly zero
effect, an equivalence result, a determinism result, or proof of the registered
sharp null.

## Registered design and execution closure

The plan was frozen and published before any MI-2 target call. The accepted
raw-CSPRNG seed artifact selected zero-based schedule index `33` from the
predeclared 400-schedule reference set. Pair orientations `P01..P12` were:

```text
ED, ED, DE, ED, DE, DE, DE, ED, DE, ED, ED, DE
```

There were six `ED` and six `DE` pairs, with three `ED` pairs in each temporal
half. Every pair contained one async-enabled and one async-disabled launch.
Consequently the registered primary sample contained twelve enabled and twelve
disabled `R001` fresh-launch units. The 24 `R002` responses never entered the
randomization sample size or either primary endpoint.

The one-time consumption record was durably written before the first target
launch. Its SHA-256 is
`129d44e45d64bdf449a9a30533c7e1247d1810ccf4a064eb5f51ae63a6688ade`.
The final ledger contains 172 chained records:

| Record type | Count |
|---|---:|
| Global quiescence / plan consumption / start marker | `1 / 1 / 1` |
| Launch start / request START / successful TERMINAL | `24 / 48 / 48` |
| Launch teardown / launch seal / run seal | `24 / 24 / 1` |

The exact ledger SHA-256 is
`1fbf880b1993290dd65b341478be82c644f35c9beecd295275dbff2e65469256`;
its final chain record is
`4111635b2e1b489582975902593ded02f1371022aaceeaa07659a897150c77ac`.
The content-addressed store contains 274 reachable blobs totaling 5,289,357
bytes. Its manifest SHA-256 is
`9bc0076d334b3a821a02b114963079d7f5e00822cba69283ecf46264a4840443`.

## Primary exact-content endpoint

The 24 primary `R001` responses occupied five exact assistant-content digest
categories. Counts were:

| Content digest | Bytes | Enabled | Disabled |
|---|---:|---:|---:|
| `14bc62d6…262a31` | 234 | 9 | 4 |
| `fa0f987e…f19a22` | 194 | 3 | 3 |
| `00f8bf62…607e02` | 214 | 0 | 3 |
| `a90f593d…41aac` | 206 | 0 | 1 |
| `6f3e88a1…f1615a` | 234 | 0 | 1 |

Thus enabled launches had two observed categories and disabled launches had
five. That descriptive asymmetry produced registered total-variation statistic
`T_content = 5`. Holding the 24 position-indexed outcomes fixed, 120 of the 400
allowed assignments had a statistic at least this large. The exact upper-tail
probability is therefore `0.30`, well above `0.025`.

The two common contents were already preserved by Q1 and MI-1. The three new
primary contents and the one new `R002`-only diagnostic content are preserved
in [`raw`](raw/). Exact content categories are byte-level observations; answer
correctness and semantic equivalence were not registered and were not judged.

## Primary fixed branch-margin endpoint

For every primary response, the frozen verifier checked the already selected
MI-1 row-20 score surface after the same 52-byte prefix. It computed
`logp(" indicates") - logp(" explicitly")` using the exact decimal strings in
the retained processed-logprob traces. The 24 values had this distribution:

| Margin | Count |
|---:|---:|
| `-0.8749998807907106` | 3 |
| `-0.3750000000000000` | 13 |
| `-0.2500000000000000` | 1 |
| `-0.125000000000000` | 1 |
| `0.2499998807907105` | 6 |

The enabled-arm sum was `-2.6250003576278685`; the disabled-arm sum was
`-3.7500000000000003`. Their registered absolute difference was
`1.1249996423721318`. Of the 400 allowed assignments, 236 had an absolute
difference at least this large, giving exact upper-tail probability `0.59`.
The score surface is an observable model output, not a calibrated probability
claim or identification of a kernel, reduction, Gated DeltaNet, or scheduler
mechanism.

## Serial diagnostic only

`R001` and `R002` assistant-content bytes matched within 21 of 24 launches.
They differed at launch indices `5`, `16`, and `22`; all three happened to be
async-disabled launches. This was a preregistered descriptive diagnostic, not
a third endpoint. It cannot change the primary family label, increase the
randomization sample size, or support a post-hoc arm-effect claim.

## Frozen provenance and independent verification

The source and independent verifier were frozen at commit
`728cee961bebf799999b364042e7088a794b735e`, tree
`afcb9714d30a17e85f9668948813269f0bfb4318`. First-attempt source CI run
[`33279010396`](https://github.com/gj3447/HSWM/actions/runs/33279010396)
completed all eight jobs successfully. Its strict receipt SHA-256 is
`a00a54c8ddbaada90060a26799ba6335353d043e0716f1e0d0a059f96c0a63a6`.

The immutable freeze binds plan SHA-256
`e05f3f09bde04f4dae1ddced7c2c730f26b0d1236e3e7b94f7547898bb9b8702`,
closure-manifest SHA-256
`5a0b901379c8cd8455867a66027b2d629f8ed33dc5429d2823f5a25473b86105`,
start-marker SHA-256
`7409e89df7b1a27f2067c649ddec7e54989ccaace7bf9d021e2280608a61ad95`,
schedule-seed artifact SHA-256
`c90c06dc8b8eaf54a214f60c25c452c04b91b5a856b1694d9638d68155f40dc4`,
and frozen verifier-source SHA-256
`e5adeea5255a5292d82b0029549fae18b59c7b1c3e860e4a2a8805dd480f57c0`.

Publication commit `0bf209e2a37a017684acc638f35d0fdb3e11ae29`, tree
`8356e50d258891c37bf775d25036e174c896ec7e`, introduced no executable
dependency change relative to the source identity. First-attempt publication
CI run
[`33280646616`](https://github.com/gj3447/HSWM/actions/runs/33280646616)
completed all eight jobs successfully. Its strict receipt SHA-256 is
`cac5b0f8741eda853324fe579e7c437f4da5028cfd057c8a702f7b1d3ffe5faa`.

Live run `dgx-qcase024-mi-2-live-0bf209e-001` ran from
`2026-08-29T23:32:48Z` through `2026-08-30T02:22:45Z`. Its wrapper receipt
SHA-256 is
`90838537a0783a88b166505f5413d7b84fc846cd638a3403be89aac3024e0d6f`;
the 5,795,840-byte durable archive SHA-256 is
`c0fea9cf07f6e3029257e22a794393030a3ee881ec1db5d0724b074e87f2214f`.

Independent run `dgx-qcase024-mi-2-verify-0bf209e-001` executed the frozen
producer-independent verifier against the original absolute evidence root and
external durable consumption registry. It reconstructed the complete terminal,
ledger chain, all blob and boundary checks, the 400 schedules, both endpoint
statistics and tails, and the same family label. Its output SHA-256 is
`8a949f79b715602270bd7b960189c53aabcb808373b069f7c982a90b016e97f5`,
wrapper receipt SHA-256 is
`5ce7b62e7e698f609ac02775731cf5fbc3db04aedc80e46b2082a9d68bb47953`,
and 10,240-byte archive SHA-256 is
`63c19f2f4d06e4615f24908d1be93ba3135ef9df304c2ace15d9ecc9b9b62243`.

The consumption record intentionally binds the original absolute node-local
evidence-root path. A copied evidence tree at a different path cannot satisfy
the verifier's original-path equality check and therefore yields
`VOID_DGX_QCASE024_MI2_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH`; this is
a portability-boundary refusal, not a change to the sealed live-run terminal.
The copied archive's hashes and recorded remote verifier output were inspected
against the authoritative result. It is an inspection copy only; the frozen
verifier's complete verdict is asserted only for the original path-bound
evidence root and durable external registry.

## Advanced-model boundary

This experiment used a revision- and digest-pinned open-weight inference
configuration: Qwen3.6 35B-total/3B-active FP8 on NVIDIA GB10. It deliberately
retained the MI-1/Q1 comparison boundary: vLLM `0.25.1`, driver `580.126.09`,
32,768-token text-only path, one sequence, eager mode, disabled prefix cache,
and 50% GPU-memory utilization. The only arm difference was the declared
`--async-scheduling` versus `--no-async-scheduling` flag.

This is not a SOTA quality, throughput, long-context, tool-use, or multimodal
study. The frozen stack was retained for causal comparability, not because it
was the newest available stack. Updating the model, runtime, driver, precision,
or backend inside MI-2 would have changed the treatment contrast. A current-
stack transport study must be separately frozen and must not be retroactively
mixed into this result.

## Scientific interpretation and next research

MI-2 closes one useful finite question: under the registered assignment and
this exact execution window, neither exact output clustering nor the fixed
token-score branch margin produced a detectable arm association. The result
therefore gives no scientific basis for declaring the async flag to be the
cause of QCASE-024 variation. It also gives no basis for declaring it harmless.

The disabled arm's five observed primary content categories versus the enabled
arm's two, and the three disabled-only within-launch mismatches, are
prospective hypotheses only. They were not separate registered endpoints and
must not be promoted from description to discovery. A fresh replication could
predeclare a dispersion or within-launch-instability endpoint, a scientifically
meaningful equivalence margin, and a larger launch budget. It must use a new
random draw and single-use plan.

More importantly, inference-byte stability is not HSWM learning. Further HSWM
science should move back to a randomized outcome-to-credit-to-revision-to-fresh-
behavior experiment with sham/no-update controls and predeclared behavioral
endpoints, treating launch/runtime variation as measurement noise. Exactness
qualification and a current-stack transport study can remain separate support
studies rather than being counted as macro-neural learning progress.

## HSWM and FCL boundary

HSWM remains one token-native LLM-function macro-neural network whose evolving
hypergraph jointly plays the roles of living harness, world model, and
continuous learner. This experiment, the repository ontology, MCP interfaces,
and the live KG are bounded evidence projections, not HSWM cognition or
learning.

MI-2 does not test or change any of the eight FCL laws, same-rule recursive
HSWM-of-HSWMs composition, outcome-bound causal learning, consciousness,
selfhood, or scale-invariant causal closure. Source A remains refused and the
DNRD-5 causal effect remains `NOT_EVALUATED`. The scientific status remains
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`; the live KG is not
mutated.
