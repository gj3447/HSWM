import { expect, it } from "@effect/vitest"
import {
  Cause,
  Context,
  Deferred,
  Effect,
  Either,
  Exit,
  Fiber,
  Layer,
  Schema
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
  makeS2SPreparedStageCarrierTestCapability,
  type S2SPreparedStageCarrierCapability,
  type S2SPreparedStageCarrierTestSeed
} from "../src/s2s-prepared-stage-carrier.js"
import {
  S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
  type S2SCurrentRunStageEvidence
} from "../src/s2s-run-authority.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "../src/s2s-stage-artifact-spec.js"
import {
  S2SStageUploadAssertionPermitError,
  appendS2SStageUploadAssertionLedgerEntryForTest,
  claimS2SStageUploadAssertionPermitScope,
  makeS2SStageUploadAssertionPermitTestScope,
  probeS2SStageUploadAssertionMechanicsForTest,
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
  s2sConfirmatoryWorkflowContractSha256
} from "../src/s2s-workflow-contract.js"

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

const makeCurrentRunEvidence = (): S2SCurrentRunStageEvidence => {
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
    stage: "REGISTER",
    currentJobId: S2S_CONFIRMATORY_STAGE_CONTRACTS.REGISTER.jobId,
    currentJobDatabaseId: REGISTER_JOB_DATABASE_ID,
    predecessorJobDatabaseIds: Object.freeze([]),
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

const makeFixture = (): Fixture => {
  const currentRunEvidence = makeCurrentRunEvidence()
  const preparedSeed: S2SPreparedStageCarrierTestSeed = {
    classification: "TEST_ONLY_NON_AUTHORIZING",
    stage: "REGISTER",
    sourceCommitA: currentRunEvidence.sourceCommitA,
    currentRunEvidenceReceiptSha256: currentRunEvidence.receiptSha256,
    workflowRunId: currentRunEvidence.workflowRunId,
    registrationCommitB: currentRunEvidence.registrationCommitB,
    workflowApiPath: currentRunEvidence.workflowApiPath,
    workflowRunCreatedAt: currentRunEvidence.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds:
      currentRunEvidence.workflowRunCreatedAtUnixSeconds,
    currentJobDatabaseId: currentRunEvidence.currentJobDatabaseId,
    predecessorJobDatabaseIds: []
  }
  const capability = right(
    makeS2SPreparedStageCarrierTestCapability(preparedSeed, {
      events: [registrationEvent()]
    })
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
    "appendS2SStageUploadAssertionLedgerEntryForTest",
    "makeS2SStageUploadAssertionPermitTestScope",
    "probeS2SStageUploadAssertionMechanicsForTest",
    "snapshotS2SStageUploadAssertionPermitEvidenceForTest",
    "useS2SStageUploadAssertionPermitForTest"
  ]) {
    expect(name in PublicApi).toBe(false)
  }
})
