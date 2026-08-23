import { expect, it } from "@effect/vitest"
import {
  Cause,
  Chunk,
  Clock,
  Context,
  Deferred,
  Effect,
  Either,
  Exit,
  Fiber,
  Layer,
  Schema,
  Scope,
  TestClock
} from "effect"

import * as PublicApi from "../src/index.js"
import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2SConfirmatoryEventSchema,
  S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
  S2S_CONFIRMATORY_EXPERIMENT_ID,
  S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
  S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
  S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  initialS2SConfirmatoryState
} from "../src/s2s-confirmatory.js"
import {
  inspectS2SPreparedStageCarrierTestCapability,
  makeS2SPreparedStageCarrierTestCapability,
  type S2SPreparedStageCarrierCapability,
  type S2SPreparedStageCarrierTestSeed
} from "../src/s2s-prepared-stage-carrier.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
  S2S_GITHUB_REPOSITORY,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  S2SGitHubObservationError,
  S2SGitHubObserver,
  S2SGitHubTransportError,
  type S2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownloadReceipt
} from "../src/s2s-live-github.js"
import {
  S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
  S2SCurrentRunStage,
  type S2SCurrentRunStageEvidence
} from "../src/s2s-run-authority.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "../src/s2s-stage-artifact-spec.js"
import {
  S2SStageUploadAssertionPermitError,
  S2SStageUploadAssertion,
  S2SStageUploadAssertionShellError,
  appendS2SStageUploadAssertionLedgerEntryForTest,
  claimS2SStageUploadAssertionPermitScope,
  inspectS2SStageUploadAssertionCompletionForTest,
  inspectS2SStageUploadAssertionReplayForTest,
  makeS2SStageUploadAssertionLiveLayer,
  makeS2SStageUploadAssertionPermitTestScope,
  makeS2SStageUploadAssertionTestLayer,
  materializeS2SStageUploadAssertionReplayForTest,
  probeS2SStageUploadAssertionMechanicsForTest,
  probeS2SProductionProcessContinuityGateForTest,
  probeS2SStageUploadAssertionShellForTest,
  probeS2SStageUploadAssertionWholeTimeoutForTest,
  snapshotS2SStageUploadAssertionPermitEvidenceForTest,
  useS2SStageUploadAssertionPermitForTest,
  type S2SStageUploadAssertionLedgerObservation,
  type S2SStageUploadAssertionLedgerPhase,
  type S2SStageUploadAssertionPermitScope,
  type S2SStageUploadAssertionPermitTestSeed,
  type S2SStageUploadAssertionTestObserver
} from "../src/s2s-stage-upload-assertion.js"
import {
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  s2sConfirmatoryWorkflowContractSha256,
  type S2SConfirmatoryJobStage
} from "../src/s2s-workflow-contract.js"
import { buildS2STestActionZip } from "./support/s2s-action-zip.js"
import { makeS2SThreeStageCarrierInputs } from "./support/s2s-three-stage-carrier-inputs.js"

const SOURCE_COMMIT_A = "a".repeat(40)
const REGISTRATION_COMMIT_B = "b".repeat(40)
const WORKFLOW_FILE_SHA256 = "c".repeat(64)
const WORKFLOW_SHA256 = "d".repeat(64)
const PREREGISTRATION_SHA256 = "e".repeat(64)
const WORKFLOW_RUN_ID = 32_442_437_970
const REGISTER_JOB_DATABASE_ID = 96_655_652_099
const WORKFLOW_CREATED_AT_UNIX_SECONDS = 1_692_806_164
const WORKFLOW_CREATED_AT = "2023-08-23T15:56:04Z"
const CURRENT_OBSERVED_AT = WORKFLOW_CREATED_AT_UNIX_SECONDS + 2_000
const ENCODER = new TextEncoder()

const right = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const WORKFLOW_CONTRACT_SHA256 = right(
  s2sConfirmatoryWorkflowContractSha256()
)

const hash = (label: string): string =>
  rawS2SFileSha256(ENCODER.encode(label))

const structuredCloneOrEmpty = (value: unknown): unknown => {
  try {
    return structuredClone(value)
  } catch {
    return Object.freeze({})
  }
}

const decodeEvent = Schema.decodeUnknownSync(S2SConfirmatoryEventSchema, {
  onExcessProperty: "error"
})

const registrationEvent = (sourceCommitA = SOURCE_COMMIT_A) => {
  const initial = initialS2SConfirmatoryState()
  const event = decodeEvent({
    schemaVersion: S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION,
    _tag: "BeginRegistration",
    binding: {
      experimentId: S2S_CONFIRMATORY_EXPERIMENT_ID,
      sourceCommitA,
      registrationCommitB: REGISTRATION_COMMIT_B,
      workflowRunId: WORKFLOW_RUN_ID,
      workflowRunAttempt: 1,
      workflowHeadSha: REGISTRATION_COMMIT_B,
      workflowSha256: WORKFLOW_SHA256,
      preregistrationSha256: PREREGISTRATION_SHA256,
      resourcePolicySha256: S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
      protocolConfigSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
      githubObservationSchemaVersion:
        S2S_GITHUB_OBSERVATION_RECEIPT_SCHEMA_VERSION,
      githubArtifactDownloadSchemaVersion:
        S2S_GITHUB_ARTIFACT_DOWNLOAD_RECEIPT_SCHEMA_VERSION,
      predecessorControlReceiptSha256:
        initial.latestControlReceiptSha256
    },
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    workflowRunId: WORKFLOW_RUN_ID,
    registrationJobId: REGISTER_JOB_DATABASE_ID,
    workflowRunAttempt: 1,
    workflowHeadSha: REGISTRATION_COMMIT_B,
    workflowCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS,
    registrationJobStartedAtUnixSeconds:
      WORKFLOW_CREATED_AT_UNIX_SECONDS + 10,
    workflowRunObservationReceiptSha256: hash("registration-run"),
    workflowJobsObservationReceiptSha256: hash("registration-jobs"),
    workflowRunStatus: "in_progress",
    registrationJobStatus: "in_progress",
    sourceCommitSha: sourceCommitA,
    preregistrationCommitSha: REGISTRATION_COMMIT_B,
    beaconId: "quicknet",
    beaconChainHashHex:
      "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
    futureBeaconRound: 1_000,
    futureRoundCommitmentSelfHashSha256:
      "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
    declaredPulseLeadSeconds: 200
  })
  if (event._tag !== "BeginRegistration") throw new Error("wrong event")
  return event
}

const makeCurrentRunEvidence = (
  stage: S2SConfirmatoryJobStage = "REGISTER"
): S2SCurrentRunStageEvidence => {
  const stageOrdinal = {
    REGISTER: 0,
    CONFIRM: 1,
    ADJUDICATE: 2
  }[stage]
  const observations = Object.freeze({
    runStart: Object.freeze({
      githubRequestId: "SEED:REGISTER:RUN-START",
      receiptSha256: hash("seed-run-start"),
      observedAtUnixSeconds: CURRENT_OBSERVED_AT - 40
    }),
    jobs: Object.freeze({
      githubRequestId: "SEED:REGISTER:JOBS",
      receiptSha256: hash("seed-jobs"),
      observedAtUnixSeconds: CURRENT_OBSERVED_AT - 30
    }),
    runsForHead: Object.freeze({
      githubRequestId: "SEED:REGISTER:RUNS-FOR-HEAD",
      receiptSha256: hash("seed-runs-for-head"),
      observedAtUnixSeconds: CURRENT_OBSERVED_AT - 20
    }),
    runEnd: Object.freeze({
      githubRequestId: "SEED:REGISTER:RUN-END",
      receiptSha256: hash("seed-run-end"),
      observedAtUnixSeconds: CURRENT_OBSERVED_AT - 10
    })
  })
  const core: Omit<S2SCurrentRunStageEvidence, "receiptSha256"> = {
    schemaVersion: S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
    authorityScope: "PROCESS_LOCAL_STAGE_ENTRY",
    uniquenessClaim: "ROSTER_OBSERVATION_INSTANT_ONLY",
    historicalUniquenessClaimed: false,
    crossExecutionReplayPreventionClaimed: false,
    durableCommitRequiresFreshTerminalObservation: true,
    sourceCommitA: SOURCE_COMMIT_A,
    registrationCommitB: REGISTRATION_COMMIT_B,
    registrationAuthorityReceiptSha256: hash("registration-authority"),
    currentInvocationReceiptSha256: hash("current-invocation"),
    workflowContractSha256: WORKFLOW_CONTRACT_SHA256,
    workflowFileSha256: WORKFLOW_FILE_SHA256,
    trackedBytesManifestSha256: hash("tracked-bytes-manifest"),
    workflowApiPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
    workflowRunId: WORKFLOW_RUN_ID,
    workflowRunAttempt: 1,
    stage,
    currentJobId: S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobId,
    currentJobDatabaseId: REGISTER_JOB_DATABASE_ID + stageOrdinal,
    predecessorJobDatabaseIds: Object.freeze(
      Array.from(
        { length: stageOrdinal },
        (_unused, index) => REGISTER_JOB_DATABASE_ID + index
      )
    ),
    workflowRunCreatedAt: WORKFLOW_CREATED_AT,
    workflowRunCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS,
    invocationCapturedAtUnixSeconds: CURRENT_OBSERVED_AT - 100,
    observations
  }
  return Object.freeze({
    ...core,
    receiptSha256: right(canonicalS2SControlSha256(core))
  })
}

interface Fixture {
  readonly permitSeed: S2SStageUploadAssertionPermitTestSeed
  readonly preparedSeed: S2SPreparedStageCarrierTestSeed
  readonly capability: S2SPreparedStageCarrierCapability
}

const makeFixture = (
  stage: S2SConfirmatoryJobStage = "REGISTER",
  carrierInput: unknown = { events: [registrationEvent()] }
): Fixture => {
  const currentRunEvidence = makeCurrentRunEvidence(stage)
  const preparedSeed: S2SPreparedStageCarrierTestSeed = {
    classification: "TEST_ONLY_NON_AUTHORIZING",
    stage,
    sourceCommitA: currentRunEvidence.sourceCommitA,
    currentRunEvidenceReceiptSha256: currentRunEvidence.receiptSha256,
    workflowRunId: currentRunEvidence.workflowRunId,
    registrationCommitB: currentRunEvidence.registrationCommitB,
    workflowApiPath: currentRunEvidence.workflowApiPath,
    workflowRunCreatedAt: currentRunEvidence.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds:
      currentRunEvidence.workflowRunCreatedAtUnixSeconds,
    currentJobDatabaseId: currentRunEvidence.currentJobDatabaseId,
    predecessorJobDatabaseIds: currentRunEvidence.predecessorJobDatabaseIds
  }
  const capability = right(
    makeS2SPreparedStageCarrierTestCapability(preparedSeed, carrierInput)
  )
  return Object.freeze({
    permitSeed: Object.freeze({
      classification: "TEST_ONLY_NON_AUTHORIZING" as const,
      currentRunEvidence
    }),
    preparedSeed,
    capability
  })
}

const makeScope = (): {
  readonly fixture: Fixture
  readonly scope: S2SStageUploadAssertionPermitScope
} => {
  const fixture = makeFixture()
  return Object.freeze({
    fixture,
    scope: right(
      makeS2SStageUploadAssertionPermitTestScope(
        fixture.permitSeed,
        fixture.capability
      )
    )
  })
}

const expectPermitReason = (
  outcome: Either.Either<unknown, unknown>,
  reason: S2SStageUploadAssertionPermitError["reason"]
): S2SStageUploadAssertionPermitError => {
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isRight(outcome)) throw new Error("expected a typed failure")
  expect(outcome.left).toBeInstanceOf(S2SStageUploadAssertionPermitError)
  if (!(outcome.left instanceof S2SStageUploadAssertionPermitError)) {
    throw outcome.left
  }
  expect(outcome.left.reason).toBe(reason)
  return outcome.left
}

interface ObserverTrace {
  readonly githubCalls: Array<{
    readonly operation: string
    readonly input: unknown
  }>
  postconditionObservationCount: number
  readonly settleOrdinals: Array<1 | 2>
}

class AssertionMechanicsTestService extends Context.Tag(
  "hswm/test/S2SStageUploadAssertionMechanics"
)<
  AssertionMechanicsTestService,
  {
    readonly run: Effect.Effect<
      void,
      S2SStageUploadAssertionPermitError
    >
  }
>() {}

const makeTrace = (): ObserverTrace => ({
  githubCalls: [],
  postconditionObservationCount: 0,
  settleOrdinals: []
})

const makeObserver = (
  successfulAttemptOrdinal: 1 | 2 | 3,
  trace: ObserverTrace
): S2SStageUploadAssertionTestObserver => {
  let receiptOrdinal = 0
  const observe = (
    operation: string,
    input: unknown,
    countsTowardPostcondition = true
  ): S2SStageUploadAssertionLedgerObservation => {
    trace.githubCalls.push(Object.freeze({ operation, input }))
    if (countsTowardPostcondition) {
      trace.postconditionObservationCount += 1
    }
    receiptOrdinal += 1
    return Object.freeze({
      githubRequestId: `ASSERTION:${receiptOrdinal}:${operation}`,
      receiptSha256: hash(`assertion-${receiptOrdinal}-${operation}`),
      observedAtUnixSeconds: CURRENT_OBSERVED_AT + receiptOrdinal
    })
  }
  return {
    observeWorkflowRun: (input) =>
      Effect.sync(() => observe("RUN", input)),
    observeWorkflowAttemptJobs: (input) =>
      Effect.sync(() => observe("JOBS", input)),
    observeRunArtifacts: (input) =>
      Effect.sync(() => {
        const observation = observe("ARTIFACTS", input)
        return input.successfulAttemptCandidate ===
          successfulAttemptOrdinal
          ? Object.freeze({
              _tag: "Observed" as const,
              observation,
              artifactId: 9_433_344_546
            })
          : Object.freeze({
              _tag: "Absent" as const,
              observation
            })
      }),
    observeArtifact: (input) =>
      Effect.sync(() =>
        Object.freeze({
          _tag: "Matched" as const,
          observation: observe("ARTIFACT", input)
        })
      ),
    downloadArtifactArchive: (input) =>
      Effect.sync(() =>
        Object.freeze({
          _tag: "Matched" as const,
          redirectReceipt: observe("DOWNLOAD", input, false)
        })
      ),
    settleAfterAbsence: (input) =>
      Effect.sync(() => {
        trace.settleOrdinals.push(input.completedAttemptOrdinal)
      })
  }
}

const topologyForAttempt = (
  attempt: 1 | 2 | 3
): ReadonlyArray<S2SStageUploadAssertionLedgerPhase> => {
  const lookup: Array<S2SStageUploadAssertionLedgerPhase> = [
    "LOOKUP_RUN_START",
    "LOOKUP_JOBS"
  ]
  for (let ordinal = 1; ordinal <= attempt; ordinal += 1) {
    lookup.push(
      `LOOKUP_ARTIFACTS_${ordinal}` as S2SStageUploadAssertionLedgerPhase,
      `LOOKUP_RUN_END_${ordinal}` as S2SStageUploadAssertionLedgerPhase
    )
  }
  return Object.freeze([
    ...lookup,
    "READBACK_RUN_START",
    "READBACK_ARTIFACT",
    "READBACK_DOWNLOAD_REDIRECT",
    "READBACK_RUN_END"
  ])
}

const appendCompleteTopology = (
  scope: S2SStageUploadAssertionPermitScope,
  attempt: 1 | 2 | 3
): Effect.Effect<void, S2SStageUploadAssertionPermitError> =>
  Effect.forEach(
    topologyForAttempt(attempt),
    (phase, index) =>
      appendS2SStageUploadAssertionLedgerEntryForTest(scope, phase, {
        githubRequestId: `DIRECT:${attempt}:${index}:${phase}`,
        receiptSha256: hash(`direct-${attempt}-${index}-${phase}`),
        observedAtUnixSeconds: CURRENT_OBSERVED_AT + index + 1
      }),
    { discard: true }
  )

it.effect(
  "runs lazy fixed attempt topologies with exact calls, observations, and settling",
  () =>
    Effect.gen(function* () {
      const expectedCalls = { 1: 8, 2: 10, 3: 12 } as const
      const expectedObservations = { 1: 7, 2: 9, 3: 11 } as const
      const expectedSettles = {
        1: [] as ReadonlyArray<1 | 2>,
        2: [1] as ReadonlyArray<1 | 2>,
        3: [1, 2] as ReadonlyArray<1 | 2>
      } as const
      for (const attempt of [1, 2, 3] as const) {
        const fixture = makeFixture()
        const trace = makeTrace()
        const probe = probeS2SStageUploadAssertionMechanicsForTest(
          fixture.permitSeed,
          fixture.capability,
          makeObserver(attempt, trace)
        )
        expect(trace.githubCalls).toEqual([])
        expect(trace.settleOrdinals).toEqual([])

        const result = yield* probe

        expect(result).toBeUndefined()
        expect(trace.githubCalls).toHaveLength(expectedCalls[attempt])
        expect(trace.postconditionObservationCount).toBe(
          expectedObservations[attempt]
        )
        expect(trace.settleOrdinals).toEqual(expectedSettles[attempt])
        expect(
          trace.githubCalls
            .filter((call) => call.operation === "ARTIFACTS")
            .map((call) => call.input)
        ).toEqual(
          Array.from({ length: attempt }, (_unused, index) => ({
            workflowRunId: WORKFLOW_RUN_ID,
            artifactName: "s2s-registration",
            successfulAttemptCandidate: index + 1
          }))
        )
        expect(
          trace.githubCalls.filter(
            (call) => call.operation === "DOWNLOAD"
          )
        ).toEqual([
          {
            operation: "DOWNLOAD",
            input: {
              artifactId: 9_433_344_546,
              maximumBytes:
                S2S_STAGE_ARTIFACT_SPECS.REGISTER.maximumArchiveBytes
            }
          }
        ])
        expect(
          trace.githubCalls
            .filter((call) => call.operation === "RUN")
            .map((call) => call.input)
        ).toEqual([
          {
            phase: "LOOKUP_RUN_START",
            workflowRunId: WORKFLOW_RUN_ID
          },
          ...Array.from({ length: attempt }, (_unused, index) => ({
            phase: `LOOKUP_RUN_END_${index + 1}`,
            workflowRunId: WORKFLOW_RUN_ID
          })),
          {
            phase: "READBACK_RUN_START",
            workflowRunId: WORKFLOW_RUN_ID
          },
          {
            phase: "READBACK_RUN_END",
            workflowRunId: WORKFLOW_RUN_ID
          }
        ])
      }
    })
)

it.effect(
  "closes a probe fixture permanently and cannot replenish it",
  () =>
    Effect.gen(function* () {
      const fixture = makeFixture()
      const trace = makeTrace()
      const observer = makeObserver(1, trace)
      const first = probeS2SStageUploadAssertionMechanicsForTest(
        fixture.permitSeed,
        fixture.capability,
        observer
      )
      yield* first
      expect(trace.githubCalls).toHaveLength(8)

      const retry = yield* first.pipe(Effect.either)

      expectPermitReason(retry, "SCOPE_CLOSED")
      expect(trace.githubCalls).toHaveLength(8)
      expect(trace.settleOrdinals).toEqual([])
    })
)

it.effect(
  "stops after bracketing a nonhealthy listing with a fresh run observation",
  () =>
    Effect.gen(function* () {
      const fixture = makeFixture()
      const trace = makeTrace()
      let receiptOrdinal = 0
      const observation = (
        operation: string,
        input: unknown
      ): S2SStageUploadAssertionLedgerObservation => {
        trace.githubCalls.push({ operation, input })
        trace.postconditionObservationCount += 1
        receiptOrdinal += 1
        return {
          githubRequestId: `NONHEALTHY:${receiptOrdinal}`,
          receiptSha256: hash(`nonhealthy-${receiptOrdinal}`),
          observedAtUnixSeconds: CURRENT_OBSERVED_AT + receiptOrdinal
        }
      }
      const observer: S2SStageUploadAssertionTestObserver = {
        observeWorkflowRun: (input) =>
          Effect.sync(() => observation("RUN", input)),
        observeWorkflowAttemptJobs: (input) =>
          Effect.sync(() => observation("JOBS", input)),
        observeRunArtifacts: (input) =>
          Effect.sync(() => ({
            _tag: "NonHealthy" as const,
            observation: observation("ARTIFACTS", input),
            outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const
          })),
        observeArtifact: () =>
          Effect.dieMessage("artifact read must not run"),
        downloadArtifactArchive: () =>
          Effect.dieMessage("download must not run"),
        settleAfterAbsence: () =>
          Effect.dieMessage("settling must not run")
      }

      yield* probeS2SStageUploadAssertionMechanicsForTest(
        fixture.permitSeed,
        fixture.capability,
        observer
      )

      expect(trace.githubCalls.map((call) => call.operation)).toEqual([
        "RUN",
        "JOBS",
        "ARTIFACTS",
        "RUN"
      ])
      expect(trace.postconditionObservationCount).toBe(4)
      expect(trace.settleOrdinals).toEqual([])
  })
)

it.effect(
  "seals only the exact 12, 14, and 16 entry ledgers and spends healthy use once",
  () =>
    Effect.gen(function* () {
      for (const attempt of [1, 2, 3] as const) {
        const { scope } = makeScope()
        const result = yield* useS2SStageUploadAssertionPermitForTest(
          scope,
          () =>
            Effect.gen(function* () {
              yield* appendCompleteTopology(scope, attempt)
              const evidence =
                yield* snapshotS2SStageUploadAssertionPermitEvidenceForTest(
                  scope
                )
              return {
                outcome:
                  "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
                value: evidence
              }
            })
        )

        expect(result.classification._tag).toBe("Healthy")
        expect(result.value.authorityScope).toBe(
          "TEST_ONLY_NON_AUTHORIZING"
        )
        expect(result.value.authorizationClaimed).toBe(false)
        expect(result.value.crossWorkerReplayPreventionClaimed).toBe(false)
        expect(result.value.ledgerCapacity).toBe(16)
        expect(result.value.ledgerEntries).toHaveLength(10 + 2 * attempt)
        expect(result.value.ledgerEntries.at(-1)?.phase).toBe(
          "READBACK_RUN_END"
        )

        let retryCallbackCalls = 0
        const retry = yield* useS2SStageUploadAssertionPermitForTest(
          scope,
          () =>
            Effect.sync(() => {
              retryCallbackCalls += 1
              return {
                outcome:
                  "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
                value: null
              }
            })
        ).pipe(Effect.either)
        expectPermitReason(retry, "PERMIT_ALREADY_SPENT")
        expect(retryCallbackCalls).toBe(0)
      }
    })
)

it.effect(
  "rejects an early forged Healthy completion and irreversibly voids the stage",
  () =>
    Effect.gen(function* () {
      const { scope } = makeScope()
      const forged = yield* useS2SStageUploadAssertionPermitForTest(
        scope,
        () =>
          Effect.succeed({
            outcome:
              "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
            value: "forged"
          })
      ).pipe(Effect.either)

      expectPermitReason(forged, "EVIDENCE_NOT_SEALABLE")
      const retry = yield* useS2SStageUploadAssertionPermitForTest(
        scope,
        () =>
          Effect.succeed({
            outcome:
              "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
            value: null
          })
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
    })
)

it.effect(
  "atomically admits one Deferred-latched winner and never runs the loser callback",
  () =>
    Effect.gen(function* () {
      const { scope } = makeScope()
      const started = yield* Deferred.make<void>()
      const release = yield* Deferred.make<void>()
      let loserCallbackCalls = 0
      const winner = yield* useS2SStageUploadAssertionPermitForTest(
        scope,
        () =>
          Deferred.succeed(started, undefined).pipe(
            Effect.zipRight(Deferred.await(release)),
            Effect.zipRight(appendCompleteTopology(scope, 1)),
            Effect.as({
              outcome:
                "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
              value: "winner"
            })
          )
      ).pipe(Effect.fork)
      yield* Deferred.await(started)

      const loser = yield* useS2SStageUploadAssertionPermitForTest(
        scope,
        () =>
          Effect.sync(() => {
            loserCallbackCalls += 1
            return {
              outcome:
                "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
              value: "loser"
            }
          })
      ).pipe(Effect.either)
      expectPermitReason(loser, "PERMIT_IN_FLIGHT")
      expect(loserCallbackCalls).toBe(0)

      yield* Deferred.succeed(release, undefined)
      const won = yield* Fiber.join(winner)
      expect(won.value).toBe("winner")
      expect(won.classification._tag).toBe("Healthy")

      const retry = yield* useS2SStageUploadAssertionPermitForTest(
        scope,
        () => Effect.dieMessage("spent callback must not run")
      ).pipe(Effect.either)
      expectPermitReason(retry, "PERMIT_ALREADY_SPENT")
    })
)

it.effect(
  "does not let a losing public probe close the Deferred-latched winner",
  () =>
    Effect.gen(function* () {
      const fixture = makeFixture()
      const started = yield* Deferred.make<void>()
      const release = yield* Deferred.make<void>()
      const winnerTrace = makeTrace()
      const winnerBase = makeObserver(1, winnerTrace)
      let winnerRunCalls = 0
      const winnerObserver: S2SStageUploadAssertionTestObserver = {
        ...winnerBase,
        observeWorkflowRun: (input) => {
          winnerRunCalls += 1
          const observed = winnerBase.observeWorkflowRun(input)
          return winnerRunCalls === 1
            ? Deferred.succeed(started, undefined).pipe(
                Effect.zipRight(Deferred.await(release)),
                Effect.zipRight(observed)
              )
            : observed
        }
      }
      const winner = yield* probeS2SStageUploadAssertionMechanicsForTest(
        fixture.permitSeed,
        fixture.capability,
        winnerObserver
      ).pipe(Effect.fork)
      yield* Deferred.await(started)

      const loserTrace = makeTrace()
      const loser = yield* probeS2SStageUploadAssertionMechanicsForTest(
        fixture.permitSeed,
        fixture.capability,
        makeObserver(1, loserTrace)
      ).pipe(Effect.either)
      expectPermitReason(loser, "PERMIT_IN_FLIGHT")
      expect(loserTrace.githubCalls).toEqual([])

      yield* Deferred.succeed(release, undefined)
      yield* Fiber.join(winner)
      expect(winnerTrace.githubCalls).toHaveLength(8)

      const closedTrace = makeTrace()
      const closed = yield* probeS2SStageUploadAssertionMechanicsForTest(
        fixture.permitSeed,
        fixture.capability,
        makeObserver(1, closedTrace)
      ).pipe(Effect.either)
      expectPermitReason(closed, "SCOPE_CLOSED")
      expect(closedTrace.githubCalls).toEqual([])
  })
)

it.effect(
  "burns nonhealthy success and typed failure without rerunning callbacks",
  () =>
    Effect.gen(function* () {
      const nonhealthy = makeScope().scope
      let nonhealthyCalls = 0
      const classified = yield* useS2SStageUploadAssertionPermitForTest(
        nonhealthy,
        () =>
          Effect.sync(() => {
            nonhealthyCalls += 1
            return {
              outcome: "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION" as const,
              value: null
            }
          })
      )
      expect(classified.classification._tag).toBe(
        "ReconciliationRequired"
      )
      const nonhealthyRetry =
        yield* useS2SStageUploadAssertionPermitForTest(
          nonhealthy,
          () =>
            Effect.sync(() => {
              nonhealthyCalls += 1
              return {
                outcome:
                  "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
                value: null
              }
            })
        ).pipe(Effect.either)
      expectPermitReason(nonhealthyRetry, "STAGE_VOID")
      expect(nonhealthyCalls).toBe(1)

      const typedFailure = makeScope().scope
      let typedCalls = 0
      const failed = yield* useS2SStageUploadAssertionPermitForTest(
        typedFailure,
        () =>
          Effect.sync(() => {
            typedCalls += 1
          }).pipe(Effect.zipRight(Effect.fail("typed-failure" as const)))
      ).pipe(Effect.either)
      expect(failed).toEqual(Either.left("typed-failure"))
      const typedRetry = yield* useS2SStageUploadAssertionPermitForTest(
        typedFailure,
        () =>
          Effect.sync(() => {
            typedCalls += 1
            return {
              outcome:
                "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
              value: null
            }
          })
      ).pipe(Effect.either)
      expectPermitReason(typedRetry, "STAGE_VOID")
      expect(typedCalls).toBe(1)
    })
)

it.effect("burns defects and preserves the original Cause", () =>
  Effect.gen(function* () {
    const { scope } = makeScope()
    let callbackCalls = 0
    const failed = yield* Effect.exit(
      useS2SStageUploadAssertionPermitForTest(scope, () =>
        Effect.sync(() => {
          callbackCalls += 1
        }).pipe(Effect.zipRight(Effect.dieMessage("observer defect")))
      )
    )
    expect(Exit.isFailure(failed)).toBe(true)
    if (Exit.isFailure(failed)) {
      expect(Cause.isDieType(failed.cause)).toBe(true)
    }

    const retry = yield* useS2SStageUploadAssertionPermitForTest(
      scope,
      () =>
        Effect.sync(() => {
          callbackCalls += 1
          return {
            outcome:
              "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
            value: null
          }
        })
    ).pipe(Effect.either)
    expectPermitReason(retry, "STAGE_VOID")
    expect(callbackCalls).toBe(1)
  })
)

it.effect("burns interruption and preserves the interrupted Cause", () =>
  Effect.gen(function* () {
    const { scope } = makeScope()
    const started = yield* Deferred.make<void>()
    let callbackCalls = 0
    const fiber = yield* useS2SStageUploadAssertionPermitForTest(
      scope,
      () =>
        Effect.sync(() => {
          callbackCalls += 1
        }).pipe(
          Effect.zipRight(Deferred.succeed(started, undefined)),
          Effect.zipRight(Effect.never)
        )
    ).pipe(Effect.fork)
    yield* Deferred.await(started)
    const interrupted = yield* Fiber.interrupt(fiber)
    expect(Exit.isFailure(interrupted)).toBe(true)
    if (Exit.isFailure(interrupted)) {
      expect(Cause.isInterruptedOnly(interrupted.cause)).toBe(true)
    }

    const retry = yield* useS2SStageUploadAssertionPermitForTest(
      scope,
      () =>
        Effect.sync(() => {
          callbackCalls += 1
          return {
            outcome:
              "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
            value: null
          }
        })
    ).pipe(Effect.either)
    expectPermitReason(retry, "STAGE_VOID")
    expect(callbackCalls).toBe(1)
  })
)

it.effect(
  "rejects phase, request, receipt, time, and capacity violations without eviction",
  () =>
    Effect.gen(function* () {
      const { scope } = makeScope()
      const classified =
        yield* useS2SStageUploadAssertionPermitForTest(
          scope,
          () =>
            Effect.gen(function* () {
              const outOfOrder =
                yield* appendS2SStageUploadAssertionLedgerEntryForTest(
                  scope,
                  "LOOKUP_JOBS",
                  {
                    githubRequestId: "STRICT:OUT-OF-ORDER",
                    receiptSha256: hash("strict-out-of-order"),
                    observedAtUnixSeconds: CURRENT_OBSERVED_AT
                  }
                ).pipe(Effect.either)
              expectPermitReason(outOfOrder, "LEDGER_ENTRY_REJECTED")

              const first = {
                githubRequestId: "STRICT:FIRST",
                receiptSha256: hash("strict-first"),
                observedAtUnixSeconds: CURRENT_OBSERVED_AT
              }
              yield* appendS2SStageUploadAssertionLedgerEntryForTest(
                scope,
                "LOOKUP_RUN_START",
                first
              )
              const duplicateRequest =
                yield* appendS2SStageUploadAssertionLedgerEntryForTest(
                  scope,
                  "LOOKUP_JOBS",
                  {
                    githubRequestId: first.githubRequestId,
                    receiptSha256: hash("strict-unique-receipt"),
                    observedAtUnixSeconds: CURRENT_OBSERVED_AT + 1
                  }
                ).pipe(Effect.either)
              expectPermitReason(duplicateRequest, "REQUEST_ID_REUSED")

              const duplicateReceipt =
                yield* appendS2SStageUploadAssertionLedgerEntryForTest(
                  scope,
                  "LOOKUP_JOBS",
                  {
                    githubRequestId: "STRICT:UNIQUE-REQUEST",
                    receiptSha256: first.receiptSha256,
                    observedAtUnixSeconds: CURRENT_OBSERVED_AT + 1
                  }
                ).pipe(Effect.either)
              expectPermitReason(duplicateReceipt, "RECEIPT_HASH_REUSED")

              const rollback =
                yield* appendS2SStageUploadAssertionLedgerEntryForTest(
                  scope,
                  "LOOKUP_JOBS",
                  {
                    githubRequestId: "STRICT:ROLLBACK",
                    receiptSha256: hash("strict-rollback"),
                    observedAtUnixSeconds: CURRENT_OBSERVED_AT - 1
                  }
                ).pipe(Effect.either)
              expectPermitReason(rollback, "OBSERVATION_ORDER_INVALID")

              const prematureSeal =
                yield* snapshotS2SStageUploadAssertionPermitEvidenceForTest(
                  scope
                ).pipe(Effect.either)
              expectPermitReason(prematureSeal, "EVIDENCE_NOT_SEALABLE")
              return {
                outcome:
                  "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE" as const,
                value: null
              }
            })
        )
      expect(classified.classification._tag).toBe("DefinitiveFailure")

      const full = makeScope().scope
      yield* useS2SStageUploadAssertionPermitForTest(
        full,
        () =>
          Effect.gen(function* () {
            yield* appendCompleteTopology(full, 3)
            const overflow =
              yield* appendS2SStageUploadAssertionLedgerEntryForTest(
                full,
                "READBACK_RUN_END",
                {
                  githubRequestId: "STRICT:OVERFLOW",
                  receiptSha256: hash("strict-overflow"),
                  observedAtUnixSeconds: CURRENT_OBSERVED_AT + 100
                }
              ).pipe(Effect.either)
            expectPermitReason(overflow, "LEDGER_CAPACITY_EXHAUSTED")
            return {
              outcome:
                "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED" as const,
              value: null
            }
          })
      )
    })
)

it("keeps production and test authority registries disjoint and rejects carrier copies", () => {
  const fixture = makeFixture()
  const copied = makeS2SStageUploadAssertionPermitTestScope(
    fixture.permitSeed,
    { ...fixture.capability }
  )
  expectPermitReason(copied, "INVALID_PREPARED_CAPABILITY")

  const proxied = makeS2SStageUploadAssertionPermitTestScope(
    fixture.permitSeed,
    new Proxy(fixture.capability, {})
  )
  expectPermitReason(proxied, "INVALID_PREPARED_CAPABILITY")

  const hostileFixture = makeS2SStageUploadAssertionPermitTestScope(
    new Proxy(fixture.permitSeed, {}),
    fixture.capability
  )
  expectPermitReason(hostileFixture, "TEST_SEED_INVALID")

  const production = claimS2SStageUploadAssertionPermitScope(
    fixture.permitSeed,
    fixture.capability
  )
  expectPermitReason(production, "INVALID_AUTHORITY")
})

it("compares sourceCommitA even when a test preparation repeats the receipt string", () => {
  const fixture = makeFixture()
  const divergentSourceCommitA = "f".repeat(40)
  const divergentSeed: S2SPreparedStageCarrierTestSeed = {
    ...fixture.preparedSeed,
    sourceCommitA: divergentSourceCommitA
  }
  const divergentCapability = right(
    makeS2SPreparedStageCarrierTestCapability(divergentSeed, {
      events: [registrationEvent(divergentSourceCommitA)]
    })
  )

  const outcome = makeS2SStageUploadAssertionPermitTestScope(
    fixture.permitSeed,
    divergentCapability
  )

  expectPermitReason(outcome, "PREPARED_CAPABILITY_BINDING_MISMATCH")
})

it("binds one fixture identity to one exact test capability object", () => {
  const fixture = makeFixture()
  const secondPreparedSeed: S2SPreparedStageCarrierTestSeed = {
    ...fixture.preparedSeed
  }
  const secondCapability = right(
    makeS2SPreparedStageCarrierTestCapability(secondPreparedSeed, {
      events: [registrationEvent()]
    })
  )
  right(
    makeS2SStageUploadAssertionPermitTestScope(
      fixture.permitSeed,
      fixture.capability
    )
  )

  const rebound = makeS2SStageUploadAssertionPermitTestScope(
    fixture.permitSeed,
    secondCapability
  )

  expectPermitReason(rebound, "PREPARED_CAPABILITY_BINDING_MISMATCH")
})

it.effect(
  "does not replenish a closed fixture when its Effect service Layer is rebuilt",
  () =>
    Effect.gen(function* () {
      const fixture = makeFixture()
      const trace = makeTrace()
      const observer = makeObserver(1, trace)
      let serviceInstances = 0
      const freshLayer = () =>
        Layer.sync(AssertionMechanicsTestService, () => {
          serviceInstances += 1
          return {
            run: probeS2SStageUploadAssertionMechanicsForTest(
              fixture.permitSeed,
              fixture.capability,
              observer
            )
          }
        })
      const invoke = Effect.flatMap(
        AssertionMechanicsTestService,
        (service) => service.run
      )

      yield* invoke.pipe(Effect.provide(freshLayer()))
      const recreated = yield* invoke.pipe(
        Effect.provide(freshLayer()),
        Effect.either
      )

      expectPermitReason(recreated, "SCOPE_CLOSED")
      expect(serviceInstances).toBe(2)
      expect(trace.githubCalls).toHaveLength(8)
    })
)

it("keeps every TEST_ONLY_NON_AUTHORIZING mechanics entrypoint out of the package root", () => {
  for (const name of [
    "S2SStageUploadAssertion",
    "appendS2SStageUploadAssertionLedgerEntryForTest",
    "claimS2SStageUploadAssertionPermitScope",
    "closeS2SStageUploadAssertionPermitScope",
    "inspectS2SStageUploadAssertionCompletion",
    "inspectS2SStageUploadAssertionCompletionForTest",
    "inspectS2SStageUploadAssertionReplay",
    "inspectS2SStageUploadAssertionReplayForTest",
    "makeS2SStageUploadAssertionLiveLayer",
    "makeS2SStageUploadAssertionPermitTestScope",
    "makeS2SStageUploadAssertionTestLayer",
    "materializeS2SStageUploadAssertionReplay",
    "materializeS2SStageUploadAssertionReplayForTest",
    "probeS2SStageUploadAssertionMechanicsForTest",
    "probeS2SProductionProcessContinuityGateForTest",
    "probeS2SStageUploadAssertionShellForTest",
    "probeS2SStageUploadAssertionWholeTimeoutForTest",
    "snapshotS2SStageUploadAssertionPermitEvidenceForTest",
    "useS2SStageUploadAssertionPermitForTest",
    "buildS2SStageUploadPostconditionFromProductionShell"
  ]) {
    expect(name in PublicApi).toBe(false)
  }
})

it.effect(
  "fails the production root at the workflow-source gate before config, capability, current-run, observer, or I/O access",
  () =>
    Effect.gen(function* () {
      const fixture = makeFixture()
      let capabilityReads = 0
      let configReads = 0
      let currentRunReads = 0
      const capability = new Proxy(fixture.capability, {
        get: (target, property, receiver) => {
          capabilityReads += 1
          return Reflect.get(target, property, receiver)
        }
      })
      const config = {}
      Object.defineProperty(config, "token", {
        enumerable: true,
        get: () => {
          configReads += 1
          throw new Error("production gate must not read config")
        }
      })
      const exit = yield* Effect.gen(function* () {
        const assertion = yield* S2SStageUploadAssertion
        return yield* assertion.assertAndRecover
      }).pipe(
        Effect.provide(
          makeS2SStageUploadAssertionLiveLayer(
            capability,
            config as { readonly token: string }
          )
        ),
        Effect.provideService(
          S2SCurrentRunStage,
          S2SCurrentRunStage.of({
            get authority(): never {
              currentRunReads += 1
              throw new Error("production gate must not read current-run")
            }
          })
        ),
        Effect.exit
      )
      expect(Exit.isFailure(exit)).toBe(true)
      if (Exit.isFailure(exit)) {
        const failure = Cause.failureOption(exit.cause)
        expect(failure._tag).toBe("Some")
        if (failure._tag === "Some") {
          expect(failure.value).toMatchObject({
            _tag: "S2SCurrentRunInputError",
            reason: "WORKFLOW_SOURCE_BYTES_OPEN"
          })
        }
      }
      expect(capabilityReads).toBe(0)
      expect(configReads).toBe(0)
      expect(currentRunReads).toBe(0)
    })
)

it("independently keeps process continuity open when the workflow-source premise is treated as closed", () => {
  const result = probeS2SProductionProcessContinuityGateForTest()
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) {
    expect(result.left).toMatchObject({
      _tag: "S2SStageUploadAssertionPermitError",
      reason: "PRODUCTION_PROCESS_CONTINUITY_OPEN"
    })
  }
})

interface FullAssertionTrace {
  readonly calls: Array<string>
  readonly selectors: Array<{
    readonly operation: string
    readonly input: unknown
  }>
}

interface FullAssertionScenario {
  readonly fixture: Fixture
  readonly archive: Uint8Array
  readonly trace: FullAssertionTrace
  readonly observer: S2SGitHubObserver["Type"]
}

interface FullArtifactJson {
  readonly id: number
  readonly name: string
  readonly size_in_bytes: number
  readonly digest: string
  readonly expired: boolean
  readonly created_at: string
  readonly expires_at: string
  readonly workflow_run: {
    readonly id: number
    readonly head_sha: string
  }
}

interface FullAssertionScenarioOptions {
  readonly memberTransform?: (
    members: ReadonlyArray<{
      readonly name: string
      readonly bytes: Uint8Array
    }>
  ) => ReadonlyArray<{
    readonly name: string
    readonly bytes: Uint8Array
  }>
  readonly archiveTransform?: (archive: Uint8Array) => Uint8Array
  readonly artifactTransform?: (
    artifact: FullArtifactJson
  ) => FullArtifactJson
  readonly listingTransform?: (
    ordinal: number,
    artifact: FullArtifactJson,
    listing: ReadonlyArray<FullArtifactJson>
  ) => ReadonlyArray<FullArtifactJson>
  readonly requeryTransform?: (
    artifact: FullArtifactJson
  ) => FullArtifactJson
  readonly runTransform?: (
    ordinal: number,
    run: ReturnType<typeof fullRunJson>
  ) => ReturnType<typeof fullRunJson>
  readonly finalRunTransform?: (
    run: ReturnType<typeof fullRunJson>
  ) => ReturnType<typeof fullRunJson>
  readonly jobsTransform?: (
    jobs: ReturnType<typeof fullJobsJson>
  ) => ReturnType<typeof fullJobsJson>
  readonly downloadedAtUnixSeconds?: number
  readonly downloadedArchiveSha256?: string
  readonly downloadArtifactId?: number
  readonly downloadEndpointPathAndQuery?: string
  readonly downloadRedirectHttpStatus?: number
  readonly downloadArchiveMediaType?: string
  readonly downloadArchiveByteLength?: number
}

const fullJsonBytes = (value: unknown): Uint8Array =>
  ENCODER.encode(`${JSON.stringify(value)}\n`)

const utc = (unixSeconds: number): string =>
  new Date(unixSeconds * 1_000).toISOString().replace(".000Z", "Z")

const fullResponseProvenance = (githubRequestId: string) =>
  Object.freeze({
    githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: `W/"${hash(githubRequestId)}"`
  })

const fullRunJson = () => ({
  id: WORKFLOW_RUN_ID,
  run_attempt: 1,
  name: "SWM-0W-S2S confirmatory",
  path: S2S_CONFIRMATORY_WORKFLOW_PATH,
  event: "push",
  head_branch: "main",
  head_sha: REGISTRATION_COMMIT_B,
  repository: { full_name: S2S_GITHUB_REPOSITORY },
  head_repository: { full_name: S2S_GITHUB_REPOSITORY },
  status: "in_progress",
  conclusion: null,
  created_at: WORKFLOW_CREATED_AT
})

const fullJobsJson = (stage: S2SConfirmatoryJobStage = "REGISTER") => {
  const currentOrdinal = {
    REGISTER: 0,
    CONFIRM: 1,
    ADJUDICATE: 2
  }[stage]
  const names = ["register", "confirm", "adjudicate"] as const
  return {
    total_count: 3,
    jobs: names.map((name, ordinal) => ({
      id: REGISTER_JOB_DATABASE_ID + ordinal,
      run_id: WORKFLOW_RUN_ID,
      run_attempt: 1,
      name,
      head_sha: REGISTRATION_COMMIT_B,
      status:
        ordinal < currentOrdinal
          ? "completed"
          : ordinal === currentOrdinal
            ? "in_progress"
            : "queued",
      conclusion: ordinal < currentOrdinal ? "success" : null,
      started_at: utc(WORKFLOW_CREATED_AT_UNIX_SECONDS + 10 + ordinal * 10),
      completed_at:
        ordinal < currentOrdinal
          ? utc(WORKFLOW_CREATED_AT_UNIX_SECONDS + 15 + ordinal * 10)
          : null,
      labels: ["ubuntu-24.04"]
    }))
  }
}

type FullJobsJson = ReturnType<typeof fullJobsJson>
type FullJobJson = FullJobsJson["jobs"][number]

const patchFullJob = (
  jobs: FullJobsJson,
  name: FullJobJson["name"],
  patch: Partial<FullJobJson>
): FullJobsJson => ({
  ...jobs,
  jobs: jobs.jobs.map((job) =>
    job.name === name ? { ...job, ...patch } : job
  )
})

const makeFullAssertionScenario = (
  successfulAttemptOrdinal: 1 | 2 | 3 | null,
  stage: S2SConfirmatoryJobStage = "REGISTER",
  carrierInput?: unknown,
  options: FullAssertionScenarioOptions = {}
): FullAssertionScenario => {
  const fixture =
    carrierInput === undefined
      ? makeFixture(stage)
      : makeFixture(stage, carrierInput)
  const prepared = right(
    inspectS2SPreparedStageCarrierTestCapability(fixture.capability)
  )
  const baseMembers = prepared.members.map((member) => ({
      name: member.name,
      bytes: member.readBytes()
    }))
  const archiveMembers = options.memberTransform === undefined
    ? baseMembers
    : options.memberTransform(baseMembers)
  const preparedArchive = buildS2STestActionZip(archiveMembers)
  const archive = options.archiveTransform === undefined
    ? preparedArchive
    : options.archiveTransform(Uint8Array.from(preparedArchive))
  const artifactId = 9_433_344_546
  const baseArtifact: FullArtifactJson = {
    id: artifactId,
    name: prepared.artifactName,
    size_in_bytes: archive.byteLength,
    digest: `sha256:${rawS2SFileSha256(archive)}`,
    expired: false,
    created_at: utc(WORKFLOW_CREATED_AT_UNIX_SECONDS + 1_000),
    expires_at: utc(WORKFLOW_CREATED_AT_UNIX_SECONDS + 8_000_000),
    workflow_run: {
      id: WORKFLOW_RUN_ID,
      head_sha: REGISTRATION_COMMIT_B
    }
  }
  const artifact = options.artifactTransform === undefined
    ? baseArtifact
    : options.artifactTransform(baseArtifact)
  const trace: FullAssertionTrace = { calls: [], selectors: [] }
  let metadataOrdinal = 0
  let artifactListOrdinal = 0
  let runOrdinal = 0
  const metadata = (operation: string, input: unknown) => {
    metadataOrdinal += 1
    trace.calls.push(operation)
    trace.selectors.push(Object.freeze({ operation, input }))
    const githubRequestId =
      `FULL:${successfulAttemptOrdinal ?? "ABSENT"}:${metadataOrdinal}:${operation}`
    return Object.freeze({
      observedAtUnixSeconds: CURRENT_OBSERVED_AT + metadataOrdinal * 10,
      provenance: fullResponseProvenance(githubRequestId)
    })
  }
  const observer = S2SGitHubObserver.of({
    observeWorkflowRun: (workflowRunId) =>
      Effect.sync(() => {
        const next = metadata("RUN", { workflowRunId })
        runOrdinal += 1
        let run = options.runTransform === undefined
          ? fullRunJson()
          : options.runTransform(runOrdinal, fullRunJson())
        if (
          options.finalRunTransform !== undefined &&
          successfulAttemptOrdinal !== null &&
          runOrdinal === successfulAttemptOrdinal + 3
        ) {
          run = options.finalRunTransform(run)
        }
        return right(
          observeS2SGitHubWorkflowRun(
            fullJsonBytes(run),
            workflowRunId,
            next.observedAtUnixSeconds,
            next.provenance
          )
        )
      }),
    observeWorkflowAttemptJobs: (workflowRunId) =>
      Effect.sync(() => {
        const next = metadata("JOBS", {
          workflowRunId,
          workflowRunAttempt: 1
        })
        const baseJobs = fullJobsJson(stage)
        const jobs = options.jobsTransform === undefined
          ? baseJobs
          : options.jobsTransform(baseJobs)
        return right(
          observeS2SGitHubWorkflowAttemptJobs(
            fullJsonBytes(jobs),
            workflowRunId,
            1,
            next.observedAtUnixSeconds,
            next.provenance
          )
        )
      }),
    observeWorkflowRunsForHead: () =>
      Effect.dieMessage("assertion shell must not query runs-for-head"),
    observeRunArtifacts: (workflowRunId) =>
      Effect.sync(() => {
        artifactListOrdinal += 1
        const next = metadata("ARTIFACTS", { workflowRunId })
        const defaultArtifacts =
          artifactListOrdinal === successfulAttemptOrdinal ? [artifact] : []
        const artifacts = options.listingTransform === undefined
          ? defaultArtifacts
          : options.listingTransform(
              artifactListOrdinal,
              artifact,
              defaultArtifacts
            )
        return right(
          observeS2SGitHubRunArtifacts(
            fullJsonBytes({ total_count: artifacts.length, artifacts }),
            workflowRunId,
            next.observedAtUnixSeconds,
            next.provenance
          )
        )
      }),
    observeArtifact: (requestedArtifactId) =>
      Effect.sync(() => {
        const next = metadata("ARTIFACT", {
          artifactId: requestedArtifactId
        })
        const requeried = options.requeryTransform === undefined
          ? artifact
          : options.requeryTransform(artifact)
        return right(
          observeS2SGitHubArtifact(
            fullJsonBytes(requeried),
            requestedArtifactId,
            next.observedAtUnixSeconds,
            next.provenance
          )
        )
      }),
    downloadArtifactArchive: (
      requestedArtifactId,
      _maximumArchiveBytes
    ) =>
      Effect.sync(() => {
        trace.calls.push("DOWNLOAD")
        trace.selectors.push(
          Object.freeze({
            operation: "DOWNLOAD",
            input: {
              artifactId: requestedArtifactId,
              maximumArchiveBytes: _maximumArchiveBytes
            }
          })
        )
        const core: Omit<
          S2SGitHubArtifactDownloadReceipt,
          "receiptSha256"
        > = Object.freeze({
          schemaVersion: S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
          apiVersion: S2S_GITHUB_API_VERSION,
          repository: S2S_GITHUB_REPOSITORY,
          artifactId: options.downloadArtifactId ?? requestedArtifactId,
          endpointPathAndQuery:
            options.downloadEndpointPathAndQuery ??
              `/repos/${S2S_GITHUB_REPOSITORY}/actions/artifacts/${requestedArtifactId}/zip`,
          downloadedAtUnixSeconds:
            options.downloadedAtUnixSeconds ??
              CURRENT_OBSERVED_AT + metadataOrdinal * 10 + 5,
          redirectHttpStatus:
            (options.downloadRedirectHttpStatus ?? 302) as 302,
          redirectGitHubRequestId:
            `FULL:${successfulAttemptOrdinal ?? "ABSENT"}:DOWNLOAD`,
          redirectGitHubApiVersionSelected: S2S_GITHUB_API_VERSION,
          redirectResponseEtag: null,
          redirectUrlSha256: hash("full-redirect-url"),
          redirectOrigin: "https://objects.example.invalid",
          archiveHttpStatus: 200,
          archiveMediaType:
            (options.downloadArchiveMediaType ?? "application/zip") as
              S2SGitHubArtifactDownloadReceipt["archiveMediaType"],
          archiveResponseEtag: `"${hash("full-archive-etag")}"`,
          archiveByteLength:
            options.downloadArchiveByteLength ?? archive.byteLength,
          downloadedArchiveSha256:
            options.downloadedArchiveSha256 ?? rawS2SFileSha256(archive)
        })
        const bytes = Uint8Array.from(archive)
        const download: S2SGitHubArtifactDownload = Object.freeze({
          receipt: Object.freeze({
            ...core,
            receiptSha256: right(canonicalS2SControlSha256(core))
          }),
          readArchiveBytes: (): Uint8Array => Uint8Array.from(bytes)
        })
        return download
      })
  })
  return Object.freeze({ fixture, archive, trace, observer })
}

const waitForScheduledSleeps = (
  expectedCount: number,
  remainingYields = 2_000
): Effect.Effect<void> =>
  TestClock.sleeps().pipe(
    Effect.flatMap((sleeps) =>
      Chunk.size(sleeps) >= expectedCount
        ? Effect.void
        : remainingYields <= 0
          ? Effect.dieMessage("expected logical sleep was not scheduled")
          : Effect.yieldNow().pipe(
              Effect.zipRight(
                waitForScheduledSleeps(expectedCount, remainingYields - 1)
              )
            )
    )
  )

const waitForSettleSleep = (): Effect.Effect<void> =>
  waitForScheduledSleeps(2)

const waitForScheduledDeadline = (
  expectedDeadline: number,
  remainingYields = 2_000
): Effect.Effect<void> =>
  TestClock.sleeps().pipe(
    Effect.flatMap((sleeps) =>
      Chunk.toReadonlyArray(sleeps).includes(expectedDeadline)
        ? Effect.void
        : remainingYields <= 0
          ? Effect.dieMessage("expected logical deadline was not scheduled")
          : Effect.yieldNow().pipe(
              Effect.zipRight(
                waitForScheduledDeadline(
                  expectedDeadline,
                  remainingYields - 1
                )
              )
            )
    )
  )

const waitForScenarioSettle = (
  scenario: FullAssertionScenario,
  expectedDeadline: number,
  expectedCallCount: number,
  remainingYields = 2_000
): Effect.Effect<void> =>
  TestClock.sleeps().pipe(
    Effect.flatMap((sleeps) =>
      Chunk.toReadonlyArray(sleeps).includes(expectedDeadline) &&
      scenario.trace.calls.length === expectedCallCount
        ? Effect.void
        : remainingYields <= 0
          ? Effect.dieMessage("expected settle boundary was not reached")
          : Effect.yieldNow().pipe(
              Effect.zipRight(
                waitForScenarioSettle(
                  scenario,
                  expectedDeadline,
                  expectedCallCount,
                  remainingYields - 1
                )
              )
            )
    )
  )

const waitForTraceCallCount = (
  scenario: FullAssertionScenario,
  expectedMinimum: number,
  remainingYields = 2_000
): Effect.Effect<void> =>
  scenario.trace.calls.length >= expectedMinimum
    ? Effect.void
    : remainingYields <= 0
      ? Effect.dieMessage("expected observer call was not reached")
      : Effect.yieldNow().pipe(
          Effect.zipRight(
            waitForTraceCallCount(
              scenario,
              expectedMinimum,
              remainingYields - 1
            )
          )
        )

const runFullScenario = (
  scenario: FullAssertionScenario,
  settleCount: 0 | 1 | 2
) =>
  Effect.gen(function* () {
    const startedAt = yield* Clock.currentTimeMillis
    const fiber = yield* probeS2SStageUploadAssertionShellForTest(
      scenario.fixture.permitSeed,
      scenario.fixture.capability,
      scenario.observer
    ).pipe(Effect.fork)
    for (let index = 0; index < settleCount; index += 1) {
      const callsBeforeSettle = 4 + index * 2
      yield* waitForScenarioSettle(
        scenario,
        startedAt + (index + 1) * 10_000,
        callsBeforeSettle
      )
      expect(scenario.trace.calls).toHaveLength(callsBeforeSettle)
      yield* TestClock.adjust(9_999)
      expect((yield* Fiber.poll(fiber))._tag).toBe("None")
      expect(scenario.trace.calls).toHaveLength(callsBeforeSettle)
      yield* TestClock.adjust(1)
      yield* waitForTraceCallCount(scenario, callsBeforeSettle + 1)
      expect(scenario.trace.calls[callsBeforeSettle]).toBe("ARTIFACTS")
    }
    return yield* Fiber.join(fiber)
  })

it.effect(
  "runs the real-observation full shell at attempts 1/2/3 and authenticates defensive completion replay",
  () =>
    Effect.gen(function* () {
      for (const attempt of [1, 2, 3] as const) {
        const scenario = makeFullAssertionScenario(attempt)
        const completion = yield* runFullScenario(
          scenario,
          (attempt - 1) as 0 | 1 | 2
        )
        const snapshot =
          yield* inspectS2SStageUploadAssertionCompletionForTest(
            scenario.fixture.permitSeed,
            scenario.fixture.capability,
            completion
          )
        expect(scenario.trace.calls).toHaveLength(6 + 2 * attempt)
        expect(scenario.trace.selectors).toEqual([
          { operation: "RUN", input: { workflowRunId: WORKFLOW_RUN_ID } },
          {
            operation: "JOBS",
            input: {
              workflowRunId: WORKFLOW_RUN_ID,
              workflowRunAttempt: 1
            }
          },
          ...Array.from({ length: attempt }, () => [
            {
              operation: "ARTIFACTS",
              input: { workflowRunId: WORKFLOW_RUN_ID }
            },
            {
              operation: "RUN",
              input: { workflowRunId: WORKFLOW_RUN_ID }
            }
          ]).flat(),
          { operation: "RUN", input: { workflowRunId: WORKFLOW_RUN_ID } },
          {
            operation: "ARTIFACT",
            input: { artifactId: 9_433_344_546 }
          },
          {
            operation: "DOWNLOAD",
            input: {
              artifactId: 9_433_344_546,
              maximumArchiveBytes:
                S2S_STAGE_ARTIFACT_SPECS.REGISTER.maximumArchiveBytes
            }
          },
          { operation: "RUN", input: { workflowRunId: WORKFLOW_RUN_ID } }
        ])
        expect(snapshot.postcondition.observations).toHaveLength(5 + 2 * attempt)
        expect(snapshot.postcondition.assertionPermitEvidence.ledgerEntries)
          .toHaveLength(10 + 2 * attempt)
        expect(snapshot.authorizationClaimed).toBe(false)
        expect(snapshot.outcome).toBe(
          "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
        )
        const completionArchive = snapshot.readCurrentStageArchiveBytes()
        completionArchive[0] = completionArchive[0] === 0 ? 1 : 0
        expect(snapshot.readCurrentStageArchiveBytes()).toEqual(
          scenario.archive
        )
        const completionCarrier = snapshot.readPostconditionCarrierBytes()
        completionCarrier[0] = completionCarrier[0] === 0 ? 1 : 0
        expect(
          rawS2SFileSha256(snapshot.readPostconditionCarrierBytes())
        ).toBe(snapshot.postconditionCarrierSha256)
        const replay =
          yield* materializeS2SStageUploadAssertionReplayForTest(
            scenario.fixture.permitSeed,
            scenario.fixture.capability,
            completion
          )
        const inspectedReplay =
          yield* inspectS2SStageUploadAssertionReplayForTest(
            scenario.fixture.permitSeed,
            scenario.fixture.capability,
            replay
          )
        expect(inspectedReplay.authorizationClaimed).toBe(false)
        const firstArchive = inspectedReplay.readCurrentStageArchiveBytes()
        firstArchive[0] = firstArchive[0] === 0 ? 1 : 0
        expect(inspectedReplay.readCurrentStageArchiveBytes()).toEqual(
          scenario.archive
        )
        const replayCarrier = inspectedReplay.readPostconditionCarrierBytes()
        replayCarrier[0] = replayCarrier[0] === 0 ? 1 : 0
        expect(
          rawS2SFileSha256(inspectedReplay.readPostconditionCarrierBytes())
        ).toBe(snapshot.postconditionCarrierSha256)
        const completionCopies: ReadonlyArray<unknown> = [
          { ...completion },
          new Proxy(completion, {}),
          structuredCloneOrEmpty(completion),
          JSON.parse(JSON.stringify(completion)) as unknown
        ]
        for (const copiedCompletion of completionCopies) {
          const copyOutcome =
            yield* inspectS2SStageUploadAssertionCompletionForTest(
              scenario.fixture.permitSeed,
              scenario.fixture.capability,
              copiedCompletion
            ).pipe(Effect.either)
          expectPermitReason(copyOutcome, "INVALID_COMPLETION_CAPABILITY")
        }
        const replayCopies: ReadonlyArray<unknown> = [
          { ...replay },
          new Proxy(replay, {}),
          structuredCloneOrEmpty(replay),
          JSON.parse(JSON.stringify(replay)) as unknown
        ]
        for (const copiedReplay of replayCopies) {
          const replayCopyOutcome =
            yield* inspectS2SStageUploadAssertionReplayForTest(
              scenario.fixture.permitSeed,
              scenario.fixture.capability,
              copiedReplay
            ).pipe(Effect.either)
          expectPermitReason(replayCopyOutcome, "INVALID_REPLAY_SNAPSHOT")
        }
      }
    })
)

it.effect(
  "recovers exact action-compatible REGISTER, CONFIRM, and ADJUDICATE archives from their stage-owned prepared bytes",
  () =>
    Effect.gen(function* () {
      const inputs = makeS2SThreeStageCarrierInputs({
        sourceCommitA: SOURCE_COMMIT_A,
        registrationCommitB: REGISTRATION_COMMIT_B,
        workflowSha256: WORKFLOW_SHA256,
        preregistrationSha256: PREREGISTRATION_SHA256,
        workflowRunId: WORKFLOW_RUN_ID,
        registerJobDatabaseId: REGISTER_JOB_DATABASE_ID,
        confirmJobDatabaseId: REGISTER_JOB_DATABASE_ID + 1,
        adjudicateJobDatabaseId: REGISTER_JOB_DATABASE_ID + 2,
        workflowCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS
      })
      const stageInputs = {
        REGISTER: inputs.register,
        CONFIRM: inputs.confirm,
        ADJUDICATE: inputs.adjudicate
      } as const
      for (const stage of ["REGISTER", "CONFIRM", "ADJUDICATE"] as const) {
        const scenario = makeFullAssertionScenario(1, stage, stageInputs[stage])
        const completion = yield* runFullScenario(scenario, 0)
        const snapshot =
          yield* inspectS2SStageUploadAssertionCompletionForTest(
            scenario.fixture.permitSeed,
            scenario.fixture.capability,
            completion
          )
        const prepared = right(
          inspectS2SPreparedStageCarrierTestCapability(
            scenario.fixture.capability
          )
        )
        expect(snapshot.stage).toBe(stage)
        expect(snapshot.postcondition.manifest.stage).toBe(stage)
        expect(snapshot.postcondition.manifest.artifact_name).toBe(
          S2S_STAGE_ARTIFACT_SPECS[stage].artifactName
        )
        expect(prepared.members).toHaveLength(
          S2S_STAGE_ARTIFACT_SPECS[stage].expectedMembers.length
        )
        expect(
          scenario.trace.selectors.find(
            (entry) => entry.operation === "DOWNLOAD"
          )?.input
        ).toEqual({
          artifactId: 9_433_344_546,
          maximumArchiveBytes:
            S2S_STAGE_ARTIFACT_SPECS[stage].maximumArchiveBytes
        })
        expect(snapshot.readCurrentStageArchiveBytes()).toEqual(
          scenario.archive
        )
      }
    })
)

it.effect(
  "rejects completed current jobs, failed predecessors, and started later stages before artifact lookup",
  () =>
    Effect.gen(function* () {
      const inputs = makeS2SThreeStageCarrierInputs({
        sourceCommitA: SOURCE_COMMIT_A,
        registrationCommitB: REGISTRATION_COMMIT_B,
        workflowSha256: WORKFLOW_SHA256,
        preregistrationSha256: PREREGISTRATION_SHA256,
        workflowRunId: WORKFLOW_RUN_ID,
        registerJobDatabaseId: REGISTER_JOB_DATABASE_ID,
        confirmJobDatabaseId: REGISTER_JOB_DATABASE_ID + 1,
        adjudicateJobDatabaseId: REGISTER_JOB_DATABASE_ID + 2,
        workflowCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS
      })
      const cases: ReadonlyArray<{
        readonly name: string
        readonly stage: S2SConfirmatoryJobStage
        readonly carrierInput?: unknown
        readonly jobsTransform: NonNullable<
          FullAssertionScenarioOptions["jobsTransform"]
        >
        readonly detail: string
      }> = [
        {
          name: "current job already completed",
          stage: "REGISTER",
          jobsTransform: (jobs) =>
            patchFullJob(jobs, "register", {
              status: "completed",
              conclusion: "success",
              completed_at: utc(WORKFLOW_CREATED_AT_UNIX_SECONDS + 15)
            }),
          detail:
            "authority-bound producer is not the sole current in-progress job"
        },
        {
          name: "predecessor did not succeed",
          stage: "CONFIRM",
          carrierInput: inputs.confirm,
          jobsTransform: (jobs) =>
            patchFullJob(jobs, "register", { conclusion: "failure" }),
          detail: "predecessor completion chain diverged"
        },
        {
          name: "later stage already started",
          stage: "REGISTER",
          jobsTransform: (jobs) =>
            patchFullJob(jobs, "confirm", {
              status: "in_progress",
              conclusion: null,
              completed_at: null
            }),
          detail: "a later stage has already started or completed"
        }
      ]
      for (const testCase of cases) {
        const scenario = makeFullAssertionScenario(
          1,
          testCase.stage,
          testCase.carrierInput,
          { jobsTransform: testCase.jobsTransform }
        )
        const failed = yield* probeS2SStageUploadAssertionShellForTest(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          scenario.observer
        ).pipe(Effect.either)
        expect(Either.isLeft(failed), testCase.name).toBe(true)
        if (Either.isRight(failed)) {
          throw new Error(`expected hostile job rejection: ${testCase.name}`)
        }
        expect(failed.left, testCase.name).toMatchObject({
          _tag: "S2SStageUploadAssertionShellError",
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "LOOKUP_JOBS",
          detail: testCase.detail,
          causeTag: null
        })
        expect(scenario.trace.calls, testCase.name).toEqual(["RUN", "JOBS"])
        expect(scenario.trace.selectors, testCase.name).toEqual([
          {
            operation: "RUN",
            input: { workflowRunId: WORKFLOW_RUN_ID }
          },
          {
            operation: "JOBS",
            input: {
              workflowRunId: WORKFLOW_RUN_ID,
              workflowRunAttempt: 1
            }
          }
        ])
        const retry = yield* probeS2SStageUploadAssertionShellForTest(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          scenario.observer
        ).pipe(Effect.either)
        expectPermitReason(retry, "STAGE_VOID")
        expect(scenario.trace.calls, testCase.name).toEqual(["RUN", "JOBS"])
      }
    })
)

it.effect(
  "classifies three bracketed absences without readback and never replenishes the void permit",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(null)
      const failed = yield* runFullScenario(scenario, 2).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected bounded absence")
      expect(failed.left).toBeInstanceOf(S2SStageUploadAssertionShellError)
      if (!(failed.left instanceof S2SStageUploadAssertionShellError)) {
        throw failed.left
      }
      expect(failed.left.outcome).toBe(
        "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION"
      )
      expect(scenario.trace.calls).toEqual([
        "RUN",
        "JOBS",
        "ARTIFACTS",
        "RUN",
        "ARTIFACTS",
        "RUN",
        "ARTIFACTS",
        "RUN"
      ])
      const callsBeforeRetry = scenario.trace.calls.length
      const retry =
        yield* probeS2SStageUploadAssertionShellForTest(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          scenario.observer
        ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toHaveLength(callsBeforeRetry)
    })
)

it.effect(
  "fails closed across duplicate, head, expiry, temporal, requery, download, member, and final-run drift",
  () =>
    Effect.gen(function* () {
      const cases: ReadonlyArray<{
        readonly name: string
        readonly options: FullAssertionScenarioOptions
        readonly outcome:
          | "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY"
          | "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE"
        readonly phase: S2SStageUploadAssertionLedgerPhase
        readonly calls: number
        readonly causeTag?: string
      }> = [
        {
          name: "duplicate fixed name",
          options: {
            listingTransform: (_ordinal, artifact, listing) =>
              listing.length === 0
                ? listing
                : [artifact, { ...artifact, id: artifact.id + 1 }]
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "LOOKUP_ARTIFACTS_1",
          calls: 4
        },
        {
          name: "wrong artifact head",
          options: {
            artifactTransform: (artifact) => ({
              ...artifact,
              workflow_run: {
                ...artifact.workflow_run,
                head_sha: "f".repeat(40)
              }
            })
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "LOOKUP_ARTIFACTS_1",
          calls: 4
        },
        {
          name: "expired listing",
          options: {
            artifactTransform: (artifact) => ({
              ...artifact,
              expired: true
            })
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "LOOKUP_ARTIFACTS_1",
          calls: 4
        },
        {
          name: "future-created listing",
          options: {
            artifactTransform: (artifact) => ({
              ...artifact,
              created_at: utc(CURRENT_OBSERVED_AT + 100)
            })
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "LOOKUP_ARTIFACTS_1",
          calls: 4
        },
        {
          name: "exact requery drift",
          options: {
            requeryTransform: (artifact) => ({
              ...artifact,
              size_in_bytes: artifact.size_in_bytes + 1
            })
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "READBACK_ARTIFACT",
          calls: 6
        },
        {
          name: "expiry before exact requery",
          options: {
            requeryTransform: (artifact) => ({
              ...artifact,
              expired: true
            })
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "READBACK_ARTIFACT",
          calls: 6
        },
        {
          name: "expiry before download",
          options: {
            artifactTransform: (artifact) => ({
              ...artifact,
              expires_at: utc(CURRENT_OBSERVED_AT + 1_000)
            }),
            downloadedAtUnixSeconds: CURRENT_OBSERVED_AT + 1_001
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7
        },
        {
          name: "download digest drift",
          options: {
            downloadedArchiveSha256: hash("wrong-download-digest")
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SGitHubArtifactDownloadValidationError"
        },
        {
          name: "download receipt artifact id drift",
          options: {
            downloadArtifactId: 9_433_344_547
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SGitHubArtifactDownloadValidationError"
        },
        {
          name: "download receipt endpoint drift",
          options: {
            downloadEndpointPathAndQuery:
              `/repos/${S2S_GITHUB_REPOSITORY}/actions/artifacts/9/zip`
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SGitHubArtifactDownloadValidationError"
        },
        {
          name: "download receipt redirect status drift",
          options: {
            downloadRedirectHttpStatus: 307
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SGitHubArtifactDownloadValidationError"
        },
        {
          name: "download receipt media type drift",
          options: {
            downloadArchiveMediaType: "text/plain"
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SGitHubArtifactDownloadValidationError"
        },
        {
          name: "download receipt byte length drift",
          options: {
            downloadArchiveByteLength: 1
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SGitHubArtifactDownloadValidationError"
        },
        {
          name: "action-compatible member byte drift",
          options: {
            memberTransform: (members) =>
              members.map((member, index) => {
                const bytes = Uint8Array.from(member.bytes)
                if (index === 0) bytes[0] = bytes[0] === 0 ? 1 : 0
                return { name: member.name, bytes }
              })
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7
        },
        {
          name: "action-compatible extra member",
          options: {
            memberTransform: (members) => [
              ...members,
              {
                name: "unexpected.json",
                bytes: ENCODER.encode("{}\n")
              }
            ]
          },
          outcome: "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
          phase: "READBACK_DOWNLOAD_REDIRECT",
          calls: 7,
          causeTag: "S2SArtifactZipValidationError"
        },
        {
          name: "final run head drift",
          options: {
            finalRunTransform: (run) => ({
              ...run,
              head_sha: "f".repeat(40)
            })
          },
          outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
          phase: "READBACK_RUN_END",
          calls: 8
        }
      ]
      for (const attempt of [1, 2, 3] as const) {
        for (const testCase of cases) {
          const scenario = makeFullAssertionScenario(
            attempt,
            "REGISTER",
            undefined,
            testCase.options
          )
          const failed = yield* runFullScenario(
            scenario,
            (attempt - 1) as 0 | 1 | 2
          ).pipe(Effect.either)
          expect(Either.isLeft(failed), testCase.name).toBe(true)
          if (Either.isRight(failed)) {
            throw new Error(`expected hostile rejection: ${testCase.name}`)
          }
          const expectedPhase =
            testCase.phase === "LOOKUP_ARTIFACTS_1"
              ? (`LOOKUP_ARTIFACTS_${attempt}` as const)
              : testCase.phase
          expect(failed.left, testCase.name).toMatchObject({
            _tag: "S2SStageUploadAssertionShellError",
            outcome: testCase.outcome,
            phase: expectedPhase
          })
          if (testCase.causeTag !== undefined) {
            expect(failed.left, testCase.name).toMatchObject({
              causeTag: testCase.causeTag
            })
          }
          expect(scenario.trace.calls, testCase.name).toHaveLength(
            testCase.calls + 2 * (attempt - 1)
          )
          const callsBeforeRetry = scenario.trace.calls.length
          const retry = yield* probeS2SStageUploadAssertionShellForTest(
            scenario.fixture.permitSeed,
            scenario.fixture.capability,
            scenario.observer
          ).pipe(Effect.either)
          expectPermitReason(retry, "STAGE_VOID")
          expect(scenario.trace.calls, testCase.name).toHaveLength(
            callsBeforeRetry
          )
        }
      }
    })
)

it.effect(
  "maps a failed final fresh-run transport observation to unknown and burns the lease without issuing completion",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      let runOrdinal = 0
      const failedFinalRun = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: (workflowRunId) => {
          runOrdinal += 1
          return runOrdinal === 4
            ? Effect.fail(
                new S2SGitHubTransportError({
                  reason: "REQUEST_FAILED",
                  operation: "READBACK_RUN_END",
                  httpStatus: null,
                  responseBodySha256: null,
                  detail: "final fresh observation unavailable"
                })
              )
            : scenario.observer.observeWorkflowRun(workflowRunId)
        }
      })
      const failed = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        failedFinalRun
      ).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected final-run failure")
      expect(failed.left).toMatchObject({
        _tag: "S2SStageUploadAssertionShellError",
        outcome: "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        phase: "READBACK_RUN_END",
        causeTag: "S2SGitHubTransportError"
      })
      expect(scenario.trace.calls).toHaveLength(7)
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toHaveLength(7)
    })
)

it.effect(
  "rejects outcome-bearing observation wrappers instead of accepting caller classification",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const base = scenario.observer
      const hostile = S2SGitHubObserver.of({
        ...base,
        observeWorkflowRun: (runId) =>
          base.observeWorkflowRun(runId).pipe(
            Effect.map((observation) =>
              Object.freeze({
                ...observation,
                outcome:
                  "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
              })
            )
          )
      })
      const failed =
        yield* probeS2SStageUploadAssertionShellForTest(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          hostile
        ).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected wrapper rejection")
      expect(failed.left).toBeInstanceOf(S2SStageUploadAssertionShellError)
      if (!(failed.left instanceof S2SStageUploadAssertionShellError)) {
        throw failed.left
      }
      expect(failed.left.outcome).toBe(
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE"
      )
      expect(scenario.trace.calls).toEqual(["RUN"])
    })
)

it.effect(
  "keeps one Deferred winner alive across a losing separately scoped Layer and prevents replenishment",
  () =>
    Effect.gen(function* () {
      const winnerScenario = makeFullAssertionScenario(1)
      const loserTrace: FullAssertionTrace = { calls: [], selectors: [] }
      const started = yield* Deferred.make<void>()
      const release = yield* Deferred.make<void>()
      const base = winnerScenario.observer
      let firstRun = true
      const winnerObserver = S2SGitHubObserver.of({
        ...base,
        observeWorkflowRun: (runId) => {
          const observed = base.observeWorkflowRun(runId)
          if (!firstRun) return observed
          firstRun = false
          return Deferred.succeed(started, undefined).pipe(
            Effect.zipRight(Deferred.await(release)),
            Effect.zipRight(observed)
          )
        }
      })
      const loserObserver = S2SGitHubObserver.of({
        ...base,
        observeWorkflowRun: () =>
          Effect.sync(() => {
            loserTrace.calls.push("RUN")
            return yieldImpossibleRunObservation()
          })
      })
      const invoke = Effect.gen(function* () {
        const assertion = yield* S2SStageUploadAssertion
        return yield* assertion.assertAndRecover
      })
      const winner = yield* invoke.pipe(
        Effect.provide(
          makeS2SStageUploadAssertionTestLayer(
            winnerScenario.fixture.permitSeed,
            winnerScenario.fixture.capability,
            winnerObserver
          )
        ),
        Effect.fork
      )
      yield* Deferred.await(started)
      const loser = yield* invoke.pipe(
        Effect.provide(
          makeS2SStageUploadAssertionTestLayer(
            winnerScenario.fixture.permitSeed,
            winnerScenario.fixture.capability,
            loserObserver
          )
        ),
        Effect.either
      )
      expectPermitReason(loser, "PERMIT_IN_FLIGHT")
      expect(loserTrace.calls).toEqual([])
      yield* Deferred.succeed(release, undefined)
      yield* Fiber.join(winner)
      expect(winnerScenario.trace.calls).toHaveLength(8)
      const recreated = yield* invoke.pipe(
        Effect.provide(
          makeS2SStageUploadAssertionTestLayer(
            winnerScenario.fixture.permitSeed,
            winnerScenario.fixture.capability,
            winnerScenario.observer
          )
        ),
        Effect.either
      )
      expectPermitReason(recreated, "PERMIT_ALREADY_SPENT")
      expect(winnerScenario.trace.calls).toHaveLength(8)
    })
)

it.effect(
  "rejects a service escaped from its released Layer even while another exact claim keeps the scope open",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const firstScope = yield* Scope.make()
      const secondScope = yield* Scope.make()
      const firstContext = yield* Layer.buildWithScope(
        makeS2SStageUploadAssertionTestLayer(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          scenario.observer
        ),
        firstScope
      )
      const secondContext = yield* Layer.buildWithScope(
        makeS2SStageUploadAssertionTestLayer(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          scenario.observer
        ),
        secondScope
      )
      const escaped = Context.get(firstContext, S2SStageUploadAssertion)
      const active = Context.get(secondContext, S2SStageUploadAssertion)
      yield* Scope.close(firstScope, Exit.succeed(undefined))
      const stale = yield* escaped.assertAndRecover.pipe(Effect.either)
      expectPermitReason(stale, "SCOPE_CLOSED")
      expect(scenario.trace.calls).toEqual([])
      yield* active.assertAndRecover
      expect(scenario.trace.calls).toHaveLength(8)
      yield* Scope.close(secondScope, Exit.succeed(undefined))
    })
)

it.effect(
  "voids instead of issuing a completion when the owning Layer closes during an in-flight healthy candidate",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const started = yield* Deferred.make<void>()
      const release = yield* Deferred.make<void>()
      let firstRun = true
      const ownerObserver = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: (runId) => {
          const observed = scenario.observer.observeWorkflowRun(runId)
          if (!firstRun) return observed
          firstRun = false
          return Deferred.succeed(started, undefined).pipe(
            Effect.zipRight(Deferred.await(release)),
            Effect.zipRight(observed)
          )
        }
      })
      const ownerScope = yield* Scope.make()
      const ownerContext = yield* Layer.buildWithScope(
        makeS2SStageUploadAssertionTestLayer(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          ownerObserver
        ),
        ownerScope
      )
      const owner = Context.get(ownerContext, S2SStageUploadAssertion)
      const fiber = yield* owner.assertAndRecover.pipe(Effect.fork)
      yield* Deferred.await(started)
      yield* Scope.close(ownerScope, Exit.succeed(undefined))
      yield* Deferred.succeed(release, undefined)
      const completion = yield* Fiber.join(fiber).pipe(Effect.either)
      expectPermitReason(completion, "INVALID_COMPLETION_CAPABILITY")
      expect(scenario.trace.calls).toHaveLength(8)

      const retryScope = yield* Scope.make()
      const retryContext = yield* Layer.buildWithScope(
        makeS2SStageUploadAssertionTestLayer(
          scenario.fixture.permitSeed,
          scenario.fixture.capability,
          scenario.observer
        ),
        retryScope
      )
      const retry = yield* Context.get(
        retryContext,
        S2SStageUploadAssertion
      ).assertAndRecover.pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toHaveLength(8)
      yield* Scope.close(retryScope, Exit.succeed(undefined))
    })
)

it.effect(
  "preserves a full-shell observer defect and irreversibly voids the exact lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const defective = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: () => Effect.dieMessage("full-shell defect")
      })
      const exit = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        defective
      ).pipe(Effect.exit)
      expect(Exit.isFailure(exit)).toBe(true)
      if (Exit.isFailure(exit)) {
        expect(Cause.isDieType(exit.cause)).toBe(true)
      }
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

it.effect(
  "preserves a malformed observer method as a TypeError defect and burns the exact lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const malformed = Object.freeze({}) as unknown as
        S2SGitHubObserver["Type"]
      const exit = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        malformed
      ).pipe(Effect.exit)
      expect(Exit.isFailure(exit)).toBe(true)
      if (Exit.isFailure(exit)) {
        expect(
          Chunk.toReadonlyArray(Cause.failures(exit.cause))
        ).toEqual([])
        const defects = Chunk.toReadonlyArray(Cause.defects(exit.cause))
        expect(defects).toHaveLength(1)
        expect(defects[0]).toBeInstanceOf(TypeError)
      }
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

it.effect(
  "maps only the typed member of a sequential observer Cause while preserving its defect and burning the lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const transportFailure = new S2SGitHubTransportError({
        reason: "REQUEST_FAILED",
        operation: "HOSTILE_COMPOSED_CAUSE",
        httpStatus: null,
        responseBodySha256: null,
        detail: "typed transport member"
      })
      const composedObserver = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: () =>
          Effect.failCause(
            Cause.sequential(
              Cause.fail(transportFailure),
              Cause.die("composed-defect-sentinel")
            )
          )
      })
      const exit = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        composedObserver
      ).pipe(Effect.exit)
      expect(Exit.isFailure(exit)).toBe(true)
      if (Exit.isFailure(exit)) {
        const failures = Chunk.toReadonlyArray(Cause.failures(exit.cause))
        const defects = Chunk.toReadonlyArray(Cause.defects(exit.cause))
        expect(failures).toHaveLength(1)
        expect(failures[0]).toMatchObject({
          _tag: "S2SStageUploadAssertionShellError",
          outcome: "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
          phase: "LOOKUP_RUN_START",
          causeTag: "S2SGitHubTransportError"
        })
        expect(defects).toContain("composed-defect-sentinel")
      }
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

it.effect(
  "preserves direct full-shell interruption and does not replenish the burned lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const started = yield* Deferred.make<void>()
      const interruptedObserver = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: () =>
          Deferred.succeed(started, undefined).pipe(
            Effect.zipRight(Effect.never)
          )
      })
      const fiber = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        interruptedObserver
      ).pipe(Effect.fork)
      yield* Deferred.await(started)
      const interrupted = yield* Fiber.interrupt(fiber)
      expect(Exit.isFailure(interrupted)).toBe(true)
      if (Exit.isFailure(interrupted)) {
        expect(Cause.isInterruptedOnly(interrupted.cause)).toBe(true)
      }
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

it.effect(
  "maps the exact metadata phase timeout and burns the full-shell lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const started = yield* Deferred.make<void>()
      const timedObserver = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: () =>
          Deferred.succeed(started, undefined).pipe(
            Effect.zipRight(Effect.never)
          )
      })
      const fiber = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        timedObserver
      ).pipe(Effect.fork)
      yield* Deferred.await(started)
      yield* waitForSettleSleep()
      yield* TestClock.adjust(119_999)
      expect((yield* Fiber.poll(fiber))._tag).toBe("None")
      yield* TestClock.adjust(1)
      const failed = yield* Fiber.join(fiber).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected phase timeout")
      expect(failed.left).toBeInstanceOf(S2SStageUploadAssertionShellError)
      if (!(failed.left instanceof S2SStageUploadAssertionShellError)) {
        throw failed.left
      }
      expect(failed.left).toMatchObject({
        outcome: "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        phase: "LOOKUP_RUN_START",
        causeTag: "S2SStageUploadAssertionMetadataTimeout"
      })
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

it.effect(
  "maps live-style wrong-run identity failure to ambiguity and burns the full-shell lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const wrongRun = S2SGitHubObserver.of({
        ...scenario.observer,
        observeWorkflowRun: () =>
          Effect.fail(
            new S2SGitHubObservationError({
              reason: "IDENTITY_MISMATCH",
              path: "$.id",
              detail: "fixture returned a different workflow run"
            })
          )
      })
      const failed = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        wrongRun
      ).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected identity failure")
      expect(failed.left).toMatchObject({
        _tag: "S2SStageUploadAssertionShellError",
        outcome: "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        phase: "LOOKUP_RUN_START",
        causeTag: "S2SGitHubObservationError"
      })
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

it.effect(
  "maps the exact 420-second download phase boundary and burns the full-shell lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const started = yield* Deferred.make<void>()
      const timedObserver = S2SGitHubObserver.of({
        ...scenario.observer,
        downloadArtifactArchive: () =>
          Deferred.succeed(started, undefined).pipe(
            Effect.zipRight(Effect.never)
          )
      })
      const fiber = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        timedObserver
      ).pipe(Effect.fork)
      yield* Deferred.await(started)
      yield* waitForScheduledSleeps(2)
      yield* TestClock.adjust(419_999)
      expect((yield* Fiber.poll(fiber))._tag).toBe("None")
      yield* TestClock.adjust(1)
      const failed = yield* Fiber.join(fiber).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected download timeout")
      expect(failed.left).toMatchObject({
        _tag: "S2SStageUploadAssertionShellError",
        outcome: "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        phase: "READBACK_DOWNLOAD_REDIRECT",
        causeTag: "S2SStageUploadAssertionDownloadTimeout"
      })
      const callsBeforeRetry = scenario.trace.calls.length
      expect(callsBeforeRetry).toBe(6)
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toHaveLength(callsBeforeRetry)
    })
)

it.effect(
  "fires the exact 1,800,000 ms whole-use boundary before observer acquisition can escape and burns the lease",
  () =>
    Effect.gen(function* () {
      const scenario = makeFullAssertionScenario(1)
      const started = yield* Deferred.make<void>()
      const fiber = yield* probeS2SStageUploadAssertionWholeTimeoutForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        Deferred.succeed(started, undefined)
      ).pipe(Effect.fork)
      yield* Deferred.await(started)
      yield* waitForScheduledSleeps(1)
      yield* TestClock.adjust(1_799_999)
      expect((yield* Fiber.poll(fiber))._tag).toBe("None")
      yield* TestClock.adjust(1)
      const failed = yield* Fiber.join(fiber).pipe(Effect.either)
      expect(Either.isLeft(failed)).toBe(true)
      if (Either.isRight(failed)) throw new Error("expected whole timeout")
      expect(failed.left).toMatchObject({
        _tag: "S2SStageUploadAssertionShellError",
        outcome: "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        phase: "WHOLE_ASSERTION",
        causeTag: "S2SStageUploadAssertionWholeTimeout"
      })
      const retry = yield* probeS2SStageUploadAssertionShellForTest(
        scenario.fixture.permitSeed,
        scenario.fixture.capability,
        scenario.observer
      ).pipe(Effect.either)
      expectPermitReason(retry, "STAGE_VOID")
      expect(scenario.trace.calls).toEqual([])
    })
)

const yieldImpossibleRunObservation = (): never => {
  throw new Error("loser observer must never run")
}
