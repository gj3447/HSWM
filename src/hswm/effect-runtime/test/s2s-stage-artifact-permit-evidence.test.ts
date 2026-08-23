import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import * as PublicApi from "../src/index.js"
import { canonicalS2SControlSha256 } from "../src/s2s-canonical.js"
import {
  S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
  type S2SCurrentRunStageEvidence
} from "../src/s2s-run-authority.js"
import {
  S2S_STAGE_ARTIFACT_PERMIT_EVIDENCE_SCHEMA_VERSION,
  validateS2SStageArtifactPermitEvidence,
  type S2SStageArtifactLedgerEntry,
  type S2SStageArtifactLedgerPhase,
  type S2SStageArtifactPermitEvidence
} from "../src/s2s-stage-artifact-permits.js"
import {
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  type S2SConfirmatoryArtifactReadOperation,
  type S2SConfirmatoryJobStage
} from "../src/s2s-workflow-contract.js"

const RUN_ID = 32_442_437_970
const REGISTER_JOB_ID = 96_655_652_099
const CONFIRM_JOB_ID = 96_655_652_100
const ADJUDICATE_JOB_ID = 96_655_652_101
const SOURCE_COMMIT_A = "a".repeat(40)
const REGISTRATION_COMMIT_B = "b".repeat(40)
const CREATED_AT = "2026-08-21T03:10:32Z"
const CREATED_AT_UNIX_SECONDS = Date.parse(CREATED_AT) / 1_000
const OBSERVED_AT = CREATED_AT_UNIX_SECONDS + 2_000

const right = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const currentJobDatabaseId = (stage: S2SConfirmatoryJobStage): number =>
  stage === "REGISTER"
    ? REGISTER_JOB_ID
    : stage === "CONFIRM"
      ? CONFIRM_JOB_ID
      : ADJUDICATE_JOB_ID

const predecessorJobDatabaseIds = (
  stage: S2SConfirmatoryJobStage
): ReadonlyArray<number> =>
  stage === "REGISTER"
    ? []
    : stage === "CONFIRM"
      ? [REGISTER_JOB_ID]
      : [REGISTER_JOB_ID, CONFIRM_JOB_ID]

const currentRunEvidence = (
  stage: S2SConfirmatoryJobStage
): S2SCurrentRunStageEvidence => {
  const observations = {
    runStart: {
      receiptSha256: "1".repeat(64),
      githubRequestId: "SEED:RUN-START",
      observedAtUnixSeconds: OBSERVED_AT - 40
    },
    jobs: {
      receiptSha256: "2".repeat(64),
      githubRequestId: "SEED:JOBS",
      observedAtUnixSeconds: OBSERVED_AT - 30
    },
    runsForHead: {
      receiptSha256: "3".repeat(64),
      githubRequestId: "SEED:RUNS-FOR-HEAD",
      observedAtUnixSeconds: OBSERVED_AT - 20
    },
    runEnd: {
      receiptSha256: "4".repeat(64),
      githubRequestId: "SEED:RUN-END",
      observedAtUnixSeconds: OBSERVED_AT - 10
    }
  }
  const core: Omit<S2SCurrentRunStageEvidence, "receiptSha256"> = {
    schemaVersion: S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
    authorityScope: "PROCESS_LOCAL_STAGE_ENTRY",
    uniquenessClaim: "ROSTER_OBSERVATION_INSTANT_ONLY",
    historicalUniquenessClaimed: false,
    crossExecutionReplayPreventionClaimed: false,
    durableCommitRequiresFreshTerminalObservation: true,
    sourceCommitA: SOURCE_COMMIT_A,
    registrationCommitB: REGISTRATION_COMMIT_B,
    registrationAuthorityReceiptSha256: "5".repeat(64),
    currentInvocationReceiptSha256: "6".repeat(64),
    workflowContractSha256: "7".repeat(64),
    workflowFileSha256: "8".repeat(64),
    trackedBytesManifestSha256: "9".repeat(64),
    workflowApiPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
    workflowRunId: RUN_ID,
    workflowRunAttempt: 1,
    stage,
    currentJobId: S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobId,
    currentJobDatabaseId: currentJobDatabaseId(stage),
    predecessorJobDatabaseIds: predecessorJobDatabaseIds(stage),
    workflowRunCreatedAt: CREATED_AT,
    workflowRunCreatedAtUnixSeconds: CREATED_AT_UNIX_SECONDS,
    invocationCapturedAtUnixSeconds: OBSERVED_AT - 100,
    observations
  }
  return {
    ...core,
    receiptSha256: right(canonicalS2SControlSha256(core))
  }
}

const seedLedger = (
  expected: S2SCurrentRunStageEvidence
): ReadonlyArray<S2SStageArtifactLedgerEntry> => [
  {
    operation: "CURRENT_RUN_AUTHORITY",
    phase: "CURRENT_RUN_RUN_START",
    ...expected.observations.runStart
  },
  {
    operation: "CURRENT_RUN_AUTHORITY",
    phase: "CURRENT_RUN_JOBS",
    ...expected.observations.jobs
  },
  {
    operation: "CURRENT_RUN_AUTHORITY",
    phase: "CURRENT_RUN_RUNS_FOR_HEAD",
    ...expected.observations.runsForHead
  },
  {
    operation: "CURRENT_RUN_AUTHORITY",
    phase: "CURRENT_RUN_RUN_END",
    ...expected.observations.runEnd
  }
]

const phasesForPoll = (
  poll: 1 | 2 | 3
): ReadonlyArray<S2SStageArtifactLedgerPhase> => {
  const phases: Array<S2SStageArtifactLedgerPhase> = [
    "LOOKUP_RUN_START",
    "LOOKUP_JOBS",
    "LOOKUP_ARTIFACTS_1",
    "LOOKUP_RUN_END_1"
  ]
  if (poll >= 2) phases.push("LOOKUP_ARTIFACTS_2", "LOOKUP_RUN_END_2")
  if (poll === 3) phases.push("LOOKUP_ARTIFACTS_3", "LOOKUP_RUN_END_3")
  phases.push(
    "READBACK_RUN_START",
    "READBACK_ARTIFACT",
    "READBACK_DOWNLOAD_REDIRECT",
    "READBACK_RUN_END"
  )
  return phases
}

const permitCore = (
  evidence: S2SStageArtifactPermitEvidence
): Omit<S2SStageArtifactPermitEvidence, "receiptSha256"> => ({
  schemaVersion: evidence.schemaVersion,
  authorityScope: evidence.authorityScope,
  authorizationClaimed: evidence.authorizationClaimed,
  oneUseClaim: evidence.oneUseClaim,
  crossWorkerReplayPreventionClaimed:
    evidence.crossWorkerReplayPreventionClaimed,
  crossModuleCopyReplayPreventionClaimed:
    evidence.crossModuleCopyReplayPreventionClaimed,
  crossProcessReplayPreventionClaimed:
    evidence.crossProcessReplayPreventionClaimed,
  durableReplayPreventionClaimed: evidence.durableReplayPreventionClaimed,
  identity: evidence.identity,
  operation: evidence.operation,
  ledgerCapacity: evidence.ledgerCapacity,
  ledgerEntries: evidence.ledgerEntries
})

const sealPermitEvidence = (
  core: Omit<S2SStageArtifactPermitEvidence, "receiptSha256">
): S2SStageArtifactPermitEvidence => ({
  ...core,
  receiptSha256: right(canonicalS2SControlSha256(core))
})

const makePermitEvidence = (
  stage: "CONFIRM" | "ADJUDICATE",
  operation: S2SConfirmatoryArtifactReadOperation,
  poll: 1 | 2 | 3 = 3
): {
  readonly expected: S2SCurrentRunStageEvidence
  readonly evidence: S2SStageArtifactPermitEvidence
} => {
  const expected = currentRunEvidence(stage)
  const contracts = S2S_CONFIRMATORY_STAGE_CONTRACTS[
    stage
  ].artifactReadOperations
  const activeIndex = contracts.findIndex(
    (contract) => contract.operation === operation
  )
  if (activeIndex < 0) throw new Error("fixture operation is outside its stage")
  const ledgerEntries: Array<S2SStageArtifactLedgerEntry> = [
    ...seedLedger(expected)
  ]
  let ordinal = ledgerEntries.length
  for (const contract of contracts.slice(0, activeIndex + 1)) {
    for (const phase of phasesForPoll(poll)) {
      ordinal += 1
      ledgerEntries.push({
        operation: contract.operation,
        phase,
        githubRequestId: `REQ:${ordinal}:${contract.operation}:${phase}`,
        receiptSha256: ordinal.toString(16).padStart(64, "0"),
        observedAtUnixSeconds: OBSERVED_AT + ordinal
      })
    }
  }
  const evidence = sealPermitEvidence({
    schemaVersion: S2S_STAGE_ARTIFACT_PERMIT_EVIDENCE_SCHEMA_VERSION,
    authorityScope: "TEST_ONLY_NON_AUTHORIZING",
    authorizationClaimed: false,
    oneUseClaim: "MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE",
    crossWorkerReplayPreventionClaimed: false,
    crossModuleCopyReplayPreventionClaimed: false,
    crossProcessReplayPreventionClaimed: false,
    durableReplayPreventionClaimed: false,
    identity: {
      workflowRunId: expected.workflowRunId,
      workflowRunAttempt: 1,
      registrationCommitB: expected.registrationCommitB,
      workflowApiPath: expected.workflowApiPath,
      workflowRunCreatedAt: expected.workflowRunCreatedAt,
      workflowRunCreatedAtUnixSeconds:
        expected.workflowRunCreatedAtUnixSeconds,
      stage,
      currentJobDatabaseId: expected.currentJobDatabaseId,
      predecessorJobDatabaseIds: [
        ...expected.predecessorJobDatabaseIds
      ]
    },
    operation,
    ledgerCapacity: stage === "CONFIRM" ? 16 : 40,
    ledgerEntries
  })
  return { expected, evidence }
}

const expectRejected = (
  input: unknown,
  expected: S2SCurrentRunStageEvidence
): void => {
  expect(
    Either.isLeft(validateS2SStageArtifactPermitEvidence(input, expected))
  ).toBe(true)
}

it("accepts exact full 16-entry and 40-entry ledgers as defensive snapshots", () => {
  const fixtures = [
    makePermitEvidence("CONFIRM", "CONFIRM_READ_REGISTRATION"),
    makePermitEvidence("ADJUDICATE", "ADJUDICATE_REREAD_CANDIDATE")
  ]
  expect(fixtures.map(({ evidence }) => evidence.ledgerEntries.length)).toEqual([
    16, 40
  ])
  for (const { expected, evidence } of fixtures) {
    const mutableInput = structuredClone(evidence)
    const outcome = validateS2SStageArtifactPermitEvidence(
      mutableInput,
      expected
    )
    const validated = right(outcome)
    expect(Object.isFrozen(validated)).toBe(true)
    expect(Object.isFrozen(validated.identity)).toBe(true)
    expect(Object.isFrozen(validated.identity.predecessorJobDatabaseIds)).toBe(
      true
    )
    expect(Object.isFrozen(validated.ledgerEntries)).toBe(true)
    expect(validated.ledgerEntries.every(Object.isFrozen)).toBe(true)
    expect(validated.identity).not.toBe(mutableInput.identity)
    expect(validated.ledgerEntries).not.toBe(mutableInput.ledgerEntries)
    expect(validated.ledgerEntries[0]).not.toBe(mutableInput.ledgerEntries[0])
    const mutableLedger = mutableInput.ledgerEntries as Array<
      S2SStageArtifactLedgerEntry
    >
    mutableLedger[0] = {
      ...mutableLedger[0]!,
      githubRequestId: "MUTATED"
    }
    expect(validated.ledgerEntries[0]?.githubRequestId).toBe(
      "SEED:RUN-START"
    )
  }
})

it("rejects missing, excess, accessor-backed, symbolic, and proxied roots", () => {
  const { expected, evidence } = makePermitEvidence(
    "CONFIRM",
    "CONFIRM_READ_REGISTRATION"
  )
  const missing = Object.fromEntries(
    Object.entries(evidence).filter(([key]) => key !== "receiptSha256")
  )
  const excess = { ...evidence, unexpected: true }
  let getterCalls = 0
  const accessor: Record<string, unknown> = { ...evidence }
  Object.defineProperty(accessor, "operation", {
    enumerable: true,
    get: () => {
      getterCalls += 1
      return evidence.operation
    }
  })
  const symbolic = { ...evidence, [Symbol("forged")]: true }
  const transparentProxy = new Proxy(evidence, {})
  const hostileProxy = new Proxy(evidence, {
    ownKeys: () => {
      throw new Error("hostile ownKeys")
    }
  })
  for (const hostile of [
    missing,
    excess,
    accessor,
    symbolic,
    transparentProxy,
    hostileProxy
  ]) {
    expectRejected(hostile, expected)
  }
  expect(getterCalls).toBe(0)
})

it("rejects nested accessors, proxies, excess array fields, and entry aliases", () => {
  const { expected, evidence } = makePermitEvidence(
    "CONFIRM",
    "CONFIRM_READ_REGISTRATION"
  )
  let getterCalls = 0
  const accessorIdentity: Record<string, unknown> = { ...evidence.identity }
  Object.defineProperty(accessorIdentity, "workflowRunId", {
    enumerable: true,
    get: () => {
      getterCalls += 1
      return evidence.identity.workflowRunId
    }
  })
  const nestedAccessor = { ...evidence, identity: accessorIdentity }
  const proxiedIdentity = {
    ...evidence,
    identity: new Proxy(evidence.identity, {})
  }
  const proxiedLedger = {
    ...evidence,
    ledgerEntries: new Proxy(evidence.ledgerEntries, {})
  }
  const proxiedEntry = {
    ...evidence,
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 5 ? new Proxy(entry, {}) : entry
    )
  }
  const excessLedger = [...evidence.ledgerEntries]
  Object.defineProperty(excessLedger, "hidden", {
    enumerable: false,
    value: true
  })
  const aliasedLedger = [...evidence.ledgerEntries]
  aliasedLedger[5] = aliasedLedger[4]!
  const aliased = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: aliasedLedger
  })
  for (const hostile of [
    nestedAccessor,
    proxiedIdentity,
    proxiedLedger,
    proxiedEntry,
    { ...evidence, ledgerEntries: excessLedger },
    aliased
  ]) {
    expectRejected(hostile, expected)
  }
  expect(getterCalls).toBe(0)
})

it("rejects receipt drift and forged-but-rehashed current-run seed drift", () => {
  const { expected, evidence } = makePermitEvidence(
    "CONFIRM",
    "CONFIRM_READ_REGISTRATION"
  )
  const unhashedDrift = {
    ...evidence,
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 5 ? { ...entry, receiptSha256: "f".repeat(64) } : entry
    )
  }
  expectRejected(unhashedDrift, expected)

  const seedDrift = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 0 ? { ...entry, receiptSha256: "f".repeat(64) } : entry
    )
  })
  expectRejected(seedDrift, expected)
})

it("rejects phase reorder, duplicate IDs or receipts, and time rollback", () => {
  const { expected, evidence } = makePermitEvidence(
    "CONFIRM",
    "CONFIRM_READ_REGISTRATION"
  )
  const reordered = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 5
        ? { ...entry, phase: "LOOKUP_ARTIFACTS_1" }
        : index === 6
          ? { ...entry, phase: "LOOKUP_JOBS" }
          : entry
    )
  })
  const duplicateRequest = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 5
        ? {
            ...entry,
            githubRequestId: evidence.ledgerEntries[4]!.githubRequestId
          }
        : entry
    )
  })
  const duplicateReceipt = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 5
        ? {
            ...entry,
            receiptSha256: evidence.ledgerEntries[4]!.receiptSha256
          }
        : entry
    )
  })
  const timeRollback = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: evidence.ledgerEntries.map((entry, index) =>
      index === 5
        ? {
            ...entry,
            observedAtUnixSeconds:
              evidence.ledgerEntries[4]!.observedAtUnixSeconds - 1
          }
        : entry
    )
  })
  for (const hostile of [
    reordered,
    duplicateRequest,
    duplicateReceipt,
    timeRollback
  ]) {
    expectRejected(hostile, expected)
  }
})

it("rejects wrong identity stage, operation contract, capacity, and cap plus one", () => {
  const { expected, evidence } = makePermitEvidence(
    "CONFIRM",
    "CONFIRM_READ_REGISTRATION"
  )
  const wrongStage = sealPermitEvidence({
    ...permitCore(evidence),
    identity: {
      ...evidence.identity,
      stage: "ADJUDICATE",
      currentJobDatabaseId: ADJUDICATE_JOB_ID,
      predecessorJobDatabaseIds: [REGISTER_JOB_ID, CONFIRM_JOB_ID]
    }
  })
  const wrongOperation = sealPermitEvidence({
    ...permitCore(evidence),
    operation: "ADJUDICATE_READ_REGISTRATION"
  })
  const wrongCapacity = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerCapacity: 40
  })
  const final = evidence.ledgerEntries.at(-1)!
  const overCapacity = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: [
      ...evidence.ledgerEntries,
      {
        ...final,
        githubRequestId: "REQ:CAP-PLUS-ONE",
        receiptSha256: "e".repeat(64),
        observedAtUnixSeconds: final.observedAtUnixSeconds + 1
      }
    ]
  })
  for (const hostile of [
    wrongStage,
    wrongOperation,
    wrongCapacity,
    overCapacity
  ]) {
    expectRejected(hostile, expected)
  }
})

it("accepts an exact adjudication prefix and rejects a skipped prior operation", () => {
  const { expected, evidence } = makePermitEvidence(
    "ADJUDICATE",
    "ADJUDICATE_READ_CANDIDATE_FIRST",
    1
  )
  expect(
    Either.isRight(validateS2SStageArtifactPermitEvidence(evidence, expected))
  ).toBe(true)
  const skipped = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: [
      ...evidence.ledgerEntries.slice(0, 4),
      ...evidence.ledgerEntries.filter(
        (entry) => entry.operation === "ADJUDICATE_READ_CANDIDATE_FIRST"
      )
    ]
  })
  expectRejected(skipped, expected)
})

it("rejects a ledger whose active operation is not sealed by READBACK_RUN_END", () => {
  const { expected, evidence } = makePermitEvidence(
    "CONFIRM",
    "CONFIRM_READ_REGISTRATION"
  )
  const incomplete = sealPermitEvidence({
    ...permitCore(evidence),
    ledgerEntries: evidence.ledgerEntries.slice(0, -1)
  })
  expectRejected(incomplete, expected)
})

it("keeps the validator out of the package root", () => {
  expect("validateS2SStageArtifactPermitEvidence" in PublicApi).toBe(false)
})
