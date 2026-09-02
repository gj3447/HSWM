# HSWM GE-2/LE-0 standard-entrypoint enforcement

> **Status:** `SECONDARY_AI_ENGINEERING_IMPLEMENTATION / LOCAL_MUTATION_BOUNDARY / LOCAL_RESEARCH_JOB_CONTROL / SCIENTIFICALLY_UNJUDGED`
>
> **Date:** 2026-09-02
>
> **Target authority:** [HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md) and [HSWM Adaptive Research Strategy](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Predecessor:** [GE-2/LE-0 local implementation](HSWM_GRAPH_LOOP_ENGINEERING_IMPLEMENTATION_2026-09-01.md)

## Answer first

The published TypeScript surface no longer exposes a raw durable graph-mutation
port. It exposes a read/stage/snapshot view and one standard
`makeGraphLoopEngineeringFileLayer` composition. A normal caller reaches
canonical graph mutation only through `GraphLoopEngineeringController`'s
`submitDelta` or `restore`, which retain GE-2 snapshot, verifier, intent,
CAS, quarantine, and recovery checks.

The same composition now feeds a real bounded subprocess job runner. It
executes a declared action command and a separately identified verifier command
without a shell, content-addresses schema/grants/declared frozen inputs and
both observations, records retry/stop/escalation through LE-0, and exposes an
executable `hswm-graph-loop-job` entrypoint after package build.

This does not make an exit code an independent outcome, a local control journal
canonical HSWM state, a graph delta a learning admission, or a successful job a
scientific result.

## Conceptual delta

Before this follow-up, GE-2/LE-0 was a controller implementation that a caller
could choose while the public durable runtime also exposed `submit`. The delta
is a capability-shaped package boundary:

```text
public graph view: stage/read/snapshot/history
    + standard GE-2/LE-0 composition
        -> private graph-loop commit seam
        -> predecessor-bound durable journal
```

The standard job path is:

```text
declared action argv and budget
    -> LE-0 trigger + source graph snapshot
    -> action subprocess observation
    -> separately identified verifier subprocess observation
    -> ACCEPT / RETRY / REJECT / ESCALATE
    -> stop, bounded retry, or escalation record
```

`actorId != verifierId` is enforced. That is role separation, not proof that
the verifier is externally independent, correct, or causally identifying.

## Implemented boundary

| surface | enforced behavior | boundary that remains open |
|---|---|---|
| public durable graph API | `CanonicalAtomV2DurableGraphView` omits `submit`; the raw runtime and raw file-layer factory are absent from the package root. | This is an API/module boundary, not hostile same-process isolation, a Permit, or distributed authorization. |
| GE-2 mutation | `submitDelta` and `restore` call a module-private graph-loop commit seam only after the existing source-bound controller checks. | Existing generic test fixtures and schema-specific protected paths remain internal implementation surfaces. |
| DNRD routing diagnostic | Its former `runtime.submit` call is replaced by a named internal diagnostic seam and remains labeled structural-only. | It is not silently promoted to independent-verifier GE-2 research admission. |
| LE-0 non-mutating job | An accepted verifier may now close a loop as `VERIFIED_ACCEPT_NO_GRAPH_DELTA`; retry is budgeted and verifier launch/timeout/truncation escalates with its artifact. | No graph delta, credit, Permit, or learning claim is inferred automatically. |
| executable wrapper | `canonical-atom-v2-graph-loop-job-process.ts` accepts canonical JSON stdin, reads exact schema/grants plus one or more regular declared frozen-input files, content-addresses them into a manifest, builds the protected layer, and runs declared argv directly with `shell: false`. | Bound input bytes and declared role separation do not prove evaluator independence, outcome truth, or causal efficacy. |
| frozen-DGX profiles | The checked-in Q1, MI, and MI-2 profiles materialize their existing runner and separate verifier module commands without changing frozen sources. Q1 uses a new non-producer verifier bridge; MI/MI-2 keep their existing verifier CLI. | These are future-launch integrations, not a rerun, requalification, or retroactive rewrite of hash-bound occurrences. DNRD and other active families still require their own registered adapters. |

The current standard caller uses the package root exports
`makeGraphLoopEngineeringFileLayer`, `GraphLoopEngineeringController`,
`CanonicalAtomV2DurableGraphView`, and
`makeGraphLoopResearchProcessRunnerLayer`. The executable bridge is installed
as `hswm-graph-loop-job` by the package manifest after:

```bash
cd src/hswm/effect-runtime
npm run build
```

The bridge accepts a canonical-JSON request that names absolute durable/control
roots, exact schema and grants files, one bounded action argv, and one bounded
verifier argv. It also requires declared frozen regular-file inputs and stages
a content-addressed input manifest. It passes only a minimal inherited
environment plus declared variables, never invokes a shell, caps combined
stdout/stderr, records timeout or launch failure, and provides the action and
verifier input-manifest descriptor plus the verifier action-artifact descriptor
through environment variables.

For the registered future DGX launches, use the profile materializer before the
Node job process:

```bash
uv run python -m hswm.experiments.graph_loop_job_profiles \
  --binding /absolute/job-binding.json \
  | hswm-graph-loop-job
```

`_research/loop_jobs/HSWM_STANDARD_RESEARCH_JOB_PROFILES.v1.json` binds the
following action/verifier role pairs: Q1
`live_experiment`/`dgx_q1_le0_verifier`, MI
`experiment`/`independent_verifier`, and MI-2
`experiment`/`independent_verifier`. Each is deliberately one-shot
(`maximumAttempts = maximumActions = 1`), preserving the frozen protocol's
no-resume/no-replacement rule. A verifier exit `0` only means that its protocol
reader produced a bounded verdict; its content-addressed stdout retains whether
that verdict was inconclusive, falsifying, unavailable, or otherwise
non-successful.

## Research-runner adoption rule

New standard research jobs should enter through this wrapper rather than invoke
a graph mutation port or ad hoc retry loop directly. The Q1/MI/MI-2 registry is
the first concrete adoption set. Existing DGX/DNRD frozen protocol sources are
intentionally not rewritten: their byte/hash closure and their pre-existing
verifier contracts remain historical evidence. A new launch wrapper calls them
as the action and their already separate verifier as the verifier command.

This is a deliberately staged migration rather than a false claim that every
historical runner has already been rerun or independently qualified. The next
adoption gate is to register each remaining active launcher (including DNRD and
non-DGX experiment families) with exact action/verifier argv, frozen-input
identity, budgets, control-journal root, and a tested recovery procedure before
it is used for a new scientific occurrence.

## Verification

The checked-in tests establish only bounded engineering facts:

1. The public package root has no raw durable runtime or raw file-layer export.
2. Production GE-2 and local diagnostic sources no longer invoke
   `runtime.submit(...)` directly.
3. A real Node action subprocess and a distinct verifier subprocess execute
   under LE-0; one retry is persisted before an accepted stop.
4. Verifier rejection stops and verifier timeout escalates without a hidden
   retry; their observations remain content-addressed.
5. The executable job-process entrypoint constructs the protected file runtime,
   binds declared frozen input files, and completes an action/verifier job.
6. Q1, MI, and MI-2 profile materialization resolves the actual historical
   runner/verifier module pairs with a one-shot budget; the Q1 bridge preserves
   the original independent-verifier terminal rather than promoting it.

These tests are not an external experimental occurrence, a result receipt, a
causal-credit qualification, or evidence that HSWM efficacy occurred. In
particular, the G0–G6 order and the independent-outcome/remove/restore demands
of `GL-1` remain unchanged.
