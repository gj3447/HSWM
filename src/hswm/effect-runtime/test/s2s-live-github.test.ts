import { expect, it } from "@effect/vitest"
import { Effect, Either, Exit, Fiber, Layer } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
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
  validateS2SGitHubArtifactDownload
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
        const body = endpoint.includes("/attempts/1/jobs")
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
    const observer = yield* S2SGitHubObserver
    const run = yield* observer.observeWorkflowRun(RUN_ID)
    const jobs = yield* observer.observeWorkflowAttemptJobs(RUN_ID)
    const artifacts = yield* observer.observeRunArtifacts(RUN_ID)
    const artifact = yield* observer.observeArtifact(ARTIFACT_ID)
    expect(run.receipt.projection.id).toBe(RUN_ID)
    expect(jobs.receipt.projection.jobs).toHaveLength(1)
    expect(artifacts.receipt.projection.artifacts).toHaveLength(1)
    expect(artifact.receipt.projection.id).toBe(ARTIFACT_ID)
    expect(requested).toEqual([
      `/repos/gj3447/HSWM/actions/runs/${RUN_ID}`,
      `/repos/gj3447/HSWM/actions/runs/${RUN_ID}/attempts/1/jobs?per_page=100`,
      `/repos/gj3447/HSWM/actions/runs/${RUN_ID}/artifacts?per_page=100`,
      `/repos/gj3447/HSWM/actions/artifacts/${ARTIFACT_ID}`
    ])
  }).pipe(Effect.provide(observerLayer))
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
          "content-length": String(9 * 1_048_576),
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
