import { execFileSync } from "node:child_process"
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync
} from "node:fs"
import { dirname, join, resolve } from "node:path"
import { tmpdir } from "node:os"

import { expect, it } from "@effect/vitest"
import { Deferred, Effect, Either, Fiber, TestClock } from "effect"

import {
  S2S_PREREG_GIT_COMMAND_TIMEOUT_MILLIS,
  S2S_PREREG_NUMERIC_PATHS,
  S2S_PREREG_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PREREG_PILOT_SOURCE_COMMIT,
  S2S_PREREG_PROTOCOL_CONFIG_SHA256,
  S2S_PREREG_RESOURCE_POLICY_SHA256,
  S2S_PREREGISTRATION_PATH,
  buildS2SPreregistration,
  buildS2STrackedBytesManifest,
  makeS2SPreregGitRepositoryProcessLayer,
  makeS2SPreregGitRepositoryTestLayer,
  parseAndValidateS2SPreregistration,
  s2sPreregCanonicalJson,
  s2sPreregCanonicalSha256,
  s2sPreregSha256Bytes,
  validateS2SRegistrationCommitB,
  verifyS2SNumericContinuity,
  type BuiltS2SPreregistration
} from "../src/s2s-preregistration.js"

const WORKSPACE_ROOT = resolve(process.cwd(), "../../..")
const UTF8_ENCODER = new TextEncoder()
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true })
const GIT_MAX_BUFFER = 32 * 1_048_576

interface GitFixture {
  readonly root: string
  readonly sourceCommitA: string
  readonly cleanup: () => void
}

const runGit = (root: string, arguments_: ReadonlyArray<string>): string =>
  execFileSync("git", ["-C", root, ...arguments_], {
    encoding: "utf8",
    maxBuffer: GIT_MAX_BUFFER
  }).trim()

const makeGitFixture = (numericDrift = false): GitFixture => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-prereg-"))
  const root = join(temporaryRoot, "repository")
  execFileSync(
    "git",
    ["clone", "--shared", "--no-checkout", "--quiet", WORKSPACE_ROOT, root],
    { maxBuffer: GIT_MAX_BUFFER }
  )
  runGit(root, ["config", "user.email", "s2s-prereg-test@example.invalid"])
  runGit(root, ["config", "user.name", "S2S prereg test"])
  runGit(root, ["checkout", "--quiet", "-b", "source-a", S2S_PREREG_PILOT_SOURCE_COMMIT])
  if (numericDrift) {
    const numericPath = join(root, S2S_PREREG_NUMERIC_PATHS[1])
    writeFileSync(
      numericPath,
      `${readFileSync(numericPath, "utf8")}\n# adversarial numeric drift\n`,
      "utf8"
    )
    runGit(root, ["add", "--", S2S_PREREG_NUMERIC_PATHS[1]])
  } else {
    writeFileSync(join(root, "s2s-control-fixture.txt"), "source A\n", "utf8")
    runGit(root, ["add", "--", "s2s-control-fixture.txt"])
  }
  runGit(root, ["commit", "--quiet", "-m", "create source A fixture"])
  const sourceCommitA = runGit(root, ["rev-parse", "HEAD"])
  return {
    root,
    sourceCommitA,
    cleanup: () => rmSync(temporaryRoot, { force: true, recursive: true })
  }
}

const buildInput = (sourceCommitA: string) => ({
  experimentId: "SWM0W-S2S-GATE-V1",
  resourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256,
  sourceCommitA,
  registeredAtUnix: 1_692_806_000,
  futureRound: 1_000
})

const encodeCanonicalDocument = (value: unknown): Uint8Array => {
  const encoded = s2sPreregCanonicalJson(value)
  if (Either.isLeft(encoded)) throw encoded.left
  return UTF8_ENCODER.encode(`${encoded.right}\n`)
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)

const decodeObject = (bytes: Uint8Array): Record<string, unknown> => {
  const value: unknown = JSON.parse(UTF8_DECODER.decode(bytes))
  if (!isRecord(value)) {
    throw new Error("expected a JSON object")
  }
  return value
}

const writeRegistration = (
  fixture: GitFixture,
  branch: string,
  bytes: Uint8Array,
  extraPath: string | null = null
): string => {
  runGit(fixture.root, [
    "checkout",
    "--quiet",
    "-B",
    branch,
    fixture.sourceCommitA
  ])
  const preregistrationPath = join(fixture.root, S2S_PREREGISTRATION_PATH)
  mkdirSync(dirname(preregistrationPath), { recursive: true })
  writeFileSync(preregistrationPath, bytes)
  runGit(fixture.root, ["add", "--", S2S_PREREGISTRATION_PATH])
  if (extraPath !== null) {
    writeFileSync(join(fixture.root, extraPath), "unexpected\n", "utf8")
    runGit(fixture.root, ["add", "--", extraPath])
  }
  runGit(fixture.root, ["commit", "--quiet", "-m", `create ${branch}`])
  return runGit(fixture.root, ["rev-parse", "HEAD"])
}

it("canonicalizes UTF-8 prereg values and rejects non-canonical JS values", () => {
  const canonical = s2sPreregCanonicalJson({ b: 2, a: "한글" })
  expect(Either.isRight(canonical)).toBe(true)
  if (Either.isRight(canonical)) {
    expect(canonical.right).toBe('{"a":"한글","b":2}')
  }
  const digest = s2sPreregCanonicalSha256({ b: 2, a: "한글" })
  expect(Either.isRight(digest)).toBe(true)
  if (Either.isRight(digest)) {
    expect(digest.right).toBe(
      "d6ad94428fb66348c062045f84283b49c816b309fa21aa928f1b6a03168822e1"
    )
  }
  const prototypeKey: unknown = JSON.parse('{"__proto__":{"safe":1},"a":2}')
  const prototypeCanonical = s2sPreregCanonicalJson(prototypeKey)
  expect(Either.isRight(prototypeCanonical)).toBe(true)
  if (Either.isRight(prototypeCanonical)) {
    expect(prototypeCanonical.right).toBe(
      '{"__proto__":{"safe":1},"a":2}'
    )
  }

  const cycle: Record<string, unknown> = {}
  cycle["self"] = cycle
  const accessor = [1]
  Object.defineProperty(accessor, "0", {
    configurable: true,
    enumerable: true,
    get: () => 1
  })
  const customArray = [1]
  Object.defineProperty(customArray, "extra", {
    configurable: true,
    enumerable: false,
    value: 2
  })
  const rejected: ReadonlyArray<unknown> = [
    0.5,
    -0,
    Number.NaN,
    undefined,
    "\ud800",
    cycle,
    Array(1),
    accessor,
    customArray
  ]
  expect(rejected.every((value) => Either.isLeft(s2sPreregCanonicalJson(value)))).toBe(
    true
  )
})

it.effect(
  "builds, strictly parses, and validates a direct-child add-only preregistration",
  () => {
    const fixture = makeGitFixture()
    const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
    return Effect.gen(function* () {
      const built = yield* buildS2SPreregistration(
        buildInput(fixture.sourceCommitA)
      )
      const preregistration = built.preregistration
      expect(
        preregistration.registration_core.evidence_binding
          .pilot_adoption_receipt_sha256
      ).toBe(S2S_PREREG_PILOT_ADOPTION_RECEIPT_SHA256)
      expect(
        preregistration.registration_core.evidence_binding.protocol_config_sha256
      ).toBe(S2S_PREREG_PROTOCOL_CONFIG_SHA256)
      expect(
        preregistration.registration_core.evidence_binding.resource_policy_sha256
      ).toBe(S2S_PREREG_RESOURCE_POLICY_SHA256)
      expect(
        preregistration.future_round_commitment.registration_evidence_sha256
      ).toBe(preregistration.registration_core_sha256)
      expect(preregistration.future_round_commitment.round_time_unix).toBe(
        1_692_806_364
      )
      expect(built.canonicalBytes.at(-1)).toBe(10)
      expect(built.fileSha256).toBe(s2sPreregSha256Bytes(built.canonicalBytes))

      const fixtureRow = preregistration.registration_core.source_freeze
        .tracked_bytes_manifest.rows.find(
          (row) => row.path === "s2s-control-fixture.txt"
        )
      expect(fixtureRow).toEqual({
        mode: "100644",
        object_type: "blob",
        path: "s2s-control-fixture.txt",
        sha256: s2sPreregSha256Bytes(UTF8_ENCODER.encode("source A\n"))
      })

      const validated = yield* parseAndValidateS2SPreregistration(
        built.canonicalBytes,
        { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
      )
      expect(validated.fileSha256).toBe(built.fileSha256)

      const registrationCommitB = writeRegistration(
        fixture,
        "registration-valid",
        built.canonicalBytes
      )
      expect(
        yield* validateS2SRegistrationCommitB(validated, registrationCommitB)
      ).toBe(registrationCommitB)

      const childCommit = runGit(fixture.root, [
        "commit",
        "--allow-empty",
        "--quiet",
        "-m",
        "not registration B"
      ])
      expect(childCommit).toBe("")
      const registrationCommitC = runGit(fixture.root, ["rev-parse", "HEAD"])
      const notDirect = yield* validateS2SRegistrationCommitB(
        validated,
        registrationCommitC
      ).pipe(Effect.either)
      expect(Either.isLeft(notDirect)).toBe(true)
      if (Either.isLeft(notDirect)) {
        expect(notDirect.left).toMatchObject({ reason: "NOT_DIRECT_CHILD" })
      }

      const extraCommit = writeRegistration(
        fixture,
        "registration-extra",
        built.canonicalBytes,
        "unexpected-registration-file.txt"
      )
      const extra = yield* validateS2SRegistrationCommitB(
        validated,
        extraCommit
      ).pipe(Effect.either)
      expect(Either.isLeft(extra)).toBe(true)
      if (Either.isLeft(extra)) {
        expect(extra.left).toMatchObject({
          reason: "DIFF_NOT_ADD_ONLY_PREREGISTRATION"
        })
      }

      const driftedBytes = new Uint8Array([
        ...built.canonicalBytes.slice(0, -1),
        32,
        10
      ])
      const driftCommit = writeRegistration(
        fixture,
        "registration-drift",
        driftedBytes
      )
      const drift = yield* validateS2SRegistrationCommitB(
        validated,
        driftCommit
      ).pipe(Effect.either)
      expect(Either.isLeft(drift)).toBe(true)
      if (Either.isLeft(drift)) {
        expect(drift.left).toMatchObject({
          reason: "PREREGISTRATION_BYTES_DRIFT"
        })
      }

      yield* assertStrictParserRejections(built)
    }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
  }
)

const assertStrictParserRejections = (
  built: BuiltS2SPreregistration
) =>
  Effect.gen(function* () {
    const excessRoot = decodeObject(built.canonicalBytes)
    excessRoot["unexpected"] = true
    const excess = yield* parseAndValidateS2SPreregistration(
      encodeCanonicalDocument(excessRoot),
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    ).pipe(Effect.either)
    expect(Either.isLeft(excess)).toBe(true)
    if (Either.isLeft(excess)) {
      expect(excess.left).toMatchObject({ reason: "SCHEMA_MISMATCH" })
    }

    const nestedExcessRoot = decodeObject(built.canonicalBytes)
    const registrationCore = nestedExcessRoot["registration_core"]
    if (!isRecord(registrationCore)) throw new Error("registration core missing")
    registrationCore["unexpected"] = true
    const nestedExcess = yield* parseAndValidateS2SPreregistration(
      encodeCanonicalDocument(nestedExcessRoot),
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    ).pipe(Effect.either)
    expect(Either.isLeft(nestedExcess)).toBe(true)
    if (Either.isLeft(nestedExcess)) {
      expect(nestedExcess.left).toMatchObject({ reason: "SCHEMA_MISMATCH" })
    }

    const tamperedRoot = decodeObject(built.canonicalBytes)
    tamperedRoot["preregistration_sha256"] = "0".repeat(64)
    const tampered = yield* parseAndValidateS2SPreregistration(
      encodeCanonicalDocument(tamperedRoot),
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    ).pipe(Effect.either)
    expect(Either.isLeft(tampered)).toBe(true)
    if (Either.isLeft(tampered)) {
      expect(tampered.left).toMatchObject({ reason: "HASH_MISMATCH" })
    }

    const text = UTF8_DECODER.decode(built.canonicalBytes)
    const duplicate = UTF8_ENCODER.encode(
      text.replace(/^\{/, '{"future_round_commitment":null,')
    )
    const duplicateResult = yield* parseAndValidateS2SPreregistration(
      duplicate,
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    ).pipe(Effect.either)
    expect(Either.isLeft(duplicateResult)).toBe(true)
    if (Either.isLeft(duplicateResult)) {
      expect(duplicateResult.left).toMatchObject({
        reason: "INVALID_CANONICAL_JSON"
      })
    }

    const wrongPolicy = yield* parseAndValidateS2SPreregistration(
      built.canonicalBytes,
      { expectedResourcePolicySha256: "0".repeat(64) }
    ).pipe(Effect.either)
    expect(Either.isLeft(wrongPolicy)).toBe(true)
    if (Either.isLeft(wrongPolicy)) {
      expect(wrongPolicy.left).toMatchObject({ reason: "INVALID_INPUT" })
    }
  })

it.effect("rejects P-to-A numeric byte drift before preregistration emission", () => {
  const fixture = makeGitFixture(true)
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const continuity = yield* verifyS2SNumericContinuity(
      fixture.sourceCommitA
    ).pipe(Effect.either)
    expect(Either.isLeft(continuity)).toBe(true)
    if (Either.isLeft(continuity)) {
      expect(continuity.left).toMatchObject({ reason: "NUMERIC_BYTES_DRIFT" })
    }

    const preregistration = yield* buildS2SPreregistration(
      buildInput(fixture.sourceCommitA)
    ).pipe(Effect.either)
    expect(Either.isLeft(preregistration)).toBe(true)
    if (Either.isLeft(preregistration)) {
      expect(preregistration.left).toMatchObject({ reason: "NUMERIC_BYTES_DRIFT" })
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("rejects a caller-injected structural source freeze at the build boundary", () => {
  let calls = 0
  const layer = makeS2SPreregGitRepositoryTestLayer(() => {
    calls += 1
    return Effect.die("Git must not be called for an invalid build input")
  })
  const forgedInput: unknown = {
    experimentId: "SWM0W-S2S-GATE-V1",
    resourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256,
    sourceFreeze: {
      schema_version: "hswm-swm0w-s2s-source-freeze/v1"
    },
    registeredAtUnix: 1_692_806_000,
    futureRound: 1_000
  }
  return Effect.gen(function* () {
    const result = yield* buildS2SPreregistration(forgedInput).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "INVALID_INPUT" })
    }
    expect(calls).toBe(0)
  }).pipe(Effect.provide(layer))
})

it.effect("times out and cancels a stalled Git test Layer", () =>
  Effect.gen(function* () {
    const started = yield* Deferred.make<void>()
    let interrupted = false
    const layer = makeS2SPreregGitRepositoryTestLayer(() =>
      Deferred.succeed(started, undefined).pipe(
        Effect.zipRight(Effect.never),
        Effect.onInterrupt(() =>
          Effect.sync(() => {
            interrupted = true
          })
        )
      )
    )
    const fiber = yield* buildS2STrackedBytesManifest(
      S2S_PREREG_PILOT_SOURCE_COMMIT
    ).pipe(Effect.provide(layer), Effect.either, Effect.fork)
    yield* Deferred.await(started)
    yield* TestClock.adjust(S2S_PREREG_GIT_COMMAND_TIMEOUT_MILLIS + 1)
    const result = yield* Fiber.join(fiber)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "COMMAND_TIMED_OUT" })
    }
    expect(interrupted).toBe(true)
  })
)

it.effect("maps malformed Git test-Layer output to a typed source-freeze error", () => {
  const layer = makeS2SPreregGitRepositoryTestLayer(() =>
    Effect.succeed({
      exitCode: 0,
      stdout: UTF8_ENCODER.encode("not-a-git-object\n"),
      stderr: new Uint8Array()
    })
  )
  return Effect.gen(function* () {
    const result = yield* buildS2STrackedBytesManifest(
      S2S_PREREG_PILOT_SOURCE_COMMIT
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "MALFORMED_GIT_OUTPUT" })
    }
  }).pipe(Effect.provide(layer))
})
