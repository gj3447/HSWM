import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit, Fiber, Layer, TestClock } from "effect"
import { runInNewContext } from "node:vm"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
  S2S_GITHUB_JSON_MAX_BYTES,
  S2S_GITHUB_OBSERVATION_SCHEMA_VERSION,
  S2S_GITHUB_REPOSITORY,
  S2SGitHubHttpTransport,
  S2SGitHubObserver,
  S2SGitHubObserverLive,
  makeS2SGitHubHttpTransportLiveLayer,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  observeS2SGitHubWorkflowRunsForHead,
  validateS2SGitHubArtifactObservation,
  validateS2SGitHubArtifactDownload,
  validateS2SGitHubRunArtifactsObservation,
  validateS2SGitHubWorkflowAttemptJobsObservation,
  validateS2SGitHubWorkflowRunObservation,
  validateS2SGitHubWorkflowRunsForHeadObservation
} from "../src/s2s-live-github.js"

const RUN_ID = 32_442_437_970
const JOB_ID = 96_655_652_099
const ARTIFACT_ID = 9_433_344_546
const HEAD_SHA = "75686549b1f6c65aea87ebd0f912a6e62909445a"
const DIGEST = "b5a29cab118737f48083613f45a34212ae73f15a1321a597947d838c077f63c5"
const OBSERVED_AT = 1_787_280_000
const encoder = new TextEncoder()
const RESPONSE_ETAG = `W/"${"e".repeat(64)}"`

const responseProvenance = (
  githubRequestId = "A1B2:C3D4:E5F6:7890"
) => Object.freeze({
  githubRequestId,
  githubApiVersionSelected: S2S_GITHUB_API_VERSION,
  responseEtag: RESPONSE_ETAG
})

const jsonBytes = (value: unknown): Uint8Array =>
  encoder.encode(`${JSON.stringify(value)}\n`)

const runFixture = (): Record<string, unknown> => ({
  id: RUN_ID,
  run_attempt: 1,
  name: "SWM-0W-S2S confirmatory",
  path: ".github/workflows/swm0w-s2s-confirmatory.yml",
  event: "push",
  head_branch: "main",
  head_sha: HEAD_SHA,
  repository: { full_name: "gj3447/HSWM" },
  head_repository: { full_name: "gj3447/HSWM" },
  status: "in_progress",
  conclusion: null,
  created_at: "2026-08-21T03:10:32Z",
  ignored_additive_field: "allowed"
})

const jobFixture = (): Record<string, unknown> => ({
  id: JOB_ID,
  run_id: RUN_ID,
  run_attempt: 1,
  name: "register",
  head_sha: HEAD_SHA,
  status: "completed",
  conclusion: "success",
  started_at: "2026-08-21T03:10:34Z",
  completed_at: "2026-08-21T03:33:15Z",
  labels: ["ubuntu-24.04", "GitHub-hosted"]
})

const artifactFixture = (): Record<string, unknown> => ({
  id: ARTIFACT_ID,
  name: "s2s-registration",
  size_in_bytes: 1_366_046,
  digest: `sha256:${DIGEST}`,
  expired: false,
  created_at: "2026-08-21T03:33:12Z",
  expires_at: "2026-11-19T03:10:32Z",
  workflow_run: { id: RUN_ID, head_sha: HEAD_SHA }
})

it("binds the exact run API body and normalized run projection", () => {
  const raw = jsonBytes(runFixture())
  const outcome = observeS2SGitHubWorkflowRun(
    raw,
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  raw.fill(0)
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isRight(outcome)) {
    expect(outcome.right.receipt.schemaVersion).toBe(
      S2S_GITHUB_OBSERVATION_SCHEMA_VERSION
    )
    expect(outcome.right.receipt.projection).toMatchObject({
      id: RUN_ID,
      runAttempt: 1,
      repository: "gj3447/HSWM",
      headRepository: "gj3447/HSWM",
      createdAtUnixSeconds: 1_787_281_832
    })
    expect(outcome.right.receipt.rawBodySha256).toMatch(/^[0-9a-f]{64}$/)
    expect(outcome.right.receipt.projectionSha256).toMatch(/^[0-9a-f]{64}$/)
    expect(outcome.right.receipt.receiptSha256).toMatch(/^[0-9a-f]{64}$/)
    const firstRead = outcome.right.readRawBody()
    expect(firstRead[0]).toBe(0x7b)
    firstRead.fill(0)
    expect(outcome.right.readRawBody()[0]).toBe(0x7b)
  }
})

it("pins the exact one-MiB GitHub JSON acceptance boundary", () => {
  expect(S2S_GITHUB_JSON_MAX_BYTES).toBe(1_048_576)
  const fixture = jsonBytes(runFixture())
  const exact = new Uint8Array(S2S_GITHUB_JSON_MAX_BYTES)
  exact.fill(0x20)
  exact.set(fixture)
  const accepted = observeS2SGitHubWorkflowRun(
    exact,
    RUN_ID,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:EXACT")
  )
  expect(Either.isRight(accepted)).toBe(true)
  if (Either.isRight(accepted)) {
    expect(accepted.right.receipt.rawBodyByteLength).toBe(
      S2S_GITHUB_JSON_MAX_BYTES
    )
  }
  const over = new Uint8Array(S2S_GITHUB_JSON_MAX_BYTES + 1)
  over.set(exact)
  over[S2S_GITHUB_JSON_MAX_BYTES] = 0x20
  const rejected = observeS2SGitHubWorkflowRun(
    over,
    RUN_ID,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:OVER")
  )
  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left).toMatchObject({
      reason: "INVALID_ARGUMENT",
      path: "$rawBody"
    })
  }
})

it("observes zero, one, or multiple exact-head runs without deciding uniqueness", () => {
  const atMain = {
    ...runFixture(),
    path: ".github/workflows/swm0w-s2s-confirmatory.yml@main"
  }
  const second = {
    ...runFixture(),
    id: RUN_ID + 1,
    run_attempt: 2,
    name: "untrusted workflow name",
    path: ".github/workflows/other.yml@dev",
    event: "workflow_dispatch",
    head_branch: "dev"
  }
  const outcomes = [
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 0, workflow_runs: [] }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance("A1B2:C3D4:E5F6:ZERO")
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 1, workflow_runs: [atMain] }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance("A1B2:C3D4:E5F6:ONE")
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 2, workflow_runs: [second, runFixture()] }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance("A1B2:C3D4:E5F6:TWO")
    )
  ]
  expect(outcomes.every(Either.isRight)).toBe(true)
  const zeroOutcome = outcomes[0]
  const twoOutcome = outcomes[2]
  if (zeroOutcome !== undefined && Either.isRight(zeroOutcome)) {
    expect(zeroOutcome.right.receipt.projection.workflowRuns).toEqual([])
  }
  const oneOutcome = outcomes[1]
  if (oneOutcome !== undefined && Either.isRight(oneOutcome)) {
    expect(oneOutcome.right.receipt.projection.workflowRuns[0]?.path).toBe(
      ".github/workflows/swm0w-s2s-confirmatory.yml@main"
    )
  }
  if (twoOutcome !== undefined && Either.isRight(twoOutcome)) {
    const observation = twoOutcome.right
    expect(observation.receipt.kind).toBe("WORKFLOW_RUNS_FOR_HEAD")
    expect(observation.receipt).toMatchObject({
      githubRequestId: "A1B2:C3D4:E5F6:TWO",
      githubApiVersionSelected: S2S_GITHUB_API_VERSION,
      responseEtag: RESPONSE_ETAG
    })
    expect(observation.receipt.endpointPathAndQuery).toBe(
      `/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&head_sha=${HEAD_SHA}&per_page=100`
    )
    expect(
      observation.receipt.projection.workflowRuns.map((run) => run.id)
    ).toEqual([RUN_ID, RUN_ID + 1])
    expect(observation.receipt.projection.workflowRuns[1]).toMatchObject({
      runAttempt: 2,
      name: "untrusted workflow name",
      path: ".github/workflows/other.yml@dev",
      event: "workflow_dispatch",
      headBranch: "dev"
    })
    expect(Object.isFrozen(observation.receipt.projection)).toBe(true)
    expect(Object.isFrozen(observation.receipt.projection.workflowRuns)).toBe(
      true
    )
    expect(
      observation.receipt.projection.workflowRuns.every(Object.isFrozen)
    ).toBe(true)
  }
})

it("rejects incomplete, duplicate, oversized, malformed, and identity-drifted run lists", () => {
  const one = runFixture()
  const oneHundredOne = Array.from({ length: 101 }, (_value, index) => ({
    ...runFixture(),
    id: RUN_ID + index
  }))
  const malformedSha = { ...runFixture(), head_sha: "not-a-sha" }
  const outcomes = [
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 2, workflow_runs: [one] }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 2, workflow_runs: [one, one] }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 101, workflow_runs: oneHundredOne }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 1, workflow_runs: [malformedSha] }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({
        total_count: 1,
        workflow_runs: [{ ...runFixture(), head_sha: "a".repeat(40) }]
      }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({
        total_count: 1,
        workflow_runs: [
          { ...runFixture(), repository: { full_name: "other/repo" } }
        ]
      }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({
        total_count: 1,
        workflow_runs: [
          { ...runFixture(), head_repository: { full_name: "other/repo" } }
        ]
      }),
      HEAD_SHA,
      OBSERVED_AT,
      responseProvenance()
    ),
    observeS2SGitHubWorkflowRunsForHead(
      jsonBytes({ total_count: 0, workflow_runs: [] }),
      HEAD_SHA.toUpperCase(),
      OBSERVED_AT,
      responseProvenance()
    )
  ]
  expect(outcomes.every(Either.isLeft)).toBe(true)
  const malformedOutcome = outcomes[3]
  expect(malformedOutcome !== undefined && Either.isLeft(malformedOutcome)).toBe(
    true
  )
  if (malformedOutcome !== undefined && Either.isLeft(malformedOutcome)) {
    expect(malformedOutcome.left.path).toBe("$.workflow_runs[0].head_sha")
  }
})

it.effect("lazily reconstructs trusted run, jobs, and run-list observations", () => {
  const runOutcome = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:RUN")
  )
  const jobsOutcome = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 1, jobs: [jobFixture()] }),
    RUN_ID,
    1,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:JOBS")
  )
  const runsOutcome = observeS2SGitHubWorkflowRunsForHead(
    jsonBytes({ total_count: 1, workflow_runs: [runFixture()] }),
    HEAD_SHA,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:LIST")
  )
  if (
    Either.isLeft(runOutcome) ||
    Either.isLeft(jobsOutcome) ||
    Either.isLeft(runsOutcome)
  ) {
    return Effect.dieMessage("valid observation fixture was rejected")
  }
  let runReads = 0
  let jobsReads = 0
  let runsReads = 0
  let runReaderThis: unknown = "not-called"
  const wrappedRun = Object.freeze({
    receipt: runOutcome.right.receipt,
    readRawBody: function (this: unknown) {
      runReaderThis = this
      runReads += 1
      return runOutcome.right.readRawBody()
    }
  })
  const wrappedJobs = Object.freeze({
    receipt: jobsOutcome.right.receipt,
    readRawBody: () => {
      jobsReads += 1
      return jobsOutcome.right.readRawBody()
    }
  })
  const wrappedRuns = Object.freeze({
    receipt: runsOutcome.right.receipt,
    readRawBody: () => {
      runsReads += 1
      return runsOutcome.right.readRawBody()
    }
  })
  const validation = validateS2SGitHubWorkflowRunObservation(
    wrappedRun,
    RUN_ID
  )
  expect([runReads, jobsReads, runsReads]).toEqual([0, 0, 0])
  return Effect.gen(function* () {
    const run = yield* validation
    const jobs = yield* validateS2SGitHubWorkflowAttemptJobsObservation(
      wrappedJobs,
      RUN_ID
    )
    const runs = yield* validateS2SGitHubWorkflowRunsForHeadObservation(
      wrappedRuns,
      HEAD_SHA
    )
    expect([runReads, jobsReads, runsReads]).toEqual([1, 1, 1])
    expect(runReaderThis).toBeUndefined()
    expect(run).not.toBe(wrappedRun)
    expect(run.receipt).not.toBe(wrappedRun.receipt)
    expect(run.receipt.projection).not.toBe(wrappedRun.receipt.projection)
    expect(run.receipt).toEqual(wrappedRun.receipt)
    expect(jobs.receipt.projection.jobs).toHaveLength(1)
    expect(runs.receipt.projection.workflowRuns).toHaveLength(1)
    expect(jobs).not.toBe(wrappedJobs)
    expect(runs).not.toBe(wrappedRuns)
    expect(jobs.receipt.projection).not.toBe(
      wrappedJobs.receipt.projection
    )
    expect(jobs.receipt.projection.jobs).not.toBe(
      wrappedJobs.receipt.projection.jobs
    )
    expect(runs.receipt.projection).not.toBe(
      wrappedRuns.receipt.projection
    )
    expect(runs.receipt.projection.workflowRuns).not.toBe(
      wrappedRuns.receipt.projection.workflowRuns
    )
    expect(Object.isFrozen(run)).toBe(true)
    expect(Object.isFrozen(run.receipt)).toBe(true)
    const first = run.readRawBody()
    first.fill(0)
    expect(run.readRawBody()[0]).toBe(0x7b)
  })
})

it.effect("fails closed on hostile observation wrapper and receipt descriptors", () => {
  const observed = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  if (Either.isLeft(observed)) {
    return Effect.dieMessage("valid observation fixture was rejected")
  }
  let rootAccessorRead = false
  const rootAccessor = {
    readRawBody: observed.right.readRawBody
  }
  Object.defineProperty(rootAccessor, "receipt", {
    enumerable: true,
    get: () => {
      rootAccessorRead = true
      return observed.right.receipt
    }
  })
  const hiddenRoot = { ...observed.right }
  Object.defineProperty(hiddenRoot, "hidden", {
    enumerable: false,
    value: true
  })
  const symbolRoot = { ...observed.right }
  Object.defineProperty(symbolRoot, Symbol("hidden"), {
    enumerable: true,
    value: true
  })
  const hostileRoot = new Proxy({}, {
    ownKeys: () => {
      throw new Error("hostile ownKeys trap")
    }
  })
  const customRoot = { ...observed.right }
  Object.setPrototypeOf(customRoot, { inherited: true })
  const rootInputs = [
    null,
    {},
    { ...observed.right, extra: true },
    hiddenRoot,
    symbolRoot,
    rootAccessor,
    hostileRoot,
    customRoot
  ]

  let receiptAccessorRead = false
  const receiptAccessor = { ...observed.right.receipt }
  Object.defineProperty(receiptAccessor, "kind", {
    enumerable: true,
    get: () => {
      receiptAccessorRead = true
      return "WORKFLOW_RUN"
    }
  })
  const hiddenReceipt = { ...observed.right.receipt }
  Object.defineProperty(hiddenReceipt, "hidden", {
    enumerable: false,
    value: true
  })
  const symbolReceipt = { ...observed.right.receipt }
  Object.defineProperty(symbolReceipt, Symbol("hidden"), {
    enumerable: true,
    value: true
  })
  const customReceipt = { ...observed.right.receipt }
  Object.setPrototypeOf(customReceipt, { inherited: true })
  const receiptInputs: Array<{
    readonly receipt: unknown
    readonly readRawBody: () => Uint8Array
  }> = [
    { ...observed.right.receipt, extra: true },
    hiddenReceipt,
    symbolReceipt,
    receiptAccessor,
    customReceipt,
    new Proxy({}, {
      ownKeys: () => {
        throw new Error("hostile receipt trap")
      }
    })
  ].map((receipt) => ({
    receipt,
    readRawBody: observed.right.readRawBody
  }))
  const { kind: removedKind, ...missingReceipt } = observed.right.receipt
  void removedKind
  let rejectedReceiptReads = 0
  receiptInputs.push({
    receipt: missingReceipt,
    readRawBody: () => {
      rejectedReceiptReads += 1
      return observed.right.readRawBody()
    }
  })

  return Effect.gen(function* () {
    for (const input of rootInputs) {
      const outcome = yield* validateS2SGitHubWorkflowRunObservation(
        input,
        RUN_ID
      ).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("WRAPPER_REJECTED")
      }
    }
    for (const input of receiptInputs) {
      const outcome = yield* validateS2SGitHubWorkflowRunObservation(
        input,
        RUN_ID
      ).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("RECEIPT_REJECTED")
      }
    }
    expect(rootAccessorRead).toBe(false)
    expect(receiptAccessorRead).toBe(false)
    expect(rejectedReceiptReads).toBe(0)
  })
})

it.effect("rejects hostile raw readers and byte drift without invoking byte accessors", () => {
  const observed = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  if (Either.isLeft(observed)) {
    return Effect.dieMessage("valid observation fixture was rejected")
  }
  const raw = observed.right.readRawBody()
  class ByteSubclass extends Uint8Array {}
  const accessorBytes = new Uint8Array(raw)
  const byteLengthAccessorBytes = new Uint8Array(raw)
  let byteLengthAccessorRead = false
  Object.defineProperty(byteLengthAccessorBytes, "byteLength", {
    configurable: true,
    get: () => {
      byteLengthAccessorRead = true
      throw new Error("must not execute")
    }
  })
  const symbolBytes = new Uint8Array(raw)
  Object.defineProperty(symbolBytes, Symbol("extra"), {
    enumerable: true,
    value: true
  })
  const detachedBytes = new Uint8Array(raw)
  structuredClone(detachedBytes.buffer, { transfer: [detachedBytes.buffer] })
  let byteAccessorRead = false
  Object.defineProperty(accessorBytes, "buffer", {
    configurable: true,
    get: () => {
      byteAccessorRead = true
      throw new Error("must not execute")
    }
  })
  const rejectedReaders: Array<() => unknown> = [
    () => {
      throw new Error("reader failed")
    },
    () => Buffer.from(raw),
    () => new ByteSubclass(raw),
    () => new Proxy(raw, {}),
    () => accessorBytes,
    () => byteLengthAccessorBytes,
    () => symbolBytes,
    () => detachedBytes,
    () => new Uint8Array(S2S_GITHUB_JSON_MAX_BYTES + 1)
  ]
  if (typeof SharedArrayBuffer !== "undefined") {
    const crossRealmShared: unknown = runInNewContext(
      `new Uint8Array(new SharedArrayBuffer(${raw.byteLength}))`
    )
    if (crossRealmShared === null || typeof crossRealmShared !== "object") {
      return Effect.dieMessage("cross-realm shared byte fixture is invalid")
    }
    Object.setPrototypeOf(crossRealmShared, Uint8Array.prototype)
    rejectedReaders.push(
      () => new Uint8Array(new SharedArrayBuffer(raw.byteLength)),
      () => crossRealmShared
    )
  }
  const drifted = new Uint8Array(raw)
  drifted[0] = 0x5b
  const lengthDrifted = raw.slice(1)
  let driftReads = 0

  return Effect.gen(function* () {
    for (const readRawBody of rejectedReaders) {
      const outcome = yield* validateS2SGitHubWorkflowRunObservation(
        { receipt: observed.right.receipt, readRawBody },
        RUN_ID
      ).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("RAW_BODY_REJECTED")
      }
    }
    const driftOutcome = yield* validateS2SGitHubWorkflowRunObservation(
      {
        receipt: observed.right.receipt,
        readRawBody: () => {
          driftReads += 1
          return drifted
        }
      },
      RUN_ID
    ).pipe(Effect.either)
    expect(Either.isLeft(driftOutcome)).toBe(true)
    if (Either.isLeft(driftOutcome)) {
      expect(driftOutcome.left.reason).toBe("RAW_BODY_DRIFT")
    }
    const lengthDriftOutcome = yield* validateS2SGitHubWorkflowRunObservation(
      {
        receipt: observed.right.receipt,
        readRawBody: () => lengthDrifted
      },
      RUN_ID
    ).pipe(Effect.either)
    expect(
      Either.isLeft(lengthDriftOutcome) && lengthDriftOutcome.left.reason
    ).toBe("RAW_BODY_DRIFT")
    expect(driftReads).toBe(1)
    expect(byteAccessorRead).toBe(false)
    expect(byteLengthAccessorRead).toBe(false)
  })
})

it.effect("rejects hostile nested projection and array descriptors", () => {
  const observed = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 1, jobs: [jobFixture()] }),
    RUN_ID,
    1,
    OBSERVED_AT,
    responseProvenance()
  )
  if (Either.isLeft(observed)) {
    return Effect.dieMessage("valid observation fixture was rejected")
  }
  const originalJob = observed.right.receipt.projection.jobs[0]
  if (originalJob === undefined) {
    return Effect.dieMessage("job fixture is absent")
  }
  let labelAccessorRead = false
  const accessorLabels = [...originalJob.labels]
  Object.defineProperty(accessorLabels, "0", {
    enumerable: true,
    get: () => {
      labelAccessorRead = true
      return originalJob.labels[0]
    }
  })
  const holeLabels = [...originalJob.labels]
  delete holeLabels[0]
  const extraLabels = [...originalJob.labels]
  Object.defineProperty(extraLabels, "extra", {
    enumerable: true,
    value: true
  })
  const symbolLabels = [...originalJob.labels]
  Object.defineProperty(symbolLabels, Symbol("extra"), {
    enumerable: true,
    value: true
  })
  const customPrototypeLabels = [...originalJob.labels]
  Object.setPrototypeOf(customPrototypeLabels, null)
  const labelVariants = [
    accessorLabels,
    holeLabels,
    extraLabels,
    symbolLabels,
    customPrototypeLabels
  ]
  const inputs = labelVariants.map((labels) => ({
    receipt: {
      ...observed.right.receipt,
      projection: {
        ...observed.right.receipt.projection,
        jobs: [{ ...originalJob, labels }]
      }
    },
    readRawBody: observed.right.readRawBody
  }))
  const jobWithExtra = {
    ...originalJob,
    labels: [...originalJob.labels],
    extra: true
  }
  let jobAccessorRead = false
  const jobWithAccessor = {
    ...originalJob,
    labels: [...originalJob.labels]
  }
  Object.defineProperty(jobWithAccessor, "name", {
    enumerable: true,
    get: () => {
      jobAccessorRead = true
      return originalJob.name
    }
  })
  const jobWithSymbol = {
    ...originalJob,
    labels: [...originalJob.labels]
  }
  Object.defineProperty(jobWithSymbol, Symbol("extra"), {
    enumerable: true,
    value: true
  })
  const jobWithCustomPrototype = {
    ...originalJob,
    labels: [...originalJob.labels]
  }
  Object.setPrototypeOf(jobWithCustomPrototype, { inherited: true })
  for (const job of [
    jobWithExtra,
    jobWithAccessor,
    jobWithSymbol,
    jobWithCustomPrototype
  ]) {
    inputs.push({
      receipt: {
        ...observed.right.receipt,
        projection: {
          ...observed.right.receipt.projection,
          jobs: [job]
        }
      },
      readRawBody: observed.right.readRawBody
    })
  }

  return Effect.gen(function* () {
    for (const input of inputs) {
      const outcome = yield* validateS2SGitHubWorkflowAttemptJobsObservation(
        input,
        RUN_ID
      ).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("RECEIPT_MISMATCH")
      }
    }
    expect(labelAccessorRead).toBe(false)
    expect(jobAccessorRead).toBe(false)
  })
})

it.effect("rejects hostile nested run-list projection and roster descriptors", () => {
  const observed = observeS2SGitHubWorkflowRunsForHead(
    jsonBytes({ total_count: 1, workflow_runs: [runFixture()] }),
    HEAD_SHA,
    OBSERVED_AT,
    responseProvenance()
  )
  if (Either.isLeft(observed)) {
    return Effect.dieMessage("valid run-list fixture was rejected")
  }
  const projection = observed.right.receipt.projection
  let projectionAccessorRead = false
  const accessorProjection = { ...projection }
  Object.defineProperty(accessorProjection, "workflowRuns", {
    enumerable: true,
    get: () => {
      projectionAccessorRead = true
      return projection.workflowRuns
    }
  })
  const hiddenProjection = { ...projection }
  Object.defineProperty(hiddenProjection, "hidden", {
    enumerable: false,
    value: true
  })
  const symbolProjection = { ...projection }
  Object.defineProperty(symbolProjection, Symbol("hidden"), {
    enumerable: true,
    value: true
  })
  const customProjection = { ...projection }
  Object.setPrototypeOf(customProjection, { inherited: true })
  const throwingProjection = new Proxy({ ...projection }, {
    ownKeys: () => {
      throw new Error("nested projection trap")
    }
  })
  const rosterHole = [...projection.workflowRuns]
  delete rosterHole[0]
  const rosterExtra = [...projection.workflowRuns]
  Object.defineProperty(rosterExtra, "extra", {
    enumerable: true,
    value: true
  })
  const rosterSymbol = [...projection.workflowRuns]
  Object.defineProperty(rosterSymbol, Symbol("extra"), {
    enumerable: true,
    value: true
  })
  const rosterCustomPrototype = [...projection.workflowRuns]
  Object.setPrototypeOf(rosterCustomPrototype, null)
  const projectionVariants: Array<unknown> = [
    { ...projection, extra: true },
    hiddenProjection,
    symbolProjection,
    accessorProjection,
    customProjection,
    throwingProjection,
    { ...projection, workflowRuns: rosterHole },
    { ...projection, workflowRuns: rosterExtra },
    { ...projection, workflowRuns: rosterSymbol },
    { ...projection, workflowRuns: rosterCustomPrototype }
  ]

  return Effect.gen(function* () {
    for (const candidate of projectionVariants) {
      const outcome = yield* validateS2SGitHubWorkflowRunsForHeadObservation(
        {
          receipt: { ...observed.right.receipt, projection: candidate },
          readRawBody: observed.right.readRawBody
        },
        HEAD_SHA
      ).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("RECEIPT_MISMATCH")
      }
    }
    expect(projectionAccessorRead).toBe(false)
  })
})

it.effect("distinguishes recomputation, self-hash, and exact receipt-shape failures", () => {
  const run = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  const jobs = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 1, jobs: [jobFixture()] }),
    RUN_ID,
    1,
    OBSERVED_AT,
    responseProvenance()
  )
  if (Either.isLeft(run) || Either.isLeft(jobs)) {
    return Effect.dieMessage("valid observation fixture was rejected")
  }
  const staleHashTamper = {
    receipt: {
      ...run.right.receipt,
      githubRequestId: "A1B2:C3D4:E5F6:TAMPERED"
    },
    readRawBody: run.right.readRawBody
  }
  let nestedAccessorRead = false
  const projectionWithAccessor = { ...run.right.receipt.projection }
  Object.defineProperty(projectionWithAccessor, "id", {
    enumerable: true,
    get: () => {
      nestedAccessorRead = true
      return RUN_ID
    }
  })
  const exactShapeTamper = {
    receipt: {
      ...run.right.receipt,
      projection: projectionWithAccessor
    },
    readRawBody: run.right.readRawBody
  }
  const changedProjection = {
    ...run.right.receipt.projection,
    name: "tampered"
  }
  const changedProjectionHash = canonicalS2SControlSha256(changedProjection)
  if (Either.isLeft(changedProjectionHash)) {
    return Effect.dieMessage("tampered projection was unexpectedly noncanonical")
  }
  const { receiptSha256: _oldReceiptHash, ...oldReceiptCore } = run.right.receipt
  const tamperedReceiptCore = {
    ...oldReceiptCore,
    projection: changedProjection,
    projectionSha256: changedProjectionHash.right
  }
  const tamperedReceiptHash = canonicalS2SControlSha256(tamperedReceiptCore)
  if (Either.isLeft(tamperedReceiptHash)) {
    return Effect.dieMessage("tampered receipt was unexpectedly noncanonical")
  }
  const fullyRehashedProjectionTamper = {
    receipt: {
      ...tamperedReceiptCore,
      receiptSha256: tamperedReceiptHash.right
    },
    readRawBody: run.right.readRawBody
  }
  const malformedProvenance = {
    receipt: {
      ...run.right.receipt,
      githubApiVersionSelected: "2099-01-01"
    },
    readRawBody: run.right.readRawBody
  }
  const malformedEtag = {
    receipt: {
      ...run.right.receipt,
      responseEtag: "not-an-etag"
    },
    readRawBody: run.right.readRawBody
  }
  const changedEtag = {
    receipt: {
      ...run.right.receipt,
      responseEtag: `"${"f".repeat(64)}"`
    },
    readRawBody: run.right.readRawBody
  }
  const wrongReceiptKind = {
    receipt: {
      ...run.right.receipt,
      kind: "ARTIFACT"
    },
    readRawBody: run.right.readRawBody
  }
  const invalidTimestamp = {
    receipt: {
      ...run.right.receipt,
      observedAtUnixSeconds: -1
    },
    readRawBody: run.right.readRawBody
  }

  return Effect.gen(function* () {
    const wrongIdentity = yield* validateS2SGitHubWorkflowRunObservation(
      run.right,
      RUN_ID + 1
    ).pipe(Effect.either)
    const wrongRawKind = yield* validateS2SGitHubWorkflowRunObservation(
      jobs.right,
      RUN_ID
    ).pipe(Effect.either)
    const staleHash = yield* validateS2SGitHubWorkflowRunObservation(
      staleHashTamper,
      RUN_ID
    ).pipe(Effect.either)
    const exactShape = yield* validateS2SGitHubWorkflowRunObservation(
      exactShapeTamper,
      RUN_ID
    ).pipe(Effect.either)
    const rehashed = yield* validateS2SGitHubWorkflowRunObservation(
      fullyRehashedProjectionTamper,
      RUN_ID
    ).pipe(Effect.either)
    const provenance = yield* validateS2SGitHubWorkflowRunObservation(
      malformedProvenance,
      RUN_ID
    ).pipe(Effect.either)
    const invalidEtag = yield* validateS2SGitHubWorkflowRunObservation(
      malformedEtag,
      RUN_ID
    ).pipe(Effect.either)
    const staleEtag = yield* validateS2SGitHubWorkflowRunObservation(
      changedEtag,
      RUN_ID
    ).pipe(Effect.either)
    const receiptKind = yield* validateS2SGitHubWorkflowRunObservation(
      wrongReceiptKind,
      RUN_ID
    ).pipe(Effect.either)
    const timestamp = yield* validateS2SGitHubWorkflowRunObservation(
      invalidTimestamp,
      RUN_ID
    ).pipe(Effect.either)
    expect(Either.isLeft(wrongIdentity) && wrongIdentity.left.reason).toBe(
      "RECOMPUTATION_REJECTED"
    )
    expect(Either.isLeft(wrongRawKind) && wrongRawKind.left.reason).toBe(
      "RECOMPUTATION_REJECTED"
    )
    expect(Either.isLeft(staleHash) && staleHash.left.reason).toBe(
      "RECEIPT_SELF_HASH_MISMATCH"
    )
    expect(Either.isLeft(exactShape) && exactShape.left.reason).toBe(
      "RECEIPT_MISMATCH"
    )
    expect(Either.isLeft(rehashed) && rehashed.left.reason).toBe(
      "RECEIPT_SELF_HASH_MISMATCH"
    )
    expect(Either.isLeft(provenance) && provenance.left.reason).toBe(
      "RECOMPUTATION_REJECTED"
    )
    expect(Either.isLeft(invalidEtag) && invalidEtag.left.reason).toBe(
      "RECOMPUTATION_REJECTED"
    )
    expect(Either.isLeft(staleEtag) && staleEtag.left.reason).toBe(
      "RECEIPT_SELF_HASH_MISMATCH"
    )
    expect(Either.isLeft(receiptKind) && receiptKind.left.reason).toBe(
      "RECEIPT_MISMATCH"
    )
    expect(Either.isLeft(timestamp) && timestamp.left.reason).toBe(
      "RECEIPT_REJECTED"
    )
    expect(nestedAccessorRead).toBe(false)
  })
})

it.effect("rejects invalid expected identity lazily without reading retained bytes", () => {
  const run = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  const runs = observeS2SGitHubWorkflowRunsForHead(
    jsonBytes({ total_count: 1, workflow_runs: [runFixture()] }),
    HEAD_SHA,
    OBSERVED_AT,
    responseProvenance()
  )
  if (Either.isLeft(run) || Either.isLeft(runs)) {
    return Effect.dieMessage("valid observation fixture was rejected")
  }
  let reads = 0
  const input = {
    receipt: run.right.receipt,
    readRawBody: () => {
      reads += 1
      return run.right.readRawBody()
    }
  }
  const invalidRun = validateS2SGitHubWorkflowRunObservation(input, 0)
  expect(reads).toBe(0)
  return Effect.gen(function* () {
    const runOutcome = yield* invalidRun.pipe(Effect.either)
    const headOutcome = yield* validateS2SGitHubWorkflowRunsForHeadObservation(
      runs.right,
      HEAD_SHA.toUpperCase()
    ).pipe(Effect.either)
    const wrongCanonicalHead = yield*
      validateS2SGitHubWorkflowRunsForHeadObservation(
        runs.right,
        "a".repeat(40)
      ).pipe(Effect.either)
    expect(Either.isLeft(runOutcome) && runOutcome.left.reason).toBe(
      "INVALID_ARGUMENT"
    )
    expect(Either.isLeft(headOutcome) && headOutcome.left.reason).toBe(
      "INVALID_ARGUMENT"
    )
    expect(
      Either.isLeft(wrongCanonicalHead) && wrongCanonicalHead.left.reason
    ).toBe("RECOMPUTATION_REJECTED")
    expect(reads).toBe(0)
  })
})

it.effect("treats self-consistent provenance as integrity, not GitHub-origin proof", () => {
  const fabricatedEtag = `"${"d".repeat(64)}"`
  const fabricated = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID,
    OBSERVED_AT + 77,
    Object.freeze({
      githubRequestId: "FABRICATED:SELF:CONSISTENT:ID",
      githubApiVersionSelected: S2S_GITHUB_API_VERSION,
      responseEtag: fabricatedEtag
    })
  )
  if (Either.isLeft(fabricated)) {
    return Effect.dieMessage("self-consistent observation fixture was rejected")
  }
  return Effect.gen(function* () {
    const validated = yield* validateS2SGitHubWorkflowRunObservation(
      fabricated.right,
      RUN_ID
    )
    expect(validated.receipt.githubRequestId).toBe(
      "FABRICATED:SELF:CONSISTENT:ID"
    )
    expect(validated.receipt.observedAtUnixSeconds).toBe(OBSERVED_AT + 77)
    expect(validated.receipt.responseEtag).toBe(fabricatedEtag)
  })
})

it("binds request-distinct response provenance into same-second receipts", () => {
  const raw = jsonBytes(runFixture())
  const first = observeS2SGitHubWorkflowRun(
    raw,
    RUN_ID,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:FIRST")
  )
  const second = observeS2SGitHubWorkflowRun(
    raw,
    RUN_ID,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:SECOND")
  )
  expect(Either.isRight(first)).toBe(true)
  expect(Either.isRight(second)).toBe(true)
  if (Either.isRight(first) && Either.isRight(second)) {
    expect(first.right.receipt.rawBodySha256).toBe(
      second.right.receipt.rawBodySha256
    )
    expect(first.right.receipt.projectionSha256).toBe(
      second.right.receipt.projectionSha256
    )
    expect(first.right.receipt.receiptSha256).not.toBe(
      second.right.receipt.receiptSha256
    )
    const { receiptSha256, ...receiptCore } = first.right.receipt
    const recomputed = canonicalS2SControlSha256(receiptCore)
    expect(Either.isRight(recomputed)).toBe(true)
    if (Either.isRight(recomputed)) expect(recomputed.right).toBe(receiptSha256)
    const tampered = canonicalS2SControlSha256({
      ...receiptCore,
      githubRequestId: "A1B2:C3D4:E5F6:TAMPERED"
    })
    expect(Either.isRight(tampered)).toBe(true)
    if (Either.isRight(tampered)) expect(tampered.right).not.toBe(receiptSha256)
  }
})

it("rejects absent, malformed, version-drifted, and accessor provenance", () => {
  let accessorRead = false
  const accessor = {
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: RESPONSE_ETAG
  }
  Object.defineProperty(accessor, "githubRequestId", {
    enumerable: true,
    get: () => {
      accessorRead = true
      return "A1B2:C3D4:E5F6:ACCESSOR"
    }
  })
  const hiddenExtra = { ...responseProvenance() }
  Object.defineProperty(hiddenExtra, "hidden", {
    enumerable: false,
    value: "must be rejected"
  })
  const outcomes = [
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      null
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      responseProvenance("contains whitespace")
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      {
        ...responseProvenance(),
        githubApiVersionSelected: "2099-01-01"
      }
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      { ...responseProvenance(), responseEtag: "not-an-etag" }
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      { ...responseProvenance(), responseEtag: null }
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      responseProvenance("x".repeat(257))
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      accessor
    ),
    observeS2SGitHubWorkflowRun(
      jsonBytes(runFixture()),
      RUN_ID,
      OBSERVED_AT,
      hiddenExtra
    )
  ]
  expect(outcomes.every(Either.isLeft)).toBe(true)
  for (const outcome of outcomes) {
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("PROVENANCE_REJECTED")
    }
  }
  expect(accessorRead).toBe(false)
})

it("normalizes a complete attempt-specific job page", () => {
  const second = {
    ...jobFixture(),
    id: JOB_ID + 1,
    name: "confirm",
    status: "in_progress",
    conclusion: null,
    completed_at: null,
    labels: ["z", "a"]
  }
  const outcome = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 2, jobs: [second, jobFixture()] }),
    RUN_ID,
    1,
    OBSERVED_AT,
    responseProvenance()
  )
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isRight(outcome)) {
    expect(outcome.right.receipt.projection.jobs.map((job) => job.id)).toEqual([
      JOB_ID,
      JOB_ID + 1
    ])
    expect(outcome.right.receipt.projection.jobs[1]?.labels).toEqual(["a", "z"])
    expect(outcome.right.receipt.endpointPathAndQuery).toContain(
      "/attempts/1/jobs?per_page=100"
    )
  }
})

it("binds both list and individual artifact projections", () => {
  const listed = observeS2SGitHubRunArtifacts(
    jsonBytes({ total_count: 1, artifacts: [artifactFixture()] }),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  const individual = observeS2SGitHubArtifact(
    jsonBytes(artifactFixture()),
    ARTIFACT_ID,
    OBSERVED_AT + 1,
    responseProvenance("A1B2:C3D4:E5F6:7891")
  )
  expect(Either.isRight(listed)).toBe(true)
  expect(Either.isRight(individual)).toBe(true)
  if (Either.isRight(individual)) {
    expect(individual.right.receipt.projection).toMatchObject({
      id: ARTIFACT_ID,
      digestSha256: DIGEST,
      workflowRunId: RUN_ID,
      workflowHeadSha: HEAD_SHA
    })
  }
})

it.effect("lazily reconstructs trusted artifact observations from one raw read", () => {
  const listedOutcome = observeS2SGitHubRunArtifacts(
    jsonBytes({ total_count: 1, artifacts: [artifactFixture()] }),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance("A1B2:C3D4:E5F6:ARTIFACTS")
  )
  const artifactOutcome = observeS2SGitHubArtifact(
    jsonBytes(artifactFixture()),
    ARTIFACT_ID,
    OBSERVED_AT + 1,
    responseProvenance("A1B2:C3D4:E5F6:ARTIFACT")
  )
  if (Either.isLeft(listedOutcome) || Either.isLeft(artifactOutcome)) {
    return Effect.dieMessage("valid artifact observation fixture was rejected")
  }
  let listedReads = 0
  let artifactReads = 0
  let listedReaderThis: unknown = "not-called"
  const wrappedListed = Object.freeze({
    receipt: listedOutcome.right.receipt,
    readRawBody: function (this: unknown) {
      listedReaderThis = this
      listedReads += 1
      return listedOutcome.right.readRawBody()
    }
  })
  const wrappedArtifact = Object.freeze({
    receipt: artifactOutcome.right.receipt,
    readRawBody: () => {
      artifactReads += 1
      return artifactOutcome.right.readRawBody()
    }
  })
  const listedValidation = validateS2SGitHubRunArtifactsObservation(
    wrappedListed,
    RUN_ID
  )
  const artifactValidation = validateS2SGitHubArtifactObservation(
    wrappedArtifact,
    ARTIFACT_ID
  )
  expect([listedReads, artifactReads]).toEqual([0, 0])

  return Effect.gen(function* () {
    const listed = yield* listedValidation
    const artifact = yield* artifactValidation
    expect([listedReads, artifactReads]).toEqual([1, 1])
    expect(listedReaderThis).toBeUndefined()
    expect(listed).not.toBe(wrappedListed)
    expect(artifact).not.toBe(wrappedArtifact)
    expect(listed.receipt).not.toBe(wrappedListed.receipt)
    expect(artifact.receipt).not.toBe(wrappedArtifact.receipt)
    expect(listed.receipt).toEqual(wrappedListed.receipt)
    expect(artifact.receipt).toEqual(wrappedArtifact.receipt)
    expect(listed.receipt.projection).not.toBe(
      wrappedListed.receipt.projection
    )
    expect(listed.receipt.projection.artifacts).not.toBe(
      wrappedListed.receipt.projection.artifacts
    )
    expect(artifact.receipt.projection).not.toBe(
      wrappedArtifact.receipt.projection
    )
    expect(Object.isFrozen(listed)).toBe(true)
    expect(Object.isFrozen(listed.receipt.projection.artifacts)).toBe(true)
    expect(Object.isFrozen(artifact)).toBe(true)
    const retained = artifact.readRawBody()
    retained.fill(0)
    expect(artifact.readRawBody()[0]).toBe(0x7b)
  })
})

it.effect("rejects hostile, counterfeit, and identity-drifted artifact observations", () => {
  const listed = observeS2SGitHubRunArtifacts(
    jsonBytes({ total_count: 1, artifacts: [artifactFixture()] }),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  const artifact = observeS2SGitHubArtifact(
    jsonBytes(artifactFixture()),
    ARTIFACT_ID,
    OBSERVED_AT + 1,
    responseProvenance("A1B2:C3D4:E5F6:7891")
  )
  if (Either.isLeft(listed) || Either.isLeft(artifact)) {
    return Effect.dieMessage("valid artifact observation fixture was rejected")
  }

  let rejectedReceiptReads = 0
  const hostileRoot = new Proxy({}, {
    ownKeys: () => {
      throw new Error("hostile artifact wrapper trap")
    }
  })
  const hostileReceipt = {
    receipt: new Proxy({}, {
      ownKeys: () => {
        throw new Error("hostile artifact receipt trap")
      }
    }),
    readRawBody: () => {
      rejectedReceiptReads += 1
      return artifact.right.readRawBody()
    }
  }
  const hostileProjection = new Proxy(
    { ...artifact.right.receipt.projection },
    {
      ownKeys: () => {
        throw new Error("hostile artifact projection trap")
      }
    }
  )

  const listedArtifact = listed.right.receipt.projection.artifacts[0]
  if (listedArtifact === undefined) {
    return Effect.dieMessage("artifact-list fixture is absent")
  }
  const counterfeitProjection = {
    ...listed.right.receipt.projection,
    artifacts: [{ ...listedArtifact, name: "counterfeit" }]
  }
  const counterfeitProjectionHash = canonicalS2SControlSha256(
    counterfeitProjection
  )
  if (Either.isLeft(counterfeitProjectionHash)) {
    return Effect.dieMessage("counterfeit projection was unexpectedly noncanonical")
  }
  const {
    receiptSha256: _originalReceiptHash,
    ...listedReceiptCore
  } = listed.right.receipt
  const counterfeitReceiptCore = {
    ...listedReceiptCore,
    projection: counterfeitProjection,
    projectionSha256: counterfeitProjectionHash.right
  }
  const counterfeitReceiptHash = canonicalS2SControlSha256(
    counterfeitReceiptCore
  )
  if (Either.isLeft(counterfeitReceiptHash)) {
    return Effect.dieMessage("counterfeit receipt was unexpectedly noncanonical")
  }
  const counterfeitListed = {
    receipt: {
      ...counterfeitReceiptCore,
      receiptSha256: counterfeitReceiptHash.right
    },
    readRawBody: listed.right.readRawBody
  }

  const artifactRaw = artifact.right.readRawBody()
  const driftedRaw = new Uint8Array(artifactRaw)
  driftedRaw[0] = 0x5b
  let rawProxyReads = 0
  let rawDriftReads = 0
  let semanticDriftReads = 0
  let invalidIdentityReads = 0

  return Effect.gen(function* () {
    const hostileRootOutcome = yield*
      validateS2SGitHubRunArtifactsObservation(hostileRoot, RUN_ID).pipe(
        Effect.either
      )
    const hostileReceiptOutcome = yield*
      validateS2SGitHubArtifactObservation(
        hostileReceipt,
        ARTIFACT_ID
      ).pipe(Effect.either)
    const hostileProjectionOutcome = yield*
      validateS2SGitHubArtifactObservation(
        {
          receipt: {
            ...artifact.right.receipt,
            projection: hostileProjection
          },
          readRawBody: artifact.right.readRawBody
        },
        ARTIFACT_ID
      ).pipe(Effect.either)
    const rawProxyOutcome = yield* validateS2SGitHubArtifactObservation(
      {
        receipt: artifact.right.receipt,
        readRawBody: () => {
          rawProxyReads += 1
          return new Proxy(artifactRaw, {})
        }
      },
      ARTIFACT_ID
    ).pipe(Effect.either)
    const rawDriftOutcome = yield* validateS2SGitHubArtifactObservation(
      {
        receipt: artifact.right.receipt,
        readRawBody: () => {
          rawDriftReads += 1
          return driftedRaw
        }
      },
      ARTIFACT_ID
    ).pipe(Effect.either)
    const counterfeitOutcome = yield*
      validateS2SGitHubRunArtifactsObservation(
        counterfeitListed,
        RUN_ID
      ).pipe(Effect.either)
    const listIdentityDrift = yield*
      validateS2SGitHubRunArtifactsObservation(
        {
          receipt: listed.right.receipt,
          readRawBody: () => {
            semanticDriftReads += 1
            return listed.right.readRawBody()
          }
        },
        RUN_ID + 1
      ).pipe(Effect.either)
    const artifactIdentityDrift = yield*
      validateS2SGitHubArtifactObservation(
        artifact.right,
        ARTIFACT_ID + 1
      ).pipe(Effect.either)
    const crossKindDrift = yield* validateS2SGitHubArtifactObservation(
      listed.right,
      ARTIFACT_ID
    ).pipe(Effect.either)
    const invalidIdentity = yield*
      validateS2SGitHubRunArtifactsObservation(
        {
          receipt: listed.right.receipt,
          readRawBody: () => {
            invalidIdentityReads += 1
            return listed.right.readRawBody()
          }
        },
        0
      ).pipe(Effect.either)

    expect(
      Either.isLeft(hostileRootOutcome) && hostileRootOutcome.left.reason
    ).toBe("WRAPPER_REJECTED")
    expect(
      Either.isLeft(hostileReceiptOutcome) && hostileReceiptOutcome.left.reason
    ).toBe("RECEIPT_REJECTED")
    expect(
      Either.isLeft(hostileProjectionOutcome) &&
        hostileProjectionOutcome.left.reason
    ).toBe("RECEIPT_MISMATCH")
    expect(
      Either.isLeft(rawProxyOutcome) && rawProxyOutcome.left.reason
    ).toBe("RAW_BODY_REJECTED")
    expect(
      Either.isLeft(rawDriftOutcome) && rawDriftOutcome.left.reason
    ).toBe("RAW_BODY_DRIFT")
    expect(
      Either.isLeft(counterfeitOutcome) && counterfeitOutcome.left.reason
    ).toBe("RECEIPT_SELF_HASH_MISMATCH")
    expect(
      Either.isLeft(listIdentityDrift) && listIdentityDrift.left.reason
    ).toBe("RECOMPUTATION_REJECTED")
    expect(
      Either.isLeft(artifactIdentityDrift) && artifactIdentityDrift.left.reason
    ).toBe("RECOMPUTATION_REJECTED")
    expect(Either.isLeft(crossKindDrift) && crossKindDrift.left.reason).toBe(
      "RECOMPUTATION_REJECTED"
    )
    expect(Either.isLeft(invalidIdentity) && invalidIdentity.left.reason).toBe(
      "INVALID_ARGUMENT"
    )
    expect([
      rejectedReceiptReads,
      rawProxyReads,
      rawDriftReads,
      semanticDriftReads,
      invalidIdentityReads
    ]).toEqual([0, 1, 1, 1, 0])
  })
})

it("rejects incomplete pagination and requested-identity mismatches", () => {
  const incomplete = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 2, jobs: [jobFixture()] }),
    RUN_ID,
    1,
    OBSERVED_AT,
    responseProvenance()
  )
  const wrongRun = observeS2SGitHubWorkflowRun(
    jsonBytes(runFixture()),
    RUN_ID + 1,
    OBSERVED_AT,
    responseProvenance()
  )
  const wrongArtifactRun = observeS2SGitHubRunArtifacts(
    jsonBytes({ total_count: 1, artifacts: [artifactFixture()] }),
    RUN_ID + 1,
    OBSERVED_AT,
    responseProvenance()
  )
  expect(Either.isLeft(incomplete)).toBe(true)
  expect(Either.isLeft(wrongRun)).toBe(true)
  expect(Either.isLeft(wrongArtifactRun)).toBe(true)
  if (Either.isLeft(incomplete)) expect(incomplete.left.reason).toBe("PROJECTION_REJECTED")
  if (Either.isLeft(wrongRun)) expect(wrongRun.left.reason).toBe("IDENTITY_MISMATCH")
})

it("rejects duplicate raw keys before a projection can hide them", () => {
  const raw = encoder.encode(
    `${JSON.stringify(runFixture()).replace(
      `"id":${RUN_ID}`,
      `"id":${RUN_ID},"id":${RUN_ID}`
    )}\n`
  )
  const outcome = observeS2SGitHubWorkflowRun(
    raw,
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isLeft(outcome)) expect(outcome.left.reason).toBe("JSON_REJECTED")
})

it("rejects malformed digests, timestamps, duplicate labels, and reruns", () => {
  const malformedArtifact = { ...artifactFixture(), digest: DIGEST }
  const invalidTimestamp = { ...runFixture(), created_at: "2026-02-30T00:00:00Z" }
  const duplicateLabels = { ...jobFixture(), labels: ["same", "same"] }
  const artifactOutcome = observeS2SGitHubArtifact(
    jsonBytes(malformedArtifact),
    ARTIFACT_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  const runOutcome = observeS2SGitHubWorkflowRun(
    jsonBytes(invalidTimestamp),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  const jobsOutcome = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 1, jobs: [duplicateLabels] }),
    RUN_ID,
    1,
    OBSERVED_AT,
    responseProvenance()
  )
  const rerunOutcome = observeS2SGitHubWorkflowAttemptJobs(
    jsonBytes({ total_count: 0, jobs: [] }),
    RUN_ID,
    2,
    OBSERVED_AT,
    responseProvenance()
  )
  const rerunPayload = observeS2SGitHubWorkflowRun(
    jsonBytes({ ...runFixture(), run_attempt: 2 }),
    RUN_ID,
    OBSERVED_AT,
    responseProvenance()
  )
  expect([
    Either.isLeft(artifactOutcome),
    Either.isLeft(runOutcome),
    Either.isLeft(jobsOutcome),
    Either.isLeft(rerunOutcome),
    Either.isLeft(rerunPayload)
  ]).toEqual([true, true, true, true, true])
})

it.effect("composes the Effect observer over a narrow read-only transport port", () => {
  const requested: Array<string> = []
  const transport = Layer.succeed(
    S2SGitHubHttpTransport,
    S2SGitHubHttpTransport.of({
      getJson: (endpoint) => {
        requested.push(endpoint)
        const body = endpoint.includes("/actions/workflows/")
          ? jsonBytes({ total_count: 1, workflow_runs: [runFixture()] })
          : endpoint.includes("/attempts/1/jobs")
          ? jsonBytes({ total_count: 1, jobs: [jobFixture()] })
          : endpoint.includes("/artifacts?per_page=100")
            ? jsonBytes({ total_count: 1, artifacts: [artifactFixture()] })
            : endpoint.includes(`/artifacts/${ARTIFACT_ID}`)
              ? jsonBytes(artifactFixture())
              : jsonBytes(runFixture())
        return Effect.succeed(
          Object.freeze({
            status: 200,
            contentType: "application/json",
            location: null,
            githubRequestId: `A1B2:C3D4:E5F6:${requested.length}`,
            githubApiVersionSelected: S2S_GITHUB_API_VERSION,
            etag: RESPONSE_ETAG,
            body
          })
        )
      },
      downloadArtifactArchive: () => Effect.dieMessage("not used")
    })
  )
  const observerLayer = S2SGitHubObserverLive.pipe(Layer.provide(transport))
  return Effect.gen(function* () {
    yield* TestClock.setTime(OBSERVED_AT * 1_000)
    const observer = yield* S2SGitHubObserver
    const run = yield* observer.observeWorkflowRun(RUN_ID)
    const jobs = yield* observer.observeWorkflowAttemptJobs(RUN_ID)
    const runsForHead = yield* observer.observeWorkflowRunsForHead(HEAD_SHA)
    const artifacts = yield* observer.observeRunArtifacts(RUN_ID)
    const artifact = yield* observer.observeArtifact(ARTIFACT_ID)
    expect(run.receipt.projection.id).toBe(RUN_ID)
    expect(jobs.receipt.projection.jobs).toHaveLength(1)
    expect(runsForHead.receipt.projection.workflowRuns).toHaveLength(1)
    expect(artifacts.receipt.projection.artifacts).toHaveLength(1)
    expect(artifact.receipt.projection.id).toBe(ARTIFACT_ID)
    expect([
      run,
      jobs,
      runsForHead,
      artifacts,
      artifact
    ].every((observation) =>
      observation.receipt.observedAtUnixSeconds === OBSERVED_AT
    )).toBe(true)
    expect(requested).toEqual([
      `/repos/gj3447/HSWM/actions/runs/${RUN_ID}`,
      `/repos/gj3447/HSWM/actions/runs/${RUN_ID}/attempts/1/jobs?per_page=100`,
      `/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&head_sha=${HEAD_SHA}&per_page=100`,
      `/repos/gj3447/HSWM/actions/runs/${RUN_ID}/artifacts?per_page=100`,
      `/repos/gj3447/HSWM/actions/artifacts/${ARTIFACT_ID}`
    ])
  }).pipe(Effect.provide(observerLayer))
})

it.effect("rejects a noncanonical head SHA before invoking a replaceable transport", () => {
  let requested = 0
  const transport = Layer.succeed(
    S2SGitHubHttpTransport,
    S2SGitHubHttpTransport.of({
      getJson: () => {
        requested += 1
        return Effect.dieMessage("must not run")
      },
      downloadArtifactArchive: () => Effect.dieMessage("not used")
    })
  )
  const observerLayer = S2SGitHubObserverLive.pipe(Layer.provide(transport))
  return Effect.gen(function* () {
    const observer = yield* S2SGitHubObserver
    const outcome = yield* observer
      .observeWorkflowRunsForHead(HEAD_SHA.toUpperCase())
      .pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left._tag).toBe("S2SGitHubObservationError")
      if (outcome.left._tag === "S2SGitHubObservationError") {
        expect(outcome.left.reason).toBe("INVALID_ARGUMENT")
      }
    }
    expect(requested).toBe(0)
  }).pipe(Effect.provide(observerLayer))
})

it.effect("allows only the exact canonical workflow-runs-for-head transport path", () => {
  const originalFetch = globalThis.fetch
  const exact = `/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&head_sha=${HEAD_SHA}&per_page=100`
  let invoked = 0
  globalThis.fetch = (async () => {
    invoked += 1
    return new Response(
      jsonBytes({ total_count: 0, workflow_runs: [] }),
      {
        status: 200,
        headers: {
          "content-type": "application/json",
          "x-github-request-id": "A1B2:C3D4:E5F6:LIST",
          "x-github-api-version-selected": S2S_GITHUB_API_VERSION,
          etag: RESPONSE_ETAG
        }
      }
    )
  }) as typeof fetch
  const invalid = [
    `/repos/gj3447/HSWM/actions/workflows/swm0w-s2s-confirmatory.yml/runs?event=push&branch=main&head_sha=${HEAD_SHA}&per_page=100`,
    `${exact}&page=1`,
    exact.replace("confirmatory.yml", "confirmatory%2eyml"),
    exact.replace(HEAD_SHA, HEAD_SHA.toUpperCase()),
    exact.replace("&per_page=100", "")
  ]
  return Effect.gen(function* () {
    const transport = yield* S2SGitHubHttpTransport
    const accepted = yield* transport.getJson(exact).pipe(Effect.either)
    expect(Either.isRight(accepted)).toBe(true)
    for (const endpoint of invalid) {
      const outcome = yield* transport.getJson(endpoint).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left.reason).toBe("CONFIGURATION_INVALID")
      }
    }
    expect(invoked).toBe(1)
  }).pipe(
    Effect.provide(
      makeS2SGitHubHttpTransportLiveLayer({ token: "test-token" })
    ),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("rejects transport config accessors without reading the token", () => {
  let invoked = false
  const malicious = {}
  Object.defineProperty(malicious, "token", {
    enumerable: true,
    get: () => {
      invoked = true
      return "secret"
    }
  })
  return Effect.gen(function* () {
    const exit = yield* Effect.gen(function* () {
      yield* S2SGitHubHttpTransport
    }).pipe(
      Effect.provide(
        makeS2SGitHubHttpTransportLiveLayer(
          malicious as { readonly token: string }
        )
      ),
      Effect.exit
    )
    expect(Exit.isFailure(exit)).toBe(true)
    expect(invoked).toBe(false)
  })
})

it.effect("strips authorization across the manual artifact redirect", () => {
  const originalFetch = globalThis.fetch
  const invocations: Array<{
    readonly url: string
    readonly authorization: string | null
    readonly redirect: "error" | "follow" | "manual" | undefined
  }> = []
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    const headers = new Headers(init?.headers)
    invocations.push({
      url,
      authorization: headers.get("authorization"),
      redirect: init?.redirect
    })
    if (invocations.length === 1) {
      return new Response("redirecting", {
        status: 302,
        headers: {
          location: "https://objects.example.invalid/signed/artifact.zip?sig=private",
          "x-github-request-id": "A1B2:C3D4:E5F6:REDIRECT",
          "x-github-api-version-selected": S2S_GITHUB_API_VERSION
        }
      })
    }
    return new Response(Uint8Array.from([0x50, 0x4b, 0x03, 0x04]), {
      status: 200,
      headers: {
        "content-length": "4",
        "content-type": "application/zip",
        etag: `"${"a".repeat(64)}"`
      }
    })
  }) as typeof fetch

  const program = Effect.gen(function* () {
    yield* TestClock.setTime(OBSERVED_AT * 1_000)
    const transport = yield* S2SGitHubHttpTransport
    const result = yield* transport.downloadArtifactArchive(
      ARTIFACT_ID,
      1_024
    )
    const firstRead = result.readArchiveBytes()
    expect(firstRead).toEqual(Uint8Array.from([0x50, 0x4b, 0x03, 0x04]))
    firstRead.fill(0)
    expect(result.readArchiveBytes()).toEqual(
      Uint8Array.from([0x50, 0x4b, 0x03, 0x04])
    )
    expect(result.receipt.downloadedArchiveSha256).toMatch(/^[0-9a-f]{64}$/)
    expect(result.receipt.receiptSha256).toMatch(/^[0-9a-f]{64}$/)
    expect(result.receipt).toMatchObject({
      downloadedAtUnixSeconds: OBSERVED_AT,
      redirectHttpStatus: 302,
      redirectGitHubRequestId: "A1B2:C3D4:E5F6:REDIRECT",
      redirectGitHubApiVersionSelected: S2S_GITHUB_API_VERSION,
      archiveHttpStatus: 200,
      archiveMediaType: "application/zip",
      archiveResponseEtag: `"${"a".repeat(64)}"`
    })
    expect(invocations).toHaveLength(2)
    expect(invocations[0]).toMatchObject({
      url: `https://api.github.com/repos/gj3447/HSWM/actions/artifacts/${ARTIFACT_ID}/zip`,
      authorization: "Bearer test-token",
      redirect: "manual"
    })
    expect(invocations[1]).toMatchObject({
      authorization: null,
      redirect: "error"
    })
  }).pipe(
    Effect.provide(
      makeS2SGitHubHttpTransportLiveLayer({ token: "test-token" })
    ),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
  return program
})

it.effect("rejects local and IP-literal artifact redirect targets", () => {
  const originalFetch = globalThis.fetch
  let invocations = 0
  globalThis.fetch = (async () => {
    invocations += 1
    if (invocations > 1) throw new Error("redirect target must not be fetched")
    return new Response("redirecting", {
      status: 302,
      headers: {
        location: "https://127.0.0.1/signed/artifact.zip",
        "x-github-request-id": "A1B2:C3D4:E5F6:LOCAL",
        "x-github-api-version-selected": S2S_GITHUB_API_VERSION
      }
    })
  }) as typeof fetch
  return Effect.gen(function* () {
    const transport = yield* S2SGitHubHttpTransport
    const outcome = yield* transport
      .downloadArtifactArchive(ARTIFACT_ID, 1_024)
      .pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("REDIRECT_REJECTED")
    }
    expect(invocations).toBe(1)
  }).pipe(
    Effect.provide(
      makeS2SGitHubHttpTransportLiveLayer({ token: "test-token" })
    ),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("refuses a non-200 response from an alternate transport Layer", () => {
  const transport = Layer.succeed(
    S2SGitHubHttpTransport,
    S2SGitHubHttpTransport.of({
      getJson: () =>
        Effect.succeed({
          status: 503,
          contentType: "application/json",
          location: null,
          githubRequestId: null,
          githubApiVersionSelected: null,
          etag: null,
          body: jsonBytes(runFixture())
        }),
      downloadArtifactArchive: () => Effect.dieMessage("not used")
    })
  )
  const observerLayer = S2SGitHubObserverLive.pipe(Layer.provide(transport))
  return Effect.gen(function* () {
    const observer = yield* S2SGitHubObserver
    const outcome = yield* observer.observeWorkflowRun(RUN_ID).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left._tag).toBe("S2SGitHubTransportError")
      if (outcome.left._tag === "S2SGitHubTransportError") {
        expect(outcome.left.reason).toBe("HTTP_STATUS_UNEXPECTED")
        expect(outcome.left.httpStatus).toBe(503)
      }
    }
  }).pipe(Effect.provide(observerLayer))
})

it.effect("refuses metadata without request identity, selected version, or ETag", () => {
  const transport = Layer.succeed(
    S2SGitHubHttpTransport,
    S2SGitHubHttpTransport.of({
      getJson: () =>
        Effect.succeed({
          status: 200,
          contentType: "application/json",
          location: null,
          githubRequestId: null,
          githubApiVersionSelected: null,
          etag: null,
          body: jsonBytes(runFixture())
        }),
      downloadArtifactArchive: () => Effect.dieMessage("not used")
    })
  )
  const observerLayer = S2SGitHubObserverLive.pipe(Layer.provide(transport))
  return Effect.gen(function* () {
    const observer = yield* S2SGitHubObserver
    const outcome = yield* observer.observeWorkflowRun(RUN_ID).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome) && outcome.left._tag === "S2SGitHubTransportError") {
      expect(outcome.left.reason).toBe("RESPONSE_HEADERS_REJECTED")
    }
  }).pipe(Effect.provide(observerLayer))
})

it.effect("propagates Effect fiber interruption into the live fetch signal", () => {
  const originalFetch = globalThis.fetch
  let aborted = false
  globalThis.fetch = ((_input: string | URL | Request, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal
      if (signal === null || signal === undefined) {
        reject(new Error("missing signal"))
        return
      }
      const onAbort = (): void => {
        aborted = true
        reject(new Error("aborted"))
      }
      if (signal.aborted) onAbort()
      else signal.addEventListener("abort", onAbort, { once: true })
    })) as typeof fetch

  return Effect.gen(function* () {
    const transport = yield* S2SGitHubHttpTransport
    const fiber = yield* Effect.fork(
      transport.getJson(`/repos/gj3447/HSWM/actions/runs/${RUN_ID}`)
    )
    yield* Effect.promise(
      () => new Promise<void>((resolve) => setImmediate(resolve))
    )
    yield* Fiber.interrupt(fiber)
    expect(aborted).toBe(true)
  }).pipe(
    Effect.provide(
      makeS2SGitHubHttpTransportLiveLayer({ token: "test-token" })
    ),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("cancels an unconsumed body rejected by Content-Length", () => {
  const originalFetch = globalThis.fetch
  let cancelled = false
  globalThis.fetch = (async () =>
    new Response(
      new ReadableStream<Uint8Array>({
        pull: () => undefined,
        cancel: () => {
          cancelled = true
        }
      }),
      {
        status: 200,
        headers: {
          "content-length": String(S2S_GITHUB_JSON_MAX_BYTES + 1),
          "content-type": "application/json"
        }
      }
    )) as typeof fetch
  return Effect.gen(function* () {
    const transport = yield* S2SGitHubHttpTransport
    const outcome = yield* transport
      .getJson(`/repos/gj3447/HSWM/actions/runs/${RUN_ID}`)
      .pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("RESPONSE_LIMIT_EXCEEDED")
    }
    expect(cancelled).toBe(true)
  }).pipe(
    Effect.provide(
      makeS2SGitHubHttpTransportLiveLayer({ token: "test-token" })
    ),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it.effect("rejects percent-encoded path traversal before bearer-token fetch", () => {
  const originalFetch = globalThis.fetch
  let invoked = false
  globalThis.fetch = (async () => {
    invoked = true
    throw new Error("must not fetch")
  }) as typeof fetch
  return Effect.gen(function* () {
    const transport = yield* S2SGitHubHttpTransport
    const outcome = yield* transport
      .getJson(
        "/repos/gj3447/HSWM/actions/%2e%2e/%2e%2e/%2e%2e/user"
      )
      .pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("CONFIGURATION_INVALID")
    }
    expect(invoked).toBe(false)
  }).pipe(
    Effect.provide(
      makeS2SGitHubHttpTransportLiveLayer({ token: "test-token" })
    ),
    Effect.ensuring(
      Effect.sync(() => {
        globalThis.fetch = originalFetch
      })
    )
  )
})

it("returns typed download validation errors for hostile proxies and byte accessors", () => {
  const rootProxy = new Proxy({}, {
    ownKeys: () => {
      throw new Error("hostile ownKeys trap")
    }
  })
  let rootOutcome: ReturnType<typeof validateS2SGitHubArtifactDownload> | undefined
  expect(() => {
    rootOutcome = validateS2SGitHubArtifactDownload(
      rootProxy,
      ARTIFACT_ID,
      1_024
    )
  }).not.toThrow()
  expect(rootOutcome !== undefined && Either.isLeft(rootOutcome)).toBe(true)
  if (rootOutcome !== undefined && Either.isLeft(rootOutcome)) {
    expect(rootOutcome.left.reason).toBe("INVALID_ARGUMENT")
  }

  const archive = Uint8Array.from([0x50, 0x4b, 0x03, 0x04])
  const receiptCore = Object.freeze({
    schemaVersion: S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
    apiVersion: S2S_GITHUB_API_VERSION,
    repository: S2S_GITHUB_REPOSITORY,
    artifactId: ARTIFACT_ID,
    endpointPathAndQuery: `/repos/${S2S_GITHUB_REPOSITORY}/actions/artifacts/${ARTIFACT_ID}/zip`,
    downloadedAtUnixSeconds: OBSERVED_AT,
    redirectHttpStatus: 302,
    redirectGitHubRequestId: "A1B2:C3D4:E5F6:DOWNLOAD",
    redirectGitHubApiVersionSelected: S2S_GITHUB_API_VERSION,
    redirectResponseEtag: null,
    redirectUrlSha256: "a".repeat(64),
    redirectOrigin: "https://objects.example.invalid",
    archiveHttpStatus: 200,
    archiveMediaType: "application/zip",
    archiveResponseEtag: `"${"a".repeat(64)}"`,
    archiveByteLength: archive.byteLength,
    downloadedArchiveSha256: rawS2SFileSha256(archive)
  })
  const receiptHash = canonicalS2SControlSha256(receiptCore)
  expect(Either.isRight(receiptHash)).toBe(true)
  if (Either.isLeft(receiptHash)) return
  const validDownload = Object.freeze({
    receipt: Object.freeze({
      ...receiptCore,
      receiptSha256: receiptHash.right
    }),
    readArchiveBytes: () => new Uint8Array(archive)
  })
  const validOutcome = validateS2SGitHubArtifactDownload(
    validDownload,
    ARTIFACT_ID,
    1_024
  )
  expect(Either.isRight(validOutcome)).toBe(true)
  const tamperedOutcome = validateS2SGitHubArtifactDownload(
    Object.freeze({
      ...validDownload,
      receipt: Object.freeze({
        ...validDownload.receipt,
        redirectGitHubRequestId: "A1B2:C3D4:E5F6:TAMPERED"
      })
    }),
    ARTIFACT_ID,
    1_024
  )
  expect(Either.isLeft(tamperedOutcome)).toBe(true)
  if (Either.isLeft(tamperedOutcome)) {
    expect(tamperedOutcome.left.reason).toBe("RECEIPT_SELF_HASH_MISMATCH")
  }
  const hostileArchive = new Proxy(archive, {})
  const archiveOutcome = validateS2SGitHubArtifactDownload(
    Object.freeze({
      receipt: Object.freeze({
        ...receiptCore,
        receiptSha256: receiptHash.right
      }),
      readArchiveBytes: () => hostileArchive
    }),
    ARTIFACT_ID,
    1_024
  )
  expect(Either.isLeft(archiveOutcome)).toBe(true)
  if (Either.isLeft(archiveOutcome)) {
    expect(archiveOutcome.left.reason).toBe("ARCHIVE_BYTES_DRIFT")
  }

  if (typeof SharedArrayBuffer !== "undefined") {
    const crossRealmShared: unknown = runInNewContext(
      `new Uint8Array(new SharedArrayBuffer(${archive.byteLength}))`
    )
    if (crossRealmShared === null || typeof crossRealmShared !== "object") {
      throw new Error("cross-realm shared archive fixture is invalid")
    }
    Object.setPrototypeOf(crossRealmShared, Uint8Array.prototype)
    const crossRealmOutcome = validateS2SGitHubArtifactDownload(
      Object.freeze({
        receipt: Object.freeze({
          ...receiptCore,
          receiptSha256: receiptHash.right
        }),
        readArchiveBytes: () => crossRealmShared
      }),
      ARTIFACT_ID,
      1_024
    )
    expect(Either.isLeft(crossRealmOutcome)).toBe(true)
    if (Either.isLeft(crossRealmOutcome)) {
      expect(crossRealmOutcome.left.reason).toBe("ARCHIVE_BYTES_DRIFT")
    }
  }

  let accessorRead = false
  const accessorArchive = new Uint8Array(archive)
  Object.defineProperty(accessorArchive, "buffer", {
    configurable: true,
    get: () => {
      accessorRead = true
      throw new Error("must not read")
    }
  })
  const accessorOutcome = validateS2SGitHubArtifactDownload(
    Object.freeze({
      receipt: Object.freeze({
        ...receiptCore,
        receiptSha256: receiptHash.right
      }),
      readArchiveBytes: () => accessorArchive
    }),
    ARTIFACT_ID,
    1_024
  )
  expect(Either.isLeft(accessorOutcome)).toBe(true)
  expect(accessorRead).toBe(false)
})
