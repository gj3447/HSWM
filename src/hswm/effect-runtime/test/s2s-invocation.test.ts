import {
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync
} from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"
import { vi } from "vitest"

import { canonicalS2SControlSha256 } from "../src/s2s-canonical.js"
import {
  S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS,
  S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES,
  S2S_CURRENT_INVOCATION_EVIDENCE_SCHEMA_VERSION,
  S2SCurrentInvocation,
  S2SCurrentInvocationLive,
  inspectS2SCurrentInvocationAuthority,
  makeS2SCurrentInvocationTestLayer,
  readS2SCurrentInvocationEventBytes,
  validateS2SCurrentInvocation
} from "../src/s2s-invocation.js"
import {
  S2S_CONFIRMATORY_WORKFLOW_CONTRACT,
  s2sConfirmatoryWorkflowContractSha256
} from "../src/s2s-workflow-contract.js"

const SOURCE_A = "a".repeat(40)
const REGISTRATION_B = "b".repeat(40)
const RUN_ID = 9_876_543
const UTF8_ENCODER = new TextEncoder()

const environmentFixture = (): Record<string, unknown> => ({
  GITHUB_ACTIONS: "true",
  GITHUB_API_URL: "https://api.github.com",
  GITHUB_EVENT_NAME: "push",
  GITHUB_JOB: "confirm",
  GITHUB_REF: "refs/heads/main",
  GITHUB_REF_NAME: "main",
  GITHUB_REF_TYPE: "branch",
  GITHUB_REPOSITORY: "gj3447/HSWM",
  GITHUB_RUN_ATTEMPT: "1",
  GITHUB_RUN_ID: String(RUN_ID),
  GITHUB_SERVER_URL: "https://github.com",
  GITHUB_SHA: REGISTRATION_B,
  GITHUB_WORKFLOW: "SWM-0W-S2S confirmatory",
  GITHUB_WORKFLOW_REF:
    "gj3447/HSWM/.github/workflows/swm0w-s2s-confirmatory.yml@refs/heads/main",
  GITHUB_WORKFLOW_SHA: REGISTRATION_B,
  RUNNER_ARCH: "X64",
  RUNNER_ENVIRONMENT: "github-hosted",
  RUNNER_OS: "Linux"
})

const eventFixture = (): Record<string, unknown> => ({
  after: REGISTRATION_B,
  base_ref: null,
  before: SOURCE_A,
  commits: [
    {
      added: ["prereg/PREREG_SWM0W_S2S_GATE_V1.json"],
      distinct: true,
      id: REGISTRATION_B,
      message: "register future measurement"
    }
  ],
  compare: `https://github.com/gj3447/HSWM/compare/${SOURCE_A}...${REGISTRATION_B}`,
  created: false,
  deleted: false,
  forced: false,
  head_commit: {
    id: REGISTRATION_B,
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

const eventBytes = (value: unknown = eventFixture()): Uint8Array =>
  UTF8_ENCODER.encode(JSON.stringify(value))

const validEvidence = () => {
  const outcome = validateS2SCurrentInvocation(
    environmentFixture(),
    eventBytes(),
    1_700_000_000
  )
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

it("binds one exact first-attempt registration push and current job", () => {
  const evidence = validEvidence()
  expect(evidence).toMatchObject({
    schemaVersion: S2S_CURRENT_INVOCATION_EVIDENCE_SCHEMA_VERSION,
    pushBeforeSha: SOURCE_A,
    pushAfterSha: REGISTRATION_B,
    workflowRunId: RUN_ID,
    workflowRunAttempt: 1,
    jobId: "confirm",
    stage: "CONFIRM",
    workflowPath: ".github/workflows/swm0w-s2s-confirmatory.yml",
    capturedAtUnixSeconds: 1_700_000_000
  })
  expect(evidence.environmentProjection).toMatchObject({
    githubActions: true,
    eventName: "push",
    jobId: "confirm",
    ref: "refs/heads/main",
    repository: "gj3447/HSWM",
    runAttempt: 1,
    runId: RUN_ID,
    commitSha: REGISTRATION_B,
    workflowSourceCommitSha: REGISTRATION_B,
    runnerArch: "X64",
    runnerEnvironment: "github-hosted",
    runnerOs: "Linux"
  })
  expect(evidence.eventProjection).toEqual({
    ref: "refs/heads/main",
    before: SOURCE_A,
    after: REGISTRATION_B,
    created: false,
    deleted: false,
    forced: false,
    baseRef: null,
    repository: "gj3447/HSWM",
    repositoryFork: false,
    repositoryDefaultBranch: "main",
    commitIds: [REGISTRATION_B],
    headCommitId: REGISTRATION_B
  })
  const contractHash = s2sConfirmatoryWorkflowContractSha256()
  expect(Either.isRight(contractHash)).toBe(true)
  if (Either.isRight(contractHash)) {
    expect(evidence.workflowContractSha256).toBe(contractHash.right)
  }
  const { receiptSha256, ...core } = evidence
  const independent = canonicalS2SControlSha256(core)
  expect(Either.isRight(independent)).toBe(true)
  if (Either.isRight(independent)) {
    expect(receiptSha256).toBe(independent.right)
  }
  expect(evidence.environmentProjectionSha256).toBe(
    "f196682960f5cfead7bcbe3cb13f20e130a387b2ddae390ef63059784280205e"
  )
  expect(evidence.eventBodySha256).toBe(
    "7f38bb7246cb0358345d10ad76e052ad24bcec0a79c5dd0a5a86e95395dcbbcb"
  )
  expect(evidence.eventProjectionSha256).toBe(
    "4bab7836a7a8b31465b233973636538851a58bd0703752df9191f5ed144140c2"
  )
  expect(evidence.receiptSha256).toBe(
    "08ea8dc16d5843947fab1488f4273f60d5bb38747460af5c0c38ea978426e5d6"
  )
  expect(Object.isFrozen(evidence)).toBe(true)
  expect(Object.isFrozen(evidence.environmentProjection)).toBe(true)
  expect(Object.isFrozen(evidence.eventProjection)).toBe(true)
  expect(Object.isFrozen(evidence.eventProjection.commitIds)).toBe(true)
  expect(Object.isFrozen(S2S_CONFIRMATORY_WORKFLOW_CONTRACT)).toBe(true)
})

it("hash-binds nonprojected push fields without trusting them as identity", () => {
  const first = validEvidence()
  const changedEvent = eventFixture()
  changedEvent["sender"] = { login: "different-fixture" }
  const second = validateS2SCurrentInvocation(
    environmentFixture(),
    eventBytes(changedEvent),
    1_700_000_000
  )
  expect(Either.isRight(second)).toBe(true)
  if (Either.isRight(second)) {
    expect(second.right.eventProjection).toEqual(first.eventProjection)
    expect(second.right.eventBodySha256).not.toBe(first.eventBodySha256)
    expect(second.right.receiptSha256).not.toBe(first.receiptSha256)
  }
})

it("maps all three exact job IDs without accepting a display-name variant", () => {
  for (const [jobId, stage] of [
    ["register", "REGISTER"],
    ["confirm", "CONFIRM"],
    ["adjudicate", "ADJUDICATE"]
  ] as const) {
    const environment = environmentFixture()
    environment["GITHUB_JOB"] = jobId
    const outcome = validateS2SCurrentInvocation(
      environment,
      eventBytes(),
      1_700_000_000
    )
    expect(Either.isRight(outcome)).toBe(true)
    if (Either.isRight(outcome)) expect(outcome.right.stage).toBe(stage)
  }
  const displayName = environmentFixture()
  displayName["GITHUB_JOB"] = "Confirm"
  expect(
    Either.isLeft(
      validateS2SCurrentInvocation(
        displayName,
        eventBytes(),
        1_700_000_000
      )
    )
  ).toBe(true)
})

it("rejects missing, extra, accessor-backed, symbolic, and hostile environments", () => {
  const missing = environmentFixture()
  delete missing["GITHUB_WORKFLOW_SHA"]
  const extra = { ...environmentFixture(), UNEXPECTED: "value" }
  const accessor = environmentFixture()
  Object.defineProperty(accessor, "GITHUB_SHA", {
    enumerable: true,
    get: () => REGISTRATION_B
  })
  const symbolic = environmentFixture()
  Object.defineProperty(symbolic, Symbol("hidden"), {
    enumerable: true,
    value: "value"
  })
  const hostile = new Proxy(environmentFixture(), {
    ownKeys: () => {
      throw new Error("hostile ownKeys")
    }
  })
  for (const input of [missing, extra, accessor, symbolic, hostile]) {
    const outcome = validateS2SCurrentInvocation(
      input,
      eventBytes(),
      1_700_000_000
    )
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("ENVIRONMENT_REJECTED")
    }
  }
})

it("rejects workflow, event, ref, runner, job, attempt, and SHA drift", () => {
  const mutations: ReadonlyArray<readonly [string, unknown]> = [
    ["GITHUB_ACTIONS", "false"],
    ["GITHUB_API_URL", "https://example.invalid"],
    ["GITHUB_EVENT_NAME", "workflow_dispatch"],
    ["GITHUB_JOB", "finalize"],
    ["GITHUB_REF", "refs/pull/1/merge"],
    ["GITHUB_REF_NAME", "1/merge"],
    ["GITHUB_REF_TYPE", "tag"],
    ["GITHUB_REPOSITORY", "attacker/fork"],
    ["GITHUB_RUN_ATTEMPT", "2"],
    ["GITHUB_RUN_ID", "01"],
    ["GITHUB_RUN_ID", "9999999999999999"],
    ["GITHUB_SERVER_URL", "https://example.invalid"],
    ["GITHUB_SHA", "c".repeat(40)],
    ["GITHUB_WORKFLOW", "lookalike"],
    ["GITHUB_WORKFLOW_REF", "gj3447/HSWM/.github/workflows/other.yml@main"],
    ["GITHUB_WORKFLOW_SHA", "c".repeat(40)],
    ["RUNNER_ARCH", "ARM64"],
    ["RUNNER_ENVIRONMENT", "self-hosted"],
    ["RUNNER_OS", "Windows"]
  ]
  expect(S2S_CURRENT_INVOCATION_ENVIRONMENT_KEYS).toHaveLength(18)
  for (const [key, value] of mutations) {
    const environment = environmentFixture()
    environment[key] = value
    expect(
      Either.isLeft(
        validateS2SCurrentInvocation(
          environment,
          eventBytes(),
          1_700_000_000
        )
      )
    ).toBe(true)
  }
})

it("rejects a noncanonical capture timestamp", () => {
  for (const timestamp of [-1, 0.5, Number.NaN, "1700000000", undefined]) {
    const outcome = validateS2SCurrentInvocation(
      environmentFixture(),
      eventBytes(),
      timestamp
    )
    expect(Either.isLeft(outcome)).toBe(true)
  }
})

it("rejects fork, force, creation, deletion, multi-commit, and lineage drift", () => {
  const mutate = (
    apply: (event: Record<string, unknown>) => void
  ): boolean => {
    const event = eventFixture()
    apply(event)
    return Either.isLeft(
      validateS2SCurrentInvocation(
        environmentFixture(),
        eventBytes(event),
        1_700_000_000
      )
    )
  }
  expect(mutate((event) => (event["ref"] = "refs/heads/other"))).toBe(true)
  expect(mutate((event) => (event["before"] = REGISTRATION_B))).toBe(true)
  expect(mutate((event) => (event["after"] = "c".repeat(40)))).toBe(true)
  expect(mutate((event) => (event["created"] = true))).toBe(true)
  expect(mutate((event) => (event["deleted"] = true))).toBe(true)
  expect(mutate((event) => (event["forced"] = true))).toBe(true)
  expect(mutate((event) => (event["base_ref"] = "refs/heads/other"))).toBe(
    true
  )
  expect(
    mutate((event) => {
      const repository = event["repository"] as Record<string, unknown>
      repository["fork"] = true
    })
  ).toBe(true)
  expect(
    mutate((event) => {
      const commits = event["commits"] as Array<Record<string, unknown>>
      commits.push({ distinct: true, id: "c".repeat(40) })
    })
  ).toBe(true)
  expect(
    mutate((event) => {
      const commit = (event["commits"] as Array<Record<string, unknown>>)[0]
      if (commit !== undefined) commit["distinct"] = false
    })
  ).toBe(true)
  expect(
    mutate((event) => {
      const head = event["head_commit"] as Record<string, unknown>
      head["id"] = "c".repeat(40)
    })
  ).toBe(true)
})

it("rejects duplicate-key, fractional, oversized, subclassed, and shared bytes", () => {
  const duplicate = UTF8_ENCODER.encode(
    `{"after":"${REGISTRATION_B}","after":"${REGISTRATION_B}"}`
  )
  const fractional = UTF8_ENCODER.encode(
    JSON.stringify(eventFixture()).replace('"created":false', '"created":0.5')
  )
  class BytesSubclass extends Uint8Array {}
  const candidates: ReadonlyArray<unknown> = [
    duplicate,
    fractional,
    new Uint8Array(S2S_CURRENT_INVOCATION_EVENT_MAX_BYTES + 1),
    new BytesSubclass(eventBytes())
  ]
  for (const candidate of candidates) {
    expect(
      Either.isLeft(
        validateS2SCurrentInvocation(
          environmentFixture(),
          candidate,
          1_700_000_000
        )
      )
    ).toBe(true)
  }
  if (typeof SharedArrayBuffer !== "undefined") {
    const shared = new Uint8Array(new SharedArrayBuffer(128))
    expect(
      Either.isLeft(
        validateS2SCurrentInvocation(
          environmentFixture(),
          shared,
          1_700_000_000
        )
      )
    ).toBe(true)
  }
})

it.effect("issues only module-authentic process-local invocation authority", () =>
  Effect.gen(function* () {
    const service = yield* S2SCurrentInvocation
    const evidence = inspectS2SCurrentInvocationAuthority(service.authority)
    expect(Either.isRight(evidence)).toBe(true)
    if (Either.isRight(evidence)) {
      expect(evidence.right.pushAfterSha).toBe(REGISTRATION_B)
      expect(evidence.right.stage).toBe("CONFIRM")
    }
    const firstBytes = readS2SCurrentInvocationEventBytes(service.authority)
    expect(Either.isRight(firstBytes)).toBe(true)
    if (Either.isRight(firstBytes)) firstBytes.right.fill(0)
    const secondBytes = readS2SCurrentInvocationEventBytes(service.authority)
    expect(Either.isRight(secondBytes)).toBe(true)
    if (Either.isRight(secondBytes)) {
      expect(secondBytes.right).toEqual(eventBytes())
    }
    const plainForgery = inspectS2SCurrentInvocationAuthority({
      _tag: "CurrentInvocation"
    })
    const proxyForgery = inspectS2SCurrentInvocationAuthority(
      new Proxy(
        {},
        {
          getPrototypeOf: () => {
            throw new Error("hostile prototype")
          }
        }
      )
    )
    expect(Either.isLeft(plainForgery)).toBe(true)
    expect(Either.isLeft(proxyForgery)).toBe(true)
    expect(Either.isLeft(readS2SCurrentInvocationEventBytes({}))).toBe(true)
  }).pipe(
    Effect.provide(
      makeS2SCurrentInvocationTestLayer(
        environmentFixture(),
        eventBytes(),
        1_700_000_000
      )
    )
  )
)

const stubLiveEnvironment = (eventPath: string): void => {
  for (const [key, value] of Object.entries(environmentFixture())) {
    vi.stubEnv(key, String(value))
  }
  vi.stubEnv("GITHUB_EVENT_PATH", eventPath)
}

it.effect("live capture reads one regular no-follow bounded event file", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-s2s-invocation-"))
  const path = join(root, "event.json")
  writeFileSync(path, eventBytes())
  stubLiveEnvironment(path)
  return Effect.gen(function* () {
    const service = yield* S2SCurrentInvocation
    const evidence = inspectS2SCurrentInvocationAuthority(service.authority)
    expect(Either.isRight(evidence)).toBe(true)
    if (Either.isRight(evidence)) {
      expect(evidence.right.eventBodyByteLength).toBe(eventBytes().byteLength)
    }
  }).pipe(
    Effect.provide(S2SCurrentInvocationLive),
    Effect.ensuring(
      Effect.sync(() => {
        vi.unstubAllEnvs()
        rmSync(root, { force: true, recursive: true })
      })
    )
  )
})

it.effect("live capture rejects a symlinked event source", () => {
  const root = mkdtempSync(join(tmpdir(), "hswm-s2s-invocation-link-"))
  const target = join(root, "target.json")
  const link = join(root, "event.json")
  writeFileSync(target, eventBytes())
  symlinkSync(target, link)
  stubLiveEnvironment(link)
  return Effect.gen(function* () {
    const outcome = yield* Effect.serviceOption(S2SCurrentInvocation).pipe(
      Effect.provide(S2SCurrentInvocationLive),
      Effect.either
    )
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({ reason: "EVENT_FILE_OPEN_FAILED" })
    }
  }).pipe(
    Effect.ensuring(
      Effect.sync(() => {
        vi.unstubAllEnvs()
        rmSync(root, { force: true, recursive: true })
      })
    )
  )
})
