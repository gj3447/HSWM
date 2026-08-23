import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

import { expect, it } from "@effect/vitest"
import {
  Cause,
  Deferred,
  Effect,
  Either,
  Exit,
  Fiber,
  Layer,
  Ref,
  TestClock
} from "effect"
import { afterAll, beforeAll, describe, vi } from "vitest"

import {
  S2S_GITHUB_API_VERSION,
  S2SGitHubObservationError,
  S2SGitHubObserver,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  observeS2SGitHubWorkflowRunsForHead,
  type S2SGitHubApiResponseProvenance,
  type S2SGitHubObservation,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection,
  type S2SGitHubWorkflowRunsProjection
} from "../src/s2s-live-github.js"
import { makeS2SStageArtifactReadsLiveLayer } from "../src/s2s-live-artifact.js"
import {
  S2SCurrentInvocation,
  inspectS2SCurrentInvocationAuthority,
  makeS2SCurrentInvocationTestLayer,
  type S2SCurrentInvocationAuthority,
  type S2SCurrentInvocationEvidence
} from "../src/s2s-invocation.js"
import {
  inspectS2SRegistrationCommitAuthority,
  inspectS2SRegistrationWorkflowManifestBinding,
  type S2SRegistrationCommitAuthorityEvidence,
  type S2SRegistrationWorkflowManifestBinding
} from "../src/s2s-preregistration.js"
import {
  S2S_CURRENT_RUN_BRACKET_TIMEOUT_MILLIS,
  S2S_CURRENT_RUN_REPLAY_MAX_RAW_BYTES,
  S2SCurrentRunStage,
  inspectS2SCurrentRunStageAuthority,
  makeS2SCurrentRunStageAuthorityLiveLayer,
  probeS2SRunAuthorityAcquisitionForTest,
  snapshotS2SCurrentRunReplay
} from "../src/s2s-run-authority.js"
import {
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  type S2SConfirmatoryJobStage
} from "../src/s2s-workflow-contract.js"
import {
  makeS2SRegistrationAuthorityFixture,
  type S2SRegistrationAuthorityFixture
} from "./support/s2s-authority-fixtures.js"

const RUN_ID = 98_765_431
const CREATED_AT = "2026-08-21T03:10:00Z"
const CREATED_AT_UNIX_SECONDS = Date.parse(CREATED_AT) / 1_000
const INVOCATION_CAPTURED_AT = CREATED_AT_UNIX_SECONDS + 20
const DEFAULT_OBSERVATION_TIMES = Object.freeze([
  INVOCATION_CAPTURED_AT + 1,
  INVOCATION_CAPTURED_AT + 2,
  INVOCATION_CAPTURED_AT + 3,
  INVOCATION_CAPTURED_AT + 4
] as const)
const DEFAULT_REQUEST_IDS = Object.freeze([
  "RUN-AUTHORITY:RUN-START",
  "RUN-AUTHORITY:JOBS",
  "RUN-AUTHORITY:RUNS-FOR-HEAD",
  "RUN-AUTHORITY:RUN-END"
] as const)
const UTF8_ENCODER = new TextEncoder()
const RESPONSE_ETAG = `W/"${"e".repeat(64)}"`

interface PolicyInput {
  readonly registration: S2SRegistrationCommitAuthorityEvidence
  readonly invocation: S2SCurrentInvocationEvidence
  readonly workflowBinding: S2SRegistrationWorkflowManifestBinding
  readonly runStart: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
  readonly jobs: S2SGitHubObservation<S2SGitHubWorkflowJobsProjection>
  readonly runsForHead: S2SGitHubObservation<S2SGitHubWorkflowRunsProjection>
  readonly runEnd: S2SGitHubObservation<S2SGitHubWorkflowRunProjection>
}
type LayerRequirements<Value> = Value extends Layer.Layer<
  infer _Success,
  infer _Failure,
  infer Requirements
>
  ? Requirements
  : unknown
type ProductionLayerRequirements = LayerRequirements<
  ReturnType<typeof makeS2SCurrentRunStageAuthorityLiveLayer>
>
const PRODUCTION_LAYER_IS_CLOSED: [ProductionLayerRequirements] extends [never]
  ? true
  : false = true
const PRODUCTION_CONSTRUCTOR_HAS_TWO_PARAMETERS: Parameters<
  typeof makeS2SCurrentRunStageAuthorityLiveLayer
>["length"] extends 2
  ? true
  : false = true
type ArtifactLayerRequirements = LayerRequirements<
  ReturnType<typeof makeS2SStageArtifactReadsLiveLayer>
>
const ARTIFACT_LAYER_IS_CLOSED: [ArtifactLayerRequirements] extends [never]
  ? true
  : false = true
const ARTIFACT_CONSTRUCTOR_HAS_TWO_PARAMETERS: Parameters<
  typeof makeS2SStageArtifactReadsLiveLayer
>["length"] extends 2
  ? true
  : false = true
type ReviewedFixture = {
  readonly workflowApiPath: string
  readonly workflowFileSha256: string
}

interface PolicyFixtureOptions {
  readonly requestIds?: readonly [string, string, string, string]
  readonly observationTimes?: readonly [number, number, number, number]
  readonly startRun?: Readonly<Record<string, unknown>>
  readonly rosterRun?: Readonly<Record<string, unknown>>
  readonly endRun?: Readonly<Record<string, unknown>>
  readonly rosterRuns?: ReadonlyArray<Readonly<Record<string, unknown>>>
  readonly jobs?: ReadonlyArray<Readonly<Record<string, unknown>>>
}

let registrationFixture: S2SRegistrationAuthorityFixture
let registrationEvidence: S2SRegistrationCommitAuthorityEvidence
let workflowBinding: S2SRegistrationWorkflowManifestBinding
const invocationAuthorities = new Map<
  S2SConfirmatoryJobStage,
  S2SCurrentInvocationAuthority
>()
const invocationEvidence = new Map<
  S2SConfirmatoryJobStage,
  S2SCurrentInvocationEvidence
>()

const jsonBytes = (value: unknown): Uint8Array =>
  UTF8_ENCODER.encode(`${JSON.stringify(value)}\n`)

const provenance = (githubRequestId: string): S2SGitHubApiResponseProvenance =>
  Object.freeze({
    githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: RESPONSE_ETAG
  })

const isoAt = (unixSeconds: number): string =>
  new Date(unixSeconds * 1_000).toISOString().replace(".000Z", "Z")

const invocationEnvironment = (
  stage: S2SConfirmatoryJobStage,
  registrationCommitB = registrationFixture.registrationCommitB
): Record<string, unknown> => {
  const jobId = stage.toLowerCase()
  return {
    GITHUB_ACTIONS: "true",
    GITHUB_API_URL: "https://api.github.com",
    GITHUB_EVENT_NAME: "push",
    GITHUB_JOB: jobId,
    GITHUB_REF: "refs/heads/main",
    GITHUB_REF_NAME: "main",
    GITHUB_REF_TYPE: "branch",
    GITHUB_REPOSITORY: "gj3447/HSWM",
    GITHUB_RUN_ATTEMPT: "1",
    GITHUB_RUN_ID: String(RUN_ID),
    GITHUB_SERVER_URL: "https://github.com",
    GITHUB_SHA: registrationCommitB,
    GITHUB_WORKFLOW: "SWM-0W-S2S confirmatory",
    GITHUB_WORKFLOW_REF:
      "gj3447/HSWM/.github/workflows/swm0w-s2s-confirmatory.yml@refs/heads/main",
    GITHUB_WORKFLOW_SHA: registrationCommitB,
    RUNNER_ARCH: "X64",
    RUNNER_ENVIRONMENT: "github-hosted",
    RUNNER_OS: "Linux"
  }
}

const invocationEvent = (
  sourceCommitA = registrationFixture.sourceCommitA,
  registrationCommitB = registrationFixture.registrationCommitB
): Record<string, unknown> => ({
  after: registrationCommitB,
  base_ref: null,
  before: sourceCommitA,
  commits: [
    {
      added: ["prereg/PREREG_SWM0W_S2S_GATE_V1.json"],
      distinct: true,
      id: registrationCommitB,
      message: "register future measurement"
    }
  ],
  compare:
    `https://github.com/gj3447/HSWM/compare/` +
    `${sourceCommitA}...${registrationCommitB}`,
  created: false,
  deleted: false,
  forced: false,
  head_commit: {
    id: registrationCommitB,
    message: "register future measurement"
  },
  pusher: { name: "fixture" },
  ref: "refs/heads/main",
  repository: {
    default_branch: "main",
    fork: false,
    full_name: "gj3447/HSWM",
    private: false
  },
  sender: { login: "fixture" }
})

const makeInvocationAuthority = async (
  stage: S2SConfirmatoryJobStage
): Promise<S2SCurrentInvocationAuthority> =>
  Effect.runPromise(
    Effect.gen(function* () {
      const current = yield* S2SCurrentInvocation
      return current.authority
    }).pipe(
      Effect.provide(
        makeS2SCurrentInvocationTestLayer(
          invocationEnvironment(stage),
          jsonBytes(invocationEvent()),
          INVOCATION_CAPTURED_AT
        )
      )
    )
  )

const runApiFixture = (
  overrides: Readonly<Record<string, unknown>> = {}
): Record<string, unknown> => ({
  id: RUN_ID,
  run_attempt: 1,
  name: "SWM-0W-S2S confirmatory",
  path: S2S_CONFIRMATORY_WORKFLOW_PATH,
  event: "push",
  head_branch: "main",
  head_sha: registrationFixture.registrationCommitB,
  repository: { full_name: "gj3447/HSWM" },
  head_repository: { full_name: "gj3447/HSWM" },
  status: "in_progress",
  conclusion: null,
  created_at: CREATED_AT,
  ...overrides
})

const jobApiFixtures = (
  stage: S2SConfirmatoryJobStage
): ReadonlyArray<Record<string, unknown>> => {
  const currentIndex = S2S_CONFIRMATORY_JOB_STAGES.indexOf(stage)
  return S2S_CONFIRMATORY_JOB_STAGES.map((jobStage, index) => {
    const startedAt = CREATED_AT_UNIX_SECONDS + 2 + index * 5
    const isEarlier = index < currentIndex
    const isCurrent = index === currentIndex
    return {
      id: 700 + index,
      run_id: RUN_ID,
      run_attempt: 1,
      name: jobStage.toLowerCase(),
      head_sha: registrationFixture.registrationCommitB,
      status: isEarlier ? "completed" : isCurrent ? "in_progress" : "queued",
      conclusion: isEarlier ? "success" : null,
      started_at: isoAt(startedAt),
      completed_at: isEarlier ? isoAt(startedAt + 2) : null,
      labels: ["ubuntu-24.04", "GitHub-hosted"]
    }
  })
}

const rightOrThrow = <Success, Failure>(
  outcome: Either.Either<Success, Failure>
): Success => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const makeRunObservation = (
  raw: Readonly<Record<string, unknown>>,
  observedAtUnixSeconds: number,
  requestId: string
): S2SGitHubObservation<S2SGitHubWorkflowRunProjection> =>
  rightOrThrow(
    observeS2SGitHubWorkflowRun(
      jsonBytes(raw),
      RUN_ID,
      observedAtUnixSeconds,
      provenance(requestId)
    )
  )

const makeJobsObservation = (
  jobs: ReadonlyArray<Readonly<Record<string, unknown>>>,
  observedAtUnixSeconds: number,
  requestId: string
): S2SGitHubObservation<S2SGitHubWorkflowJobsProjection> =>
  rightOrThrow(
    observeS2SGitHubWorkflowAttemptJobs(
      jsonBytes({ total_count: jobs.length, jobs }),
      RUN_ID,
      1,
      observedAtUnixSeconds,
      provenance(requestId)
    )
  )

const makeRosterObservation = (
  runs: ReadonlyArray<Readonly<Record<string, unknown>>>,
  observedAtUnixSeconds: number,
  requestId: string
): S2SGitHubObservation<S2SGitHubWorkflowRunsProjection> =>
  rightOrThrow(
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: runs.length, workflow_runs: runs }),
      registrationFixture.registrationCommitB,
      observedAtUnixSeconds,
      provenance(requestId)
    )
  )

const makePolicyInput = (
  stage: S2SConfirmatoryJobStage,
  options: PolicyFixtureOptions = {}
): PolicyInput => {
  const invocation = invocationEvidence.get(stage)
  if (invocation === undefined) throw new Error("invocation fixture is absent")
  const requestIds = options.requestIds ?? DEFAULT_REQUEST_IDS
  const times = options.observationTimes ?? DEFAULT_OBSERVATION_TIMES
  const start = runApiFixture(options.startRun)
  const roster = runApiFixture(options.rosterRun)
  const end = runApiFixture(options.endRun)
  const jobs = options.jobs ?? jobApiFixtures(stage)
  return {
    registration: registrationEvidence,
    invocation,
    workflowBinding,
    runStart: makeRunObservation(start, times[0], requestIds[0]),
    jobs: makeJobsObservation(jobs, times[1], requestIds[1]),
    runsForHead: makeRosterObservation(
      options.rosterRuns ?? [roster],
      times[2],
      requestIds[2]
    ),
    runEnd: makeRunObservation(end, times[3], requestIds[3])
  }
}

const reviewedFixture = (
  workflowApiPath: string = S2S_CONFIRMATORY_WORKFLOW_PATH
): ReviewedFixture => ({
  workflowApiPath,
  workflowFileSha256: workflowBinding.workflowFileSha256
})

type ObservationTrace = Array<
  | { readonly phase: "RUN"; readonly identity: number }
  | { readonly phase: "JOBS"; readonly identity: number }
  | { readonly phase: "RUNS_FOR_HEAD"; readonly identity: string }
>

const observerForPolicyInput = (
  input: PolicyInput,
  trace: ObservationTrace = []
): S2SGitHubObserver["Type"] => {
  let runReadCount = 0
  return S2SGitHubObserver.of({
    observeWorkflowRun: (workflowRunId) =>
      Effect.suspend(() => {
        trace.push({ phase: "RUN", identity: workflowRunId })
        const observation =
          runReadCount === 0
            ? input.runStart
            : runReadCount === 1
              ? input.runEnd
              : undefined
        runReadCount += 1
        return observation === undefined
          ? Effect.dieMessage("unexpected third run observation")
          : Effect.succeed(observation)
      }),
    observeWorkflowAttemptJobs: (workflowRunId) =>
      Effect.sync(() => {
        trace.push({ phase: "JOBS", identity: workflowRunId })
        return input.jobs
      }),
    observeWorkflowRunsForHead: (headSha) =>
      Effect.sync(() => {
        trace.push({ phase: "RUNS_FOR_HEAD", identity: headSha })
        return input.runsForHead
      }),
    observeRunArtifacts: () => Effect.dieMessage("unexpected artifact query"),
    observeArtifact: () => Effect.dieMessage("unexpected artifact query"),
    downloadArtifactArchive: () =>
      Effect.dieMessage("unexpected artifact download")
  })
}

const acquisitionProbe = (
  input: PolicyInput,
  reviewed: unknown,
  observer: S2SGitHubObserver["Type"] = observerForPolicyInput(input)
) => {
  const authority = invocationAuthorities.get(input.invocation.stage)
  if (authority === undefined) throw new Error("invocation authority is absent")
  return probeS2SRunAuthorityAcquisitionForTest(
    registrationFixture.registrationAuthority,
    authority,
    observer,
    reviewed
  )
}

const probePolicy = (
  input: PolicyInput,
  reviewed: unknown,
  trace?: ObservationTrace
): Either.Either<
  void,
  Effect.Effect.Error<ReturnType<typeof acquisitionProbe>>
> =>
  Effect.runSync(
    acquisitionProbe(
      input,
      reviewed,
      observerForPolicyInput(input, trace)
    ).pipe(Effect.either)
  )

type AcquisitionPhase = "RUN_START" | "JOBS" | "RUNS_FOR_HEAD" | "RUN_END"

const observerFailingAt = (
  input: PolicyInput,
  failingPhase: AcquisitionPhase,
  trace: ObservationTrace
): S2SGitHubObserver["Type"] => {
  let runReadCount = 0
  const failure = () =>
    Effect.fail(
      new S2SGitHubObservationError({
        reason: "INVALID_ARGUMENT",
        path: "$test",
        detail: "intentional observer failure"
      })
    )
  return S2SGitHubObserver.of({
    observeWorkflowRun: (workflowRunId) =>
      Effect.suspend(() => {
        const phase = runReadCount === 0 ? "RUN_START" : "RUN_END"
        const observation =
          runReadCount === 0 ? input.runStart : input.runEnd
        runReadCount += 1
        trace.push({ phase: "RUN", identity: workflowRunId })
        return phase === failingPhase ? failure() : Effect.succeed(observation)
      }),
    observeWorkflowAttemptJobs: (workflowRunId) =>
      Effect.suspend(() => {
        trace.push({ phase: "JOBS", identity: workflowRunId })
        return failingPhase === "JOBS"
          ? failure()
          : Effect.succeed(input.jobs)
      }),
    observeWorkflowRunsForHead: (headSha) =>
      Effect.suspend(() => {
        trace.push({ phase: "RUNS_FOR_HEAD", identity: headSha })
        return failingPhase === "RUNS_FOR_HEAD"
          ? failure()
          : Effect.succeed(input.runsForHead)
      }),
    observeRunArtifacts: () => Effect.dieMessage("unexpected artifact query"),
    observeArtifact: () => Effect.dieMessage("unexpected artifact query"),
    downloadArtifactArchive: () =>
      Effect.dieMessage("unexpected artifact download")
  })
}

type BracketProjection =
  | S2SGitHubWorkflowRunProjection
  | S2SGitHubWorkflowJobsProjection
  | S2SGitHubWorkflowRunsProjection

const corruptObservationBytes = <Projection extends BracketProjection>(
  observation: S2SGitHubObservation<Projection>
): S2SGitHubObservation<Projection> =>
  Object.freeze({
    receipt: observation.receipt,
    readRawBody: () => new Uint8Array([0])
  })

const observerCorruptingAt = (
  input: PolicyInput,
  corruptPhase: AcquisitionPhase,
  trace: ObservationTrace
): S2SGitHubObserver["Type"] => {
  let runReadCount = 0
  return S2SGitHubObserver.of({
    observeWorkflowRun: (workflowRunId) =>
      Effect.sync(() => {
        const phase = runReadCount === 0 ? "RUN_START" : "RUN_END"
        const observation =
          runReadCount === 0 ? input.runStart : input.runEnd
        runReadCount += 1
        trace.push({ phase: "RUN", identity: workflowRunId })
        return phase === corruptPhase
          ? corruptObservationBytes(observation)
          : observation
      }),
    observeWorkflowAttemptJobs: (workflowRunId) =>
      Effect.sync(() => {
        trace.push({ phase: "JOBS", identity: workflowRunId })
        return corruptPhase === "JOBS"
          ? corruptObservationBytes(input.jobs)
          : input.jobs
      }),
    observeWorkflowRunsForHead: (headSha) =>
      Effect.sync(() => {
        trace.push({ phase: "RUNS_FOR_HEAD", identity: headSha })
        return corruptPhase === "RUNS_FOR_HEAD"
          ? corruptObservationBytes(input.runsForHead)
          : input.runsForHead
      }),
    observeRunArtifacts: () => Effect.dieMessage("unexpected artifact query"),
    observeArtifact: () => Effect.dieMessage("unexpected artifact query"),
    downloadArtifactArchive: () =>
      Effect.dieMessage("unexpected artifact download")
  })
}

const expectPolicyFailure = (
  outcome: ReturnType<typeof probePolicy>,
  reason: string
): void => {
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isLeft(outcome)) expect(outcome.left.reason).toBe(reason)
}

beforeAll(async () => {
  registrationFixture = await makeS2SRegistrationAuthorityFixture()
  registrationEvidence = rightOrThrow(
    inspectS2SRegistrationCommitAuthority(
      registrationFixture.registrationAuthority
    )
  )
  workflowBinding = rightOrThrow(
    inspectS2SRegistrationWorkflowManifestBinding(
      registrationFixture.registrationAuthority
    )
  )
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    const authority = await makeInvocationAuthority(stage)
    invocationAuthorities.set(stage, authority)
    invocationEvidence.set(
      stage,
      rightOrThrow(inspectS2SCurrentInvocationAuthority(authority))
    )
  }
}, 30_000)

afterAll(() => {
  registrationFixture?.cleanup()
})

describe("non-authorizing run-stage policy probe", () => {
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    it(`accepts the exact ${stage} predecessor matrix but returns only void`, () => {
      const outcome = probePolicy(
        makePolicyInput(stage),
        reviewedFixture()
      )
      expect(Either.isRight(outcome)).toBe(true)
      if (Either.isRight(outcome)) {
        expect(outcome.right).toBeUndefined()
        expect(
          Either.isLeft(inspectS2SCurrentRunStageAuthority(outcome.right))
        ).toBe(true)
        expect(
          Either.isLeft(inspectS2SCurrentRunStageAuthority({ outcome: outcome.right }))
        ).toBe(true)
      }
    })
  }

  it("is lazy and performs the exact authentic four-read bracket", () => {
    const input = makePolicyInput("CONFIRM")
    const trace: ObservationTrace = []
    const effect = acquisitionProbe(
      input,
      reviewedFixture(),
      observerForPolicyInput(input, trace)
    )
    expect(trace).toEqual([])
    const outcome = Effect.runSync(effect.pipe(Effect.either))
    expect(Either.isRight(outcome)).toBe(true)
    if (Either.isRight(outcome)) {
      expect(outcome.right).toBeUndefined()
      expect(
        Either.isLeft(inspectS2SCurrentRunStageAuthority(outcome.right))
      ).toBe(true)
    }
    expect(trace).toEqual([
      { phase: "RUN", identity: RUN_ID },
      { phase: "JOBS", identity: RUN_ID },
      {
        phase: "RUNS_FOR_HEAD",
        identity: registrationFixture.registrationCommitB
      },
      { phase: "RUN", identity: RUN_ID }
    ])
    const secondTrace: ObservationTrace = []
    const second = probePolicy(input, reviewedFixture(), secondTrace)
    expect(Either.isRight(second)).toBe(true)
    expect(secondTrace).toEqual(trace)
  })

  it("revalidates each retained-byte reader exactly once", () => {
    const input = makePolicyInput("CONFIRM")
    const runStartReader = vi.fn(() => input.runStart.readRawBody())
    const jobsReader = vi.fn(() => input.jobs.readRawBody())
    const rosterReader = vi.fn(() => input.runsForHead.readRawBody())
    const runEndReader = vi.fn(() => input.runEnd.readRawBody())
    const instrumented: PolicyInput = {
      ...input,
      runStart: Object.freeze({
        receipt: input.runStart.receipt,
        readRawBody: runStartReader
      }),
      jobs: Object.freeze({
        receipt: input.jobs.receipt,
        readRawBody: jobsReader
      }),
      runsForHead: Object.freeze({
        receipt: input.runsForHead.receipt,
        readRawBody: rosterReader
      }),
      runEnd: Object.freeze({
        receipt: input.runEnd.receipt,
        readRawBody: runEndReader
      })
    }
    const outcome = probePolicy(instrumented, reviewedFixture())
    expect(Either.isRight(outcome)).toBe(true)
    expect([
      runStartReader.mock.calls.length,
      jobsReader.mock.calls.length,
      rosterReader.mock.calls.length,
      runEndReader.mock.calls.length
    ]).toEqual([1, 1, 1, 1])
  })

  it("maps every observer failure to its phase and short-circuits", () => {
    const input = makePolicyInput("CONFIRM")
    const expectations: ReadonlyArray<{
      readonly phase: AcquisitionPhase
      readonly traceLength: number
    }> = [
      { phase: "RUN_START", traceLength: 1 },
      { phase: "JOBS", traceLength: 2 },
      { phase: "RUNS_FOR_HEAD", traceLength: 3 },
      { phase: "RUN_END", traceLength: 4 }
    ]
    for (const expectation of expectations) {
      const trace: ObservationTrace = []
      const outcome = Effect.runSync(
        acquisitionProbe(
          input,
          reviewedFixture(),
          observerFailingAt(input, expectation.phase, trace)
        ).pipe(Effect.either)
      )
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left).toMatchObject({
          _tag: "S2SCurrentRunAcquisitionError",
          phase: expectation.phase,
          reason: "OBSERVATION_FAILED"
        })
      }
      expect(trace).toHaveLength(expectation.traceLength)
    }
  })

  it("maps every byte revalidation failure and short-circuits", () => {
    const input = makePolicyInput("CONFIRM")
    const expectations: ReadonlyArray<{
      readonly phase: AcquisitionPhase
      readonly traceLength: number
    }> = [
      { phase: "RUN_START", traceLength: 1 },
      { phase: "JOBS", traceLength: 2 },
      { phase: "RUNS_FOR_HEAD", traceLength: 3 },
      { phase: "RUN_END", traceLength: 4 }
    ]
    for (const expectation of expectations) {
      const trace: ObservationTrace = []
      const outcome = Effect.runSync(
        acquisitionProbe(
          input,
          reviewedFixture(),
          observerCorruptingAt(input, expectation.phase, trace)
        ).pipe(Effect.either)
      )
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left).toMatchObject({
          _tag: "S2SCurrentRunAcquisitionError",
          phase: expectation.phase,
          reason: "REVALIDATION_FAILED"
        })
      }
      expect(trace).toHaveLength(expectation.traceLength)
    }
  })

  it("accepts equal observation seconds and case-distinct request IDs", () => {
    const equalTime = INVOCATION_CAPTURED_AT + 1
    const outcome = probePolicy(
      makePolicyInput("CONFIRM", {
        requestIds: ["same", "Same", "SAME", "sAmE"],
        observationTimes: [equalTime, equalTime, equalTime, equalTime]
      }),
      reviewedFixture()
    )
    expect(Either.isRight(outcome)).toBe(true)
  })

  it("rejects every pairwise request-ID reuse placement", () => {
    for (let left = 0; left < 4; left += 1) {
      for (let right = left + 1; right < 4; right += 1) {
        const requestIds = [...DEFAULT_REQUEST_IDS] as [
          string,
          string,
          string,
          string
        ]
        const reused = requestIds[left]
        if (reused === undefined) throw new Error("request-ID fixture is absent")
        requestIds[right] = reused
        expectPolicyFailure(
          probePolicy(
            makePolicyInput("CONFIRM", { requestIds }),
            reviewedFixture()
          ),
          "REQUEST_ID_REUSED"
        )
      }
    }
  })

  it("rejects invocation/observation inversion and every later timestamp inversion", () => {
    const invalidTimes: ReadonlyArray<readonly [number, number, number, number]> = [
      [
        INVOCATION_CAPTURED_AT - 1,
        INVOCATION_CAPTURED_AT + 2,
        INVOCATION_CAPTURED_AT + 3,
        INVOCATION_CAPTURED_AT + 4
      ],
      [101, 100, 102, 103],
      [100, 102, 101, 103],
      [100, 101, 103, 102]
    ]
    for (const observationTimes of invalidTimes) {
      expectPolicyFailure(
        probePolicy(
          makePolicyInput("CONFIRM", { observationTimes }),
          reviewedFixture()
        ),
        "OBSERVATION_ORDER_INVALID"
      )
    }
  })

  it("rejects zero, multiple, and wrong sole exact-head roster rows", () => {
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", { rosterRuns: [] }),
        reviewedFixture()
      ),
      "RUN_MULTIPLICITY_ZERO"
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", {
          rosterRuns: [runApiFixture(), runApiFixture({ id: RUN_ID + 1 })]
        }),
        reviewedFixture()
      ),
      "RUN_MULTIPLICITY_MULTIPLE"
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", {
          rosterRuns: [runApiFixture({ id: RUN_ID + 1 })]
        }),
        reviewedFixture()
      ),
      "CURRENT_RUN_MISMATCH"
    )
  })

  it("rejects one-field immutable run drift across the bracket", () => {
    const driftCases: ReadonlyArray<Readonly<Record<string, unknown>>> = [
      { name: "different workflow" },
      { event: "workflow_dispatch" },
      { head_branch: "dev" },
      { run_attempt: 2 },
      { created_at: isoAt(CREATED_AT_UNIX_SECONDS - 1) }
    ]
    for (const rosterRun of driftCases) {
      expectPolicyFailure(
        probePolicy(
          makePolicyInput("CONFIRM", { rosterRun }),
          reviewedFixture()
        ),
        "RUN_IDENTITY_DRIFT"
      )
    }
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", {
          endRun: { head_sha: "f".repeat(40) }
        }),
        reviewedFixture()
      ),
      "RUN_IDENTITY_DRIFT"
    )
  })

  it("requires one exact reviewed workflow API path representation", () => {
    const suffixed = `${S2S_CONFIRMATORY_WORKFLOW_PATH}@main`
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", {
          startRun: { path: suffixed },
          rosterRun: { path: suffixed },
          endRun: { path: suffixed }
        }),
        reviewedFixture()
      ),
      "WORKFLOW_PATH_REJECTED"
    )
    const accepted = probePolicy(
      makePolicyInput("CONFIRM", {
        startRun: { path: suffixed },
        rosterRun: { path: suffixed },
        endRun: { path: suffixed }
      }),
      reviewedFixture(suffixed)
    )
    expect(Either.isRight(accepted)).toBe(true)
  })

  it("rejects caller attempts to add OPEN overrides or replace reviewed bytes", () => {
    const hostileFixtures: ReadonlyArray<{
      readonly fixture: unknown
      readonly reason: string
    }> = [
      {
        fixture: { ...reviewedFixture(), allowOpen: true },
        reason: "REVIEWED_FIXTURE_REJECTED"
      },
      {
        fixture: {
          ...reviewedFixture(),
          workflowFileSha256: "0".repeat(64)
        },
        reason: "WORKFLOW_HASH_MISMATCH"
      },
      {
        fixture: {
          ...reviewedFixture(),
          workflowApiPath: ".github/workflows/other.yml"
        },
        reason: "REVIEWED_FIXTURE_REJECTED"
      }
    ]
    for (const hostile of hostileFixtures) {
      const trace: ObservationTrace = []
      expectPolicyFailure(
        probePolicy(makePolicyInput("CONFIRM"), hostile.fixture, trace),
        hostile.reason
      )
      expect(trace).toEqual([])
    }
  })

  it("allows nonterminal roster lag but rejects a terminal contradiction", () => {
    const outcome = probePolicy(
      makePolicyInput("CONFIRM", {
        rosterRun: { status: "queued", conclusion: null }
      }),
      reviewedFixture()
    )
    expect(Either.isRight(outcome)).toBe(true)
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", {
          rosterRun: { status: "completed", conclusion: "failure" }
        }),
        reviewedFixture()
      ),
      "RUN_STATE_REJECTED"
    )
  })

  it("requires both direct run reads to remain in progress", () => {
    for (const side of ["startRun", "endRun"] as const) {
      expectPolicyFailure(
        probePolicy(
          makePolicyInput("CONFIRM", {
            [side]: { status: "completed", conclusion: "success" }
          }),
          reviewedFixture()
        ),
        "RUN_STATE_REJECTED"
      )
    }
  })

  it("rejects missing, duplicate, renamed, or matrix-expanded fixed jobs", () => {
    const base = jobApiFixtures("CONFIRM")
    const hostileRosters = [
      base.slice(0, 2),
      base.map((job, index) =>
        index === 1 ? { ...job, name: "register" } : job
      ),
      base.map((job, index) =>
        index === 1 ? { ...job, name: "renamed-confirm" } : job
      ),
      base.map((job, index) =>
        index === 1 ? { ...job, name: "confirm (node-24)" } : job
      )
    ]
    for (const jobs of hostileRosters) {
      expectPolicyFailure(
        probePolicy(
          makePolicyInput("CONFIRM", { jobs }),
          reviewedFixture()
        ),
        "JOB_ROSTER_REJECTED"
      )
    }
  })

  it("rejects job head drift and a non-active current job", () => {
    const wrongHead = jobApiFixtures("CONFIRM").map((job, index) =>
      index === 1 ? { ...job, head_sha: "f".repeat(40) } : job
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", { jobs: wrongHead }),
        reviewedFixture()
      ),
      "JOB_ROSTER_REJECTED"
    )
    const completedCurrent = jobApiFixtures("CONFIRM").map((job, index) =>
      index === 1
        ? {
            ...job,
            status: "completed",
            conclusion: "success",
            completed_at: isoAt(CREATED_AT_UNIX_SECONDS + 11)
          }
        : job
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("CONFIRM", { jobs: completedCurrent }),
        reviewedFixture()
      ),
      "CURRENT_JOB_REJECTED"
    )
  })

  it("rejects failed or chronologically invalid required predecessors", () => {
    const failed = jobApiFixtures("ADJUDICATE").map((job, index) =>
      index === 1 ? { ...job, conclusion: "failure" } : job
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("ADJUDICATE", { jobs: failed }),
        reviewedFixture()
      ),
      "PREDECESSOR_REJECTED"
    )
    const overlapping = jobApiFixtures("ADJUDICATE").map((job, index) =>
      index === 0
        ? {
            ...job,
            completed_at: isoAt(CREATED_AT_UNIX_SECONDS + 9)
          }
        : job
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("ADJUDICATE", { jobs: overlapping }),
        reviewedFixture()
      ),
      "PREDECESSOR_REJECTED"
    )
  })

  it("rejects a later job that is already active", () => {
    const activeLater = jobApiFixtures("REGISTER").map((job, index) =>
      index === 1 ? { ...job, status: "in_progress" } : job
    )
    expectPolicyFailure(
      probePolicy(
        makePolicyInput("REGISTER", { jobs: activeLater }),
        reviewedFixture()
      ),
      "LATER_JOB_REJECTED"
    )
  })

  it("rejects structural and proxied output-like objects", () => {
    const forged = [
      {},
      Object.freeze({ authorityScope: "PROCESS_LOCAL_STAGE_ENTRY" }),
      new Proxy({}, {}),
      Object.create(null)
    ]
    for (const candidate of forged) {
      const outcome = inspectS2SCurrentRunStageAuthority(candidate)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("INVALID_CURRENT_RUN_AUTHORITY")
      }
    }
  })

  it("keeps replay materialization selector-free and rejects forged services", () => {
    expect(S2S_CURRENT_RUN_REPLAY_MAX_RAW_BYTES).toBe(5_242_880)
    let authorityAccessorInvoked = false
    const forged: Record<string, unknown> = {}
    Object.defineProperty(forged, "authority", {
      enumerable: true,
      get: () => {
        authorityAccessorInvoked = true
        return {}
      }
    })
    const outcome = Effect.runSync(
      snapshotS2SCurrentRunReplay.pipe(
        Effect.provide(
          Layer.succeed(
            S2SCurrentRunStage,
            forged as unknown as S2SCurrentRunStage["Type"]
          )
        ),
        Effect.either
      )
    )
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("INVALID_CURRENT_RUN_AUTHORITY")
    }
    expect(authorityAccessorInvoked).toBe(false)
  })

  it("rejects copies and proxies of genuine input authorities before observation", () => {
    const input = makePolicyInput("CONFIRM")
    const genuineRegistration = registrationFixture.registrationAuthority
    const genuineInvocation = invocationAuthorities.get("CONFIRM")
    if (genuineInvocation === undefined) {
      throw new Error("genuine invocation authority is absent")
    }
    const cases: ReadonlyArray<{
      readonly registration: unknown
      readonly invocation: unknown
      readonly reason: string
    }> = [
      {
        registration: { ...genuineRegistration },
        invocation: genuineInvocation,
        reason: "REGISTRATION_AUTHORITY_REJECTED"
      },
      {
        registration: new Proxy(genuineRegistration, {}),
        invocation: genuineInvocation,
        reason: "REGISTRATION_AUTHORITY_REJECTED"
      },
      {
        registration: genuineRegistration,
        invocation: { ...genuineInvocation },
        reason: "INVOCATION_AUTHORITY_REJECTED"
      },
      {
        registration: genuineRegistration,
        invocation: new Proxy(genuineInvocation, {}),
        reason: "INVOCATION_AUTHORITY_REJECTED"
      }
    ]
    for (const fixture of cases) {
      const trace: ObservationTrace = []
      const outcome = Effect.runSync(
        probeS2SRunAuthorityAcquisitionForTest(
          fixture.registration,
          fixture.invocation,
          observerForPolicyInput(input, trace),
          reviewedFixture()
        ).pipe(Effect.either)
      )
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe(fixture.reason)
      }
      expect(trace).toEqual([])
    }
  })
})

it.effect("times out and cancels a stalled acquisition bracket", () =>
  Effect.gen(function* () {
    const input = makePolicyInput("CONFIRM")
    const started = yield* Deferred.make<void>()
    const interrupted = yield* Ref.make(false)
    let runReadCount = 0
    const observer = S2SGitHubObserver.of({
      observeWorkflowRun: () =>
        Effect.sync(() => {
          const observation =
            runReadCount === 0 ? input.runStart : input.runEnd
          runReadCount += 1
          return observation
        }),
      observeWorkflowAttemptJobs: () =>
        Deferred.succeed(started, undefined).pipe(
          Effect.zipRight(Effect.never),
          Effect.onInterrupt(() => Ref.set(interrupted, true))
        ),
      observeWorkflowRunsForHead: () =>
        Effect.dieMessage("roster must not run after stalled jobs"),
      observeRunArtifacts: () => Effect.dieMessage("unexpected artifact query"),
      observeArtifact: () => Effect.dieMessage("unexpected artifact query"),
      downloadArtifactArchive: () =>
        Effect.dieMessage("unexpected artifact download")
    })
    const fiber = yield* acquisitionProbe(
      input,
      reviewedFixture(),
      observer
    ).pipe(Effect.either, Effect.fork)
    yield* Deferred.await(started)
    yield* TestClock.adjust(S2S_CURRENT_RUN_BRACKET_TIMEOUT_MILLIS + 1)
    const outcome = yield* Fiber.join(fiber)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({
        _tag: "S2SCurrentRunAcquisitionError",
        phase: "BRACKET",
        reason: "BRACKET_TIMED_OUT"
      })
    }
    expect(yield* Ref.get(interrupted)).toBe(true)
  })
)

it.effect("preserves direct interruption of a stalled acquisition", () =>
  Effect.gen(function* () {
    const input = makePolicyInput("CONFIRM")
    const started = yield* Deferred.make<void>()
    const interrupted = yield* Ref.make(false)
    const observer = S2SGitHubObserver.of({
      observeWorkflowRun: () => Effect.succeed(input.runStart),
      observeWorkflowAttemptJobs: () =>
        Deferred.succeed(started, undefined).pipe(
          Effect.zipRight(Effect.never),
          Effect.onInterrupt(() => Ref.set(interrupted, true))
        ),
      observeWorkflowRunsForHead: () =>
        Effect.dieMessage("roster must not run after stalled jobs"),
      observeRunArtifacts: () => Effect.dieMessage("unexpected artifact query"),
      observeArtifact: () => Effect.dieMessage("unexpected artifact query"),
      downloadArtifactArchive: () =>
        Effect.dieMessage("unexpected artifact download")
    })
    const fiber = yield* acquisitionProbe(
      input,
      reviewedFixture(),
      observer
    ).pipe(Effect.fork)
    yield* Deferred.await(started)
    const exit = yield* Fiber.interrupt(fiber)
    expect(Exit.isFailure(exit)).toBe(true)
    if (Exit.isFailure(exit)) {
      expect(Cause.isInterruptedOnly(exit.cause)).toBe(true)
    }
    expect(yield* Ref.get(interrupted)).toBe(true)
  })
)

it.effect("preserves observer defects instead of laundering them as typed errors", () =>
  Effect.gen(function* () {
    const input = makePolicyInput("CONFIRM")
    const observer = S2SGitHubObserver.of({
      observeWorkflowRun: () => Effect.succeed(input.runStart),
      observeWorkflowAttemptJobs: () => Effect.dieMessage("observer defect"),
      observeWorkflowRunsForHead: () =>
        Effect.dieMessage("roster must not run after defect"),
      observeRunArtifacts: () => Effect.dieMessage("unexpected artifact query"),
      observeArtifact: () => Effect.dieMessage("unexpected artifact query"),
      downloadArtifactArchive: () =>
        Effect.dieMessage("unexpected artifact download")
    })
    const exit = yield* Effect.exit(
      acquisitionProbe(input, reviewedFixture(), observer)
    )
    expect(Exit.isFailure(exit)).toBe(true)
    if (Exit.isFailure(exit)) {
      expect(Cause.isDieType(exit.cause)).toBe(true)
    }
  })
)

it("keeps production issuance closed before GitHub I/O while source bytes are OPEN", async () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-live-invocation-"))
  const eventPath = join(temporaryRoot, "event.json")
  writeFileSync(eventPath, jsonBytes(invocationEvent()))
  const fetchSpy = vi.fn(() => Promise.reject(new Error("unexpected fetch")))
  try {
    const environment = invocationEnvironment("CONFIRM")
    for (const [key, value] of Object.entries(environment)) {
      vi.stubEnv(key, String(value))
    }
    vi.stubEnv("GITHUB_EVENT_PATH", eventPath)
    vi.stubGlobal("fetch", fetchSpy)
    const outcome = await Effect.runPromise(
      Layer.build(
        makeS2SCurrentRunStageAuthorityLiveLayer(
          registrationFixture.registrationAuthority,
          { token: "" }
        )
      ).pipe(Effect.either, Effect.scoped)
    )
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({
        _tag: "S2SCurrentRunInputError",
        reason: "WORKFLOW_SOURCE_BYTES_OPEN"
      })
    }
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(makeS2SCurrentRunStageAuthorityLiveLayer.length).toBe(2)
  } finally {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    rmSync(temporaryRoot, { force: true, recursive: true })
  }
}, 30_000)

it("keeps production stage artifact reads closed before artifact configuration or I/O", async () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-live-artifact-"))
  const eventPath = join(temporaryRoot, "event.json")
  writeFileSync(eventPath, jsonBytes(invocationEvent()))
  const fetchSpy = vi.fn(() => Promise.reject(new Error("unexpected fetch")))
  try {
    const environment = invocationEnvironment("CONFIRM")
    for (const [key, value] of Object.entries(environment)) {
      vi.stubEnv(key, String(value))
    }
    vi.stubEnv("GITHUB_EVENT_PATH", eventPath)
    vi.stubGlobal("fetch", fetchSpy)
    const outcome = await Effect.runPromise(
      Layer.build(
        makeS2SStageArtifactReadsLiveLayer(
          registrationFixture.registrationAuthority,
          { token: "" }
        )
      ).pipe(Effect.either, Effect.scoped)
    )
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({
        _tag: "S2SCurrentRunInputError",
        reason: "WORKFLOW_SOURCE_BYTES_OPEN"
      })
    }
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(makeS2SStageArtifactReadsLiveLayer.length).toBe(2)
  } finally {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    rmSync(temporaryRoot, { force: true, recursive: true })
  }
}, 30_000)

it("rejects authentic but cross-mismatched invocation A/B before GitHub I/O", async () => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-live-mismatch-"))
  const eventPath = join(temporaryRoot, "event.json")
  const mismatchedSourceA = "c".repeat(40)
  const mismatchedRegistrationB = "d".repeat(40)
  writeFileSync(
    eventPath,
    jsonBytes(invocationEvent(mismatchedSourceA, mismatchedRegistrationB))
  )
  const fetchSpy = vi.fn(() => Promise.reject(new Error("unexpected fetch")))
  try {
    const environment = invocationEnvironment(
      "CONFIRM",
      mismatchedRegistrationB
    )
    for (const [key, value] of Object.entries(environment)) {
      vi.stubEnv(key, String(value))
    }
    vi.stubEnv("GITHUB_EVENT_PATH", eventPath)
    vi.stubGlobal("fetch", fetchSpy)
    const outcome = await Effect.runPromise(
      Layer.build(
        makeS2SCurrentRunStageAuthorityLiveLayer(
          registrationFixture.registrationAuthority,
          { token: "" }
        )
      ).pipe(Effect.either, Effect.scoped)
    )
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({
        _tag: "S2SCurrentRunInputError",
        reason: "REGISTRATION_INVOCATION_MISMATCH"
      })
    }
    expect(fetchSpy).not.toHaveBeenCalled()
  } finally {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    rmSync(temporaryRoot, { force: true, recursive: true })
  }
}, 30_000)

it("keeps every current-run authority surface out of the package root", async () => {
  // @ts-expect-error current-run capability types are deliberately root-private
  type ForbiddenRootAuthority = import("../src/index.js").S2SCurrentRunStageAuthority
  // @ts-expect-error current-run evidence types are deliberately root-private
  type ForbiddenRootEvidence = import("../src/index.js").S2SCurrentRunStageEvidence
  const typeOnlyAbsence: readonly [
    ForbiddenRootAuthority | undefined,
    ForbiddenRootEvidence | undefined
  ] = [undefined, undefined]
  expect(typeOnlyAbsence).toEqual([undefined, undefined])
  const publicApi: Record<string, unknown> = await import("../src/index.js")
  for (const key of [
    "S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION",
    "S2S_CURRENT_RUN_BRACKET_TIMEOUT_MILLIS",
    "S2S_CURRENT_RUN_REPLAY_MAX_RAW_BYTES",
    "S2SCurrentRunInputError",
    "S2SCurrentRunAcquisitionError",
    "S2SCurrentRunPolicyError",
    "S2SCurrentRunStage",
    "S2SCurrentRunStageAuthority",
    "inspectS2SCurrentRunStageAuthority",
    "snapshotS2SCurrentRunReplay",
    "makeS2SCurrentRunStageAuthorityLiveLayer",
    "probeS2SRunAuthorityAcquisitionForTest",
    "S2SStageArtifactReads",
    "S2SStageArtifactPermitError",
    "makeS2SStageArtifactReadsLiveLayer",
    "probeS2SStageArtifactReadMechanicsForTest"
  ]) {
    expect(key in publicApi).toBe(false)
  }
  const packageManifest: unknown = JSON.parse(
    readFileSync(join(process.cwd(), "package.json"), "utf8")
  )
  expect(packageManifest).toMatchObject({
    exports: { ".": { types: "./dist/index.d.ts", default: "./dist/index.js" } }
  })
  if (
    packageManifest === null ||
    typeof packageManifest !== "object" ||
    !("exports" in packageManifest) ||
    packageManifest.exports === null ||
    typeof packageManifest.exports !== "object"
  ) {
    throw new Error("package export fixture is malformed")
  }
  expect(Reflect.ownKeys(packageManifest.exports)).toEqual(["."])
})

it("defines an observer-shaped decoy without creating a production override seam", () => {
  const decoy: S2SGitHubObserver["Type"] = S2SGitHubObserver.of({
    observeWorkflowRun: () => Effect.dieMessage("decoy"),
    observeWorkflowAttemptJobs: () => Effect.dieMessage("decoy"),
    observeWorkflowRunsForHead: () => Effect.dieMessage("decoy"),
    observeRunArtifacts: () => Effect.dieMessage("decoy"),
    observeArtifact: () => Effect.dieMessage("decoy"),
    downloadArtifactArchive: () => Effect.dieMessage("decoy")
  })
  expect(decoy).toBeDefined()
  expect(PRODUCTION_LAYER_IS_CLOSED).toBe(true)
  expect(PRODUCTION_CONSTRUCTOR_HAS_TWO_PARAMETERS).toBe(true)
  expect(ARTIFACT_LAYER_IS_CLOSED).toBe(true)
  expect(ARTIFACT_CONSTRUCTOR_HAS_TWO_PARAMETERS).toBe(true)
  expect(makeS2SCurrentRunStageAuthorityLiveLayer.length).toBe(2)
  expect(makeS2SStageArtifactReadsLiveLayer.length).toBe(2)
  if (false) {
    // @ts-expect-error production has no Observer or policy override parameter
    makeS2SCurrentRunStageAuthorityLiveLayer({}, { token: "" }, decoy)
    // @ts-expect-error production has no Observer or policy override parameter
    makeS2SStageArtifactReadsLiveLayer({}, { token: "" }, decoy)
  }
})
