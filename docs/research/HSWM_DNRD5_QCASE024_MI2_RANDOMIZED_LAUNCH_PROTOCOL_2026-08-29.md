# HSWM-DNRD-5 QCASE-024 MI-2 randomized-launch protocol

- Date: `2026-08-29`
- Instrument: `DNRD5-QCASE024-MI-2-RANDOMIZED-LAUNCH`
- Status: `SOURCE_IMPLEMENTATION_COMPLETE / NO_MI2_TARGET_CALLS`
- Scope: post-result-selected, finite, randomized mechanism diagnostic
- Predecessor result: `DNRD5-QCASE024-MI-1-CONTENT-V4 / BOTH_ARMS_VARIATION`
- DNRD-5 causal effect: `NOT_EVALUATED`
- Source-A disposition: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`

## Result sought and conceptual delta

MI-1 v4 established a narrow negative result: disabling vLLM asynchronous
scheduling was not sufficient to guarantee assistant-content byte stability
across the two observed fresh disabled launches. Both arms produced the same
two exact contents, while every four-request launch was internally stable.
That ABBA diagnostic did not randomize treatment, had only four launch units,
and did not evaluate an async-setting causal effect.

MI-2 changes the experimental unit and the assignment mechanism. A fresh
server launch, not a repeated request within one process, is the unit. Twenty-
four fresh launches are arranged in twelve adjacent matched pairs. Each pair
contains one `ASYNC_ENABLED` launch and one `ASYNC_DISABLED` launch, and their
order is assigned before outcomes by a recorded raw-CSPRNG randomization draw.
The first response from each launch supplies the two registered primary-family
endpoints. A second serial response is retained only as a within-process
repeatability diagnostic.

This is a bounded mechanism experiment, not a new HSWM architecture. It does
not change HSWM's target identity, the eight FCL laws, same-rule recursive
HSWM-of-HSWMs composition, or the live KG.

## Frozen design candidate

The source implementation must refuse any plan that differs from all of the
following before the preregistration is published:

1. There are exactly twelve adjacent pair IDs, `P01` through `P12`, and exactly
   twenty-four fresh-server launch positions.
2. Every pair contains one enabled launch and one disabled launch. Exactly six
   pairs have order `ED` and six have order `DE`.
3. Pairs `P01..P06` contain exactly three `ED` orders, and pairs `P07..P12`
   independently contain exactly three `ED` orders. This yields exactly
   `C(6,3) × C(6,3) = 400` allowed schedules, balances first-launch arm within
   both temporal halves, and fixes the randomization reference set.
4. A fresh 32-byte cryptographic random draw is generated before any MI-2
   target call. Interpreted directly as an unsigned uniform 256-bit integer
   `x`, it is accepted only when
   `0 <= x < floor(2^256 / 400) * 400`; the selected index is then exactly
   `x mod 400`. A rejected raw draw is not a schedule candidate and causes a
   fresh independent draw, never a hash-derived retry. Conditional on faithful
   use of independent CSPRNG draws, the 400 lexicographically ordered schedules
   therefore have exactly equal selection probability without modulo bias. The
   closure binds the accepted raw draw, its SHA-256 artifact binding, the
   selected index, and the resulting schedule before publication. It does not
   bind an entropy source, certify any discarded raw draw, or prove that an
   operator did not discard an accepted draw.
   The source implementation and independent verifier are bound to the same
   clean published Git commit and tree; their separately recorded successful-CI
   receipts remain content-addressed provenance, not an alternative source
   identity.
5. Every launch uses a new container/process/network-namespace identity and
   fresh writable Hugging Face and compile-cache directories. No server or
   writable cache is reused across launch units.
6. Every launch makes exactly two serialized POSTs: `R001` is the primary
   fresh-launch outcome and `R002` is a technical repeat diagnostic. A
   complete experiment therefore contains 24 primary outcomes and 48 total
   POSTs. `R002` never increases the causal sample size.
7. There is no retry, refill, replacement, resume, early stopping, or
   outcome-conditioned extension. The one-time plan is durably burned before
   the first target launch.
8. Every launch teardown must show the target container removed, no target
   listener, no GPU compute process, and a recorded bounded GPU-state
   projection before the next launch may begin. Launch and teardown times,
   pair index, absolute position, parity, and prior arm are retained. These are
   carryover diagnostics and mitigations, not proof of no interference.

The request bytes, response schema, checkpoint revision, snapshot manifest,
container image digest, model identity, engine seed, eager execution,
single-sequence setting, disabled prefix cache, processed-logprob mode, GPU,
driver, and all non-arm server arguments remain pinned to the completed MI-1
v4 boundary. The two arm identities may differ only in the explicit
`--async-scheduling` versus `--no-async-scheduling` setting and its recorded
boolean projection. Updating vLLM, the driver, model precision, backend, or
checkpoint in this experiment would confound the intended comparison and is
forbidden.

This frozen MI-1-comparable runtime is a historical causal-comparison boundary,
not a claim that the model, vLLM release, driver, or DGX configuration is
current, frontier, or SOTA at execution time. Any current-stack modernization
or SOTA comparison requires a separately frozen study and cannot be folded
into MI-2.

## Registered primary family and exact randomization inference

Only `R001` from each launch enters a primary endpoint. The family contains two
outcome functions fixed before schedule publication. Each is tested against
the same 400 restricted assignments with an inclusive exact upper tail.

### Endpoint A: exact-content total variation

The first outcome is the SHA-256 digest of retained exact assistant
`message.content` UTF-8 bytes. The test treats distinct digests as distinct
nominal categories; it makes no semantic-equivalence judgment or answer-field
reduction. Equality is equality of recorded SHA-256 digest categories, not a
mathematical proof of byte equality in the event of a hash collision.

For every observed content category `c`, let `N_E,c` and `N_D,c` be its counts
among the twelve enabled and twelve disabled primary outcomes. The registered
statistic is the unnormalized total-variation count

```math
T_{\mathrm{content}} = \frac{1}{2}\sum_c
\left|N_{E,c}-N_{D,c}\right|.
```

This endpoint detects arm-wise clustering of identical recorded digest
categories and, absent a SHA-256 collision, byte-identical outputs. If all 24
content digests are unique, its statistic is invariant over all schedules and
its p-value is `1`; it cannot detect a systematic arm difference expressed only
through mutually unique strings.

### Endpoint B: fixed token-score branch margin

MI-1 v4 located the two observed exact trajectories' first differing emitted
token at zero-based completion row `20`, after an identical 52-byte prefix. The
second endpoint therefore uses that already observed score surface without
selecting a position from MI-2 outcomes. The verifier requires:

- the bytes emitted by rows `0..19` to have length `52` and SHA-256
  `073d99db9361985aa3706af40d268a21bd9bb68fd608dd00a2b51ff3857b3bdf`;
- row `20` to contain exactly one top-20 candidate with token bytes
  ` indicates` (SHA-256
  `55fde3431b756dfca90d8b612bb85fd7d7a282438be28c060af78d5081c0470e`)
  and exactly one with token bytes ` explicitly` (SHA-256
  `d6a745a584f5f0b57eddf076426e31a457cf068a78b2caa9d0cc3778f354d697`);
- both candidate scores to be finite exact decimal values in the frozen full
  processed-logprob trace.

The checked-in MI-1 independent reduction records both candidates as available
at this row.  In its two observed trajectories, the corresponding
`indicates-minus-explicitly` margins were `0.2499998807907105` and `-0.375`.
Those predecessor values justify observability of the fixed score surface; they
are not MI-2 outcomes, effect estimates, or thresholds.

For launch `i`, define

```math
M_i = \log p_i(\text{` indicates`})
      - \log p_i(\text{` explicitly`}),
```

and, because both arms contain twelve launches, use the exactly represented
sum-difference statistic

```math
T_{\mathrm{margin}} = \left|
\sum_{i:A_i=E} M_i - \sum_{i:A_i=D} M_i
\right|.
```

Here “exactly represented” means exact decimal arithmetic over the score
strings serialized by the pinned provider. It is not a claim that the
underlying floating-point kernel computes mathematically exact or calibrated
log probabilities.

A missing row, changed prefix, absent/duplicated candidate, nonfinite score, or
trace misalignment makes the registered family unavailable and the run
inconclusive. There is no content-only fallback after seeing outcomes.

### Family decision

Holding all twenty-four position-indexed outcomes fixed, the verifier assigns
arms under every allowed schedule and recomputes both statistics. For endpoint
`k`, the exact inclusive upper-tail probability is

```math
p_k = \frac{\#\{a \in \mathcal{A}:T_k(a) \geq
T_{k,\mathrm{obs}}\}}{400}.
```

Here `A` is exactly the two-half-stratified schedule set above. Bonferroni
allocates endpoint alpha `0.025` to each test, bounding family alpha by `0.05`.
There is no asymptotic approximation, mid-p adjustment, endpoint selection, or
treatment of `R002` as an independent unit.

- If either registered endpoint has `p_k <= 0.025`, the finite family label is
  `FINITE_RANDOMIZED_ARM_ASSOCIATION_DETECTED`.
- Otherwise, if both endpoints are available, the family label is
  `FINITE_RANDOMIZED_NO_ARM_ASSOCIATION_DETECTED`.

The second label does not mean zero effect, equivalence, determinism, or proof
of the sharp null. At most, the first label is evidence against the sharp
schedule-invariance null that all 24 position-indexed R001 outcomes are
unchanged under every permitted whole-schedule assignment.
`FINITE_RANDOMIZED_ARM_ASSOCIATION_DETECTED` is a finite test decision, not
discovery of a direct async effect. Only conditional on consistency and no
interference can it be read as finite evidence of an assignment effect of the
complete declared async CLI configuration. It does not separate a direct arm
effect from pair carryover, identify a provider-internal scheduler mechanism,
give an effect direction by itself, or generalize to other prompts, models,
hardware, runtime versions, or time periods.

No population outcome model or equivalence margin is registered, and twelve
launches per arm are not claimed to provide a general small-effect guarantee.
Global arm-complement symmetry maps every allowed schedule to a distinct
allowed schedule with the same absolute statistic. Therefore every inclusive
upper-tail count is even and at least two: the smallest attainable exact tail
is `2/400 = 0.005`, not `1/400`. That grid is not the same thing as power. A
family non-detection cannot be converted into an upper bound on an async
effect.

## Secondary diagnostics

All secondary analyses are descriptive and cannot change the primary label:

- `R001` versus `R002` assistant-content equality within each launch;
- full processed-logprob-trace SHA-256 equality within and across launches;
- content and trace categories by pair, absolute launch position, first versus
  second position in a pair, and early versus late half;
- first differing byte and other aligned token-score surfaces when exact
  contents differ;
- server fingerprint, launch/teardown time, GPU temperature, power, SM clock,
  and performance state retained as bounded runtime observations.

The two exact score trajectories discovered after MI-1 publication motivate
the fixed MI-2 branch-margin endpoint and full trace retention. They remain
exploratory predecessor evidence and are not retroactively promoted to an MI-1
registered endpoint. None of the descriptive diagnostics can rescue a primary
family non-detection or change its label.

The randomization p-values are exact for the registered assignment mechanism
under the sharp null that all 24 position-indexed R001 outcomes are unchanged
by arm assignment and by assignments at other launches. They are not a test of
the weaker equality-of-marginal-distributions null and do not estimate an
average causal effect. Fresh processes, caches, quiescence checks, adjacency,
and half-stratification reduce known contamination paths but cannot establish
that physical-GPU, thermal, allocator, host, or other carryover is absent.

## Failure, void, and terminal boundaries

A complete scientific reduction requires all 24 scheduled fresh launches, all
48 serialized responses, all exact content and trace blobs, and every
pre/post/final boundary attestation. A transport, provider, content, trace, or
qualification failure consumes its scheduled slot and seals the plan
inconclusive without retry or replacement. A plan, schedule, identity,
ordering, hash-chain, blob, publication, or boundary-integrity breach is void.
No primary p-value is emitted for an incomplete or void run.

Allowed terminal classes are:

- `LIVE_COMPLETE_DGX_QCASE024_MI2_RANDOMIZED_LAUNCH_EXPERIMENT`;
- `INCONCLUSIVE_DGX_QCASE024_MI2_INCOMPLETE_LAUNCHES`;
- `INCONCLUSIVE_DGX_QCASE024_MI2_REQUIRED_CONTENT_OR_TRACE`;
- `VOID_DGX_QCASE024_MI2_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH`.

The independent verifier must reconstruct the schedule from the frozen
randomization material, validate every content-addressed blob and ledger link,
recompute both statistics and their family decision across all 400 schedules,
and reproduce the terminal and result label without network access.

No additional user echo or hash-ratification message is required to freeze or
run this bounded preregistration. The required authorization boundary is the
checked-in, clean, successful-CI publication plus its write-once local freeze;
neither substitutes for the scientific limitations stated below.

## Scientific and HSWM boundary

MI-2 was selected after observing Q1 and MI-1. It is a newly preregistered
randomized follow-up, confirmatory only relative to its frozen finite null and
analysis family; it remains post-selection at the wider program level. It is
not a Q1 retry, a population repeatability estimate, a DNRD-5 300-block
occurrence, Source-A qualification, or evidence of HSWM outcome-bound causal
learning.

HSWM remains one token-native LLM-function macro-neural network whose evolving
hypergraph jointly plays living-harness, world-model, and continuous-learner
roles. This protocol, its code, the repository ontology, and MCP/KG projections
are bounded evidence instruments and interfaces, not HSWM cognition. The eight
FCL laws and cognition-bearing same-rule recursive HSWM-of-HSWMs composition
remain preserved and untested here. Consciousness, selfhood, and scale-
invariant causal closure remain unjudged. The program status therefore remains
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`.
