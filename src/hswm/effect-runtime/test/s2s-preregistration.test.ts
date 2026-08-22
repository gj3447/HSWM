import { execFileSync } from "node:child_process"
import {
  chmodSync,
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
import { vi } from "vitest"

import {
  S2S_PREREG_ANCESTRY_MAX_COMMITS,
  S2S_PREREG_GIT_COMMAND_TIMEOUT_MILLIS,
  S2S_PREREG_NUMERIC_PATHS,
  S2S_PREREG_PILOT_ADOPTION_RECEIPT_SHA256,
  S2S_PREREG_PILOT_SOURCE_COMMIT,
  S2S_PREREG_PROTOCOL_CONFIG_SHA256,
  S2S_PREREG_RESOURCE_POLICY_SHA256,
  S2S_PREREGISTRATION_PATH,
  S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE_SCHEMA_VERSION,
  buildS2SPreregistration,
  buildS2STrackedBytesManifest,
  makeS2SPreregGitRepositoryProcessLayer,
  makeS2SPreregGitRepositoryTestLayer,
  parseAndValidateS2SPreregistration,
  inspectS2SRegistrationCommitAuthority,
  inspectS2SRegistrationWorkflowManifestBinding,
  s2sPreregCanonicalJson,
  s2sPreregCanonicalSha256,
  s2sPreregSha256Bytes,
  validateS2SRegistrationCommitB,
  verifyS2SNumericContinuity,
  type BuiltS2SPreregistration,
  type S2SGitCommand,
  type S2SGitCommandResult
} from "../src/s2s-preregistration.js"
import { S2S_CONFIRMATORY_WORKFLOW_PATH } from "../src/s2s-workflow-contract.js"

const WORKSPACE_ROOT = resolve(process.cwd(), "../../..")
const UTF8_ENCODER = new TextEncoder()
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true })
const GIT_MAX_BUFFER = 32 * 1_048_576
const GIT_COMMAND_MAX_BUFFER = 129 * 1_048_576
const WORKFLOW_FIXTURE_BYTES = UTF8_ENCODER.encode(
  "name: SWM-0W-S2S confirmatory\n"
)

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

const makeGitFixture = (
  numericDrift = false,
  workflowMode: "100644" | "100755" | "absent" = "100644"
): GitFixture => {
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
  if (workflowMode !== "absent") {
    const workflowPath = join(root, S2S_CONFIRMATORY_WORKFLOW_PATH)
    mkdirSync(dirname(workflowPath), { recursive: true })
    writeFileSync(workflowPath, WORKFLOW_FIXTURE_BYTES)
    if (workflowMode === "100755") chmodSync(workflowPath, 0o755)
    runGit(root, ["add", "--", S2S_CONFIRMATORY_WORKFLOW_PATH])
  }
  runGit(root, ["commit", "--quiet", "-m", "create source A fixture"])
  const sourceCommitA = runGit(root, ["rev-parse", "HEAD"])
  return {
    root,
    sourceCommitA,
    cleanup: () => rmSync(temporaryRoot, { force: true, recursive: true })
  }
}

const makeIsolatedGitFixture = (): GitFixture => {
  const temporaryRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-git-decoy-"))
  const root = join(temporaryRoot, "repository")
  mkdirSync(root)
  runGit(root, ["init", "--quiet"])
  runGit(root, ["config", "user.email", "s2s-decoy@example.invalid"])
  runGit(root, ["config", "user.name", "S2S decoy repository"])
  runGit(root, ["commit", "--allow-empty", "--quiet", "-m", "decoy root"])
  return {
    root,
    sourceCommitA: runGit(root, ["rev-parse", "HEAD"]),
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

const requiredRecord = (
  parent: Record<string, unknown>,
  key: string
): Record<string, unknown> => {
  const value = parent[key]
  if (!isRecord(value)) throw new Error(`expected object at ${key}`)
  return value
}

const canonicalShaOrThrow = (value: unknown): string => {
  const digest = s2sPreregCanonicalSha256(value)
  if (Either.isLeft(digest)) throw digest.left
  return digest.right
}

const selfHash = (
  value: Record<string, unknown>,
  hashField: string
): string => {
  const unsigned: Record<string, unknown> = {}
  for (const [key, item] of Object.entries(value)) {
    if (key !== hashField) unsigned[key] = item
  }
  return canonicalShaOrThrow(unsigned)
}

const rehashPreregistrationDocument = (
  root: Record<string, unknown>
): void => {
  const core = requiredRecord(root, "registration_core")
  const sourceFreeze = requiredRecord(core, "source_freeze")
  const manifest = requiredRecord(sourceFreeze, "tracked_bytes_manifest")
  const futureRound = requiredRecord(root, "future_round_commitment")
  manifest["manifest_sha256"] = selfHash(manifest, "manifest_sha256")
  sourceFreeze["receipt_sha256"] = selfHash(sourceFreeze, "receipt_sha256")
  const coreSha256 = canonicalShaOrThrow(core)
  root["registration_core_sha256"] = coreSha256
  futureRound["registration_evidence_sha256"] = coreSha256
  futureRound["commitment_sha256"] = selfHash(
    futureRound,
    "commitment_sha256"
  )
  root["preregistration_sha256"] = selfHash(
    root,
    "preregistration_sha256"
  )
}

const executeGitCommand = (
  root: string,
  command: S2SGitCommand
): S2SGitCommandResult => {
  const stdout =
    command.stdin === null
      ? execFileSync("git", ["-C", root, ...command.arguments], {
          maxBuffer: GIT_COMMAND_MAX_BUFFER
        })
      : execFileSync("git", ["-C", root, ...command.arguments], {
          input: command.stdin,
          maxBuffer: GIT_COMMAND_MAX_BUFFER
        })
  return {
    exitCode: 0,
    stdout: new Uint8Array(stdout),
    stderr: new Uint8Array()
  }
}

const encodeRawCommitBatch = (
  oid: string,
  parents: ReadonlyArray<string>
): Uint8Array => {
  const parentHeaders = parents.map((parent) => `parent ${parent}\n`).join("")
  const payload = UTF8_ENCODER.encode(
    `tree ${"b".repeat(40)}\n${parentHeaders}` +
      "author Cycle Test <cycle@example.invalid> 1 +0000\n" +
      "committer Cycle Test <cycle@example.invalid> 1 +0000\n\n" +
      "synthetic commit\n"
  )
  return new Uint8Array([
    ...UTF8_ENCODER.encode(`${oid} commit ${payload.length}\n`),
    ...payload,
    10
  ])
}

const writeGraft = (
  fixture: GitFixture,
  commit: string,
  parents: ReadonlyArray<string>
): void => {
  const graftPath = join(fixture.root, ".git", "info", "grafts")
  mkdirSync(dirname(graftPath), { recursive: true })
  runGit(fixture.root, ["config", "advice.graftFileDeprecated", "false"])
  writeFileSync(graftPath, `${commit} ${parents.join(" ")}\n`, "utf8")
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

const writeRegistrationWithMode = (
  fixture: GitFixture,
  branch: string,
  bytes: Uint8Array,
  mode: "100755" | "120000" | "160000"
): string => {
  const preregistrationPath = join(fixture.root, S2S_PREREGISTRATION_PATH)
  rmSync(preregistrationPath, { force: true })
  runGit(fixture.root, [
    "checkout",
    "--quiet",
    "-B",
    branch,
    fixture.sourceCommitA
  ])
  mkdirSync(dirname(preregistrationPath), { recursive: true })
  writeFileSync(preregistrationPath, bytes)
  const objectId =
    mode === "160000"
      ? fixture.sourceCommitA
      : execFileSync(
          "git",
          ["-C", fixture.root, "hash-object", "-w", "--stdin"],
          { encoding: "utf8", input: bytes, maxBuffer: GIT_MAX_BUFFER }
        ).trim()
  runGit(fixture.root, [
    "update-index",
    "--add",
    "--cacheinfo",
    mode,
    objectId,
    S2S_PREREGISTRATION_PATH
  ])
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
      expect(S2S_PREREG_RESOURCE_POLICY_SHA256).toBe(
        "b2c631ff80922800d06ac7e31c0632e02e1b560a31759cd0d11ae0a39c374351"
      )
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
      const exposedRepositoryBinding =
        validated.preregistration.registration_core.repository_binding
      expect(Object.isFrozen(exposedRepositoryBinding)).toBe(true)
      expect(
        Reflect.set(
          exposedRepositoryBinding,
          "source_commit_a",
          "0".repeat(40)
        )
      ).toBe(false)
      expect(exposedRepositoryBinding.source_commit_a).toBe(fixture.sourceCommitA)

      const exposedBytes = validated.canonicalBytes
      exposedBytes.fill(0)
      expect(s2sPreregSha256Bytes(validated.canonicalBytes)).toBe(
        built.fileSha256
      )

      const registrationCommitB = writeRegistration(
        fixture,
        "registration-valid",
        built.canonicalBytes
      )
      const registrationAuthority = yield* validateS2SRegistrationCommitB(
        validated,
        registrationCommitB
      )
      expect(Object.isFrozen(registrationAuthority)).toBe(true)
      const registrationEvidence = inspectS2SRegistrationCommitAuthority(
        registrationAuthority
      )
      expect(Either.isRight(registrationEvidence)).toBe(true)
      if (Either.isRight(registrationEvidence)) {
        expect(registrationEvidence.right).toMatchObject({
          schemaVersion:
            S2S_REGISTRATION_COMMIT_AUTHORITY_EVIDENCE_SCHEMA_VERSION,
          sourceCommitA: fixture.sourceCommitA,
          registrationCommitB,
          preregistrationSha256: preregistration.preregistration_sha256,
          preregistrationFileSha256: built.fileSha256,
          registrationCoreSha256: preregistration.registration_core_sha256,
          resourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256,
          registeredAtUnixSeconds: 1_692_806_000,
          futureRound: 1_000
        })
        const { receiptSha256, ...evidenceCore } = registrationEvidence.right
        expect(canonicalShaOrThrow(evidenceCore)).toBe(receiptSha256)
      }
      const workflowBinding = inspectS2SRegistrationWorkflowManifestBinding(
        registrationAuthority
      )
      expect(Either.isRight(workflowBinding)).toBe(true)
      if (Either.isRight(workflowBinding)) {
        expect(workflowBinding.right).toEqual({
          workflowPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
          mode: "100644",
          objectType: "blob",
          workflowFileSha256: s2sPreregSha256Bytes(WORKFLOW_FIXTURE_BYTES),
          trackedBytesManifestSha256:
            preregistration.registration_core.source_freeze
              .tracked_bytes_manifest.manifest_sha256
        })
        expect(Object.isFrozen(workflowBinding.right)).toBe(true)
      }
      const hostileValidate = validateS2SRegistrationCommitB as unknown as (
        snapshot: typeof validated,
        registrationCommit: unknown
      ) => ReturnType<typeof validateS2SRegistrationCommitB>
      const hostileIdentity = yield* hostileValidate(
        validated,
        Symbol("registration-commit")
      ).pipe(Effect.either)
      expect(Either.isLeft(hostileIdentity)).toBe(true)
      if (Either.isLeft(hostileIdentity)) {
        expect(hostileIdentity.left).toMatchObject({ reason: "INVALID_COMMIT" })
      }

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

      const hashInvalidRoot = decodeObject(built.canonicalBytes)
      hashInvalidRoot["preregistration_sha256"] = "0".repeat(64)
      const hashInvalidCommit = writeRegistration(
        fixture,
        "registration-hash-invalid",
        encodeCanonicalDocument(hashInvalidRoot)
      )
      const hashInvalid = yield* validateS2SRegistrationCommitB(
        validated,
        hashInvalidCommit
      ).pipe(Effect.either)
      expect(Either.isLeft(hashInvalid)).toBe(true)
      if (Either.isLeft(hashInvalid)) {
        expect(hashInvalid.left).toMatchObject({
          reason: "PREREGISTRATION_BYTES_DRIFT"
        })
      }

      yield* assertStrictParserRejections(built)
    }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
  }
)

for (const workflowMode of ["absent", "100755"] as const) {
  it.effect(
    `withholds workflow manifest binding for ${workflowMode} source entry`,
    () => {
      const fixture = makeGitFixture(false, workflowMode)
      const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
      return Effect.gen(function* () {
        const built = yield* buildS2SPreregistration(
          buildInput(fixture.sourceCommitA)
        )
        const validated = yield* parseAndValidateS2SPreregistration(
          built.canonicalBytes,
          { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
        )
        const registrationCommitB = writeRegistration(
          fixture,
          `registration-workflow-${workflowMode}`,
          built.canonicalBytes
        )
        const authority = yield* validateS2SRegistrationCommitB(
          validated,
          registrationCommitB
        )
        const binding = inspectS2SRegistrationWorkflowManifestBinding(authority)
        expect(Either.isLeft(binding)).toBe(true)
        if (Either.isLeft(binding)) {
          expect(binding.left).toMatchObject({
            reason: "WORKFLOW_MANIFEST_BINDING_INVALID"
          })
        }
      }).pipe(
        Effect.provide(layer),
        Effect.ensuring(Effect.sync(fixture.cleanup))
      )
    }
  )
}

it.effect("rejects executable, symlink, and gitlink preregistration entries", () => {
  const fixture = makeGitFixture()
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const built = yield* buildS2SPreregistration(
      buildInput(fixture.sourceCommitA)
    )
    const validated = yield* parseAndValidateS2SPreregistration(
      built.canonicalBytes,
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    )
    for (const mode of ["100755", "120000", "160000"] as const) {
      const registrationCommitB = writeRegistrationWithMode(
        fixture,
        `registration-mode-${mode}`,
        built.canonicalBytes,
        mode
      )
      const outcome = yield* validateS2SRegistrationCommitB(
        validated,
        registrationCommitB
      ).pipe(Effect.either)
      expect(Either.isLeft(outcome)).toBe(true)
      if (Either.isLeft(outcome)) {
        expect(outcome.left).toMatchObject({
          reason: "PREREGISTRATION_ENTRY_INVALID"
        })
      }
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("rejects an annotated-tag object as source A", () => {
  const fixture = makeGitFixture()
  runGit(fixture.root, [
    "tag",
    "-a",
    "source-a-annotated",
    "-m",
    "annotated source A",
    fixture.sourceCommitA
  ])
  const annotatedTagOid = runGit(fixture.root, [
    "rev-parse",
    "refs/tags/source-a-annotated^{tag}"
  ])
  expect(runGit(fixture.root, ["cat-file", "-t", annotatedTagOid])).toBe("tag")
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const result = yield* buildS2SPreregistration(
      buildInput(annotatedTagOid)
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "INVALID_GIT_IDENTITY" })
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("ignores a replacement ref that maps an annotated tag to a commit", () => {
  const fixture = makeGitFixture()
  runGit(fixture.root, [
    "tag",
    "-a",
    "source-a-replaced",
    "-m",
    "replacement attack source A",
    fixture.sourceCommitA
  ])
  const annotatedTagOid = runGit(fixture.root, [
    "rev-parse",
    "refs/tags/source-a-replaced^{tag}"
  ])
  runGit(fixture.root, [
    "update-ref",
    `refs/replace/${annotatedTagOid}`,
    fixture.sourceCommitA
  ])
  expect(runGit(fixture.root, ["cat-file", "-t", annotatedTagOid])).toBe(
    "commit"
  )
  expect(
    runGit(fixture.root, [
      "--no-replace-objects",
      "cat-file",
      "-t",
      annotatedTagOid
    ])
  ).toBe("tag")
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const result = yield* buildS2SPreregistration(
      buildInput(annotatedTagOid)
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "INVALID_GIT_IDENTITY" })
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("ignores an inherited GIT_DIR that points at another repository", () => {
  const fixture = makeGitFixture()
  const decoy = makeIsolatedGitFixture()
  expect(decoy.sourceCommitA).not.toBe(fixture.sourceCommitA)
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  const restoreGitDir = (previous: string | undefined): void => {
    if (previous === undefined) {
      delete process.env["GIT_DIR"]
    } else {
      process.env["GIT_DIR"] = previous
    }
  }
  return Effect.acquireUseRelease(
    Effect.sync(() => {
      const previous = process.env["GIT_DIR"]
      process.env["GIT_DIR"] = join(decoy.root, ".git")
      return previous
    }),
    () =>
      Effect.gen(function* () {
        const built = yield* buildS2SPreregistration(
          buildInput(fixture.sourceCommitA)
        )
        expect(
          built.preregistration.registration_core.repository_binding
            .source_commit_a
        ).toBe(fixture.sourceCommitA)
        expect(
          built.preregistration.registration_core.source_freeze
            .tracked_bytes_manifest.commit
        ).toBe(fixture.sourceCommitA)
      }),
    (previous) => Effect.sync(() => restoreGitDir(previous))
  ).pipe(
    Effect.provide(layer),
    Effect.ensuring(
      Effect.sync(() => {
        fixture.cleanup()
        decoy.cleanup()
      })
    )
  )
})

it.effect("ignores a fake git executable injected ahead of the pinned PATH", () => {
  const fixture = makeGitFixture()
  const fakeBin = join(fixture.root, "fake-bin")
  const fakeGit = join(fakeBin, "git")
  mkdirSync(fakeBin)
  writeFileSync(fakeGit, "#!/bin/sh\nexit 97\n", "utf8")
  chmodSync(fakeGit, 0o755)
  return Effect.acquireUseRelease(
    Effect.sync(() => {
      const previous = process.env["PATH"]
      process.env["PATH"] = `${fakeBin}:/usr/bin:/bin`
      vi.resetModules()
      return previous
    }),
    () =>
      Effect.gen(function* () {
        const isolated = yield* Effect.promise(
          () => import("../src/s2s-preregistration.js")
        )
        const layer = isolated.makeS2SPreregGitRepositoryProcessLayer(
          fixture.root
        )
        const built = yield* isolated.buildS2SPreregistration(
          buildInput(fixture.sourceCommitA)
        ).pipe(Effect.provide(layer))
        expect(
          built.preregistration.registration_core.repository_binding
            .source_commit_a
        ).toBe(fixture.sourceCommitA)
      }),
    (previous) =>
      Effect.sync(() => {
        if (previous === undefined) {
          delete process.env["PATH"]
        } else {
          process.env["PATH"] = previous
        }
      })
  ).pipe(Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("rejects ancestry forged only through .git/info/grafts", () => {
  const fixture = makeGitFixture()
  const sourceTree = runGit(fixture.root, [
    "rev-parse",
    `${fixture.sourceCommitA}^{tree}`
  ])
  const unrelatedSourceA = runGit(fixture.root, [
    "commit-tree",
    sourceTree,
    "-m",
    "unrelated source A"
  ])
  writeGraft(fixture, unrelatedSourceA, [S2S_PREREG_PILOT_SOURCE_COMMIT])
  expect(
    runGit(fixture.root, [
      "--no-replace-objects",
      "merge-base",
      "--is-ancestor",
      S2S_PREREG_PILOT_SOURCE_COMMIT,
      unrelatedSourceA
    ])
  ).toBe("")
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const continuity = yield* verifyS2SNumericContinuity(
      unrelatedSourceA
    ).pipe(Effect.either)
    expect(Either.isLeft(continuity)).toBe(true)
    if (Either.isLeft(continuity)) {
      expect(continuity.left).toMatchObject({ reason: "PILOT_NOT_ANCESTOR" })
    }

    const built = yield* buildS2SPreregistration(
      buildInput(unrelatedSourceA)
    ).pipe(Effect.either)
    expect(Either.isLeft(built)).toBe(true)
    if (Either.isLeft(built)) {
      expect(built.left).toMatchObject({ reason: "PILOT_NOT_ANCESTOR" })
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("rejects source A when it already tracks the preregistration path", () => {
  const fixture = makeGitFixture()
  const preregistrationPath = join(fixture.root, S2S_PREREGISTRATION_PATH)
  mkdirSync(dirname(preregistrationPath), { recursive: true })
  writeFileSync(preregistrationPath, "{}\n", "utf8")
  runGit(fixture.root, ["add", "--", S2S_PREREGISTRATION_PATH])
  runGit(fixture.root, [
    "commit",
    "--quiet",
    "-m",
    "adversarial preexisting preregistration"
  ])
  const sourceWithPreregistration = runGit(fixture.root, ["rev-parse", "HEAD"])
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const result = yield* buildS2SPreregistration(
      buildInput(sourceWithPreregistration)
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        reason: "PREREGISTRATION_PATH_PRESENT"
      })
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("rejects a structurally forged validation snapshot before Git I/O", () => {
  let calls = 0
  const layer = makeS2SPreregGitRepositoryTestLayer(() => {
    calls += 1
    return Effect.die("Git must not be called for a forged validation snapshot")
  })
  const forged = {
    preregistration: {},
    canonicalBytes: UTF8_ENCODER.encode("{}\n"),
    fileSha256: "0".repeat(64)
  }
  return Effect.gen(function* () {
    // @ts-expect-error The missing private brand is the compile-time half of this test.
    const validation = validateS2SRegistrationCommitB(forged, "0".repeat(40))
    const result = yield* validation.pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        reason: "INVALID_VALIDATION_SNAPSHOT"
      })
    }
    expect(calls).toBe(0)
  }).pipe(Effect.provide(layer))
})

it("rejects forged and hostile registration commit authorities", () => {
  const hostile = new Proxy({}, {
    getPrototypeOf: () => {
      throw new Error("authority inspection must not traverse the object")
    },
    ownKeys: () => {
      throw new Error("authority inspection must not enumerate the object")
    }
  })
  const plain = inspectS2SRegistrationCommitAuthority(Object.freeze({}))
  const hostileOutcome = inspectS2SRegistrationCommitAuthority(hostile)
  expect(Either.isLeft(plain)).toBe(true)
  expect(Either.isLeft(hostileOutcome)).toBe(true)
  if (Either.isLeft(plain)) {
    expect(plain.left.reason).toBe("INVALID_REGISTRATION_AUTHORITY")
  }
  if (Either.isLeft(hostileOutcome)) {
    expect(hostileOutcome.left.reason).toBe("INVALID_REGISTRATION_AUTHORITY")
  }
})

it.effect("snapshots input bytes before asynchronous Git revalidation", () => {
  const fixture = makeGitFixture()
  const processLayer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const built = yield* buildS2SPreregistration(
      buildInput(fixture.sourceCommitA)
    ).pipe(Effect.provide(processLayer))
    const callerBytes = new Uint8Array(built.canonicalBytes)
    const started = yield* Deferred.make<void>()
    const release = yield* Deferred.make<void>()
    let delayed = false
    const delayedLayer = makeS2SPreregGitRepositoryTestLayer((command) => {
      const execute = Effect.sync(() => executeGitCommand(fixture.root, command))
      if (delayed) return execute
      delayed = true
      return Deferred.succeed(started, undefined).pipe(
        Effect.zipRight(Deferred.await(release)),
        Effect.zipRight(execute)
      )
    })
    const fiber = yield* parseAndValidateS2SPreregistration(callerBytes, {
      expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256
    }).pipe(Effect.provide(delayedLayer), Effect.fork)
    yield* Deferred.await(started)
    callerBytes.fill(0)
    yield* Deferred.succeed(release, undefined)
    const validated = yield* Fiber.join(fiber)
    expect(validated.fileSha256).toBe(built.fileSha256)
    expect(validated.canonicalBytes).toEqual(built.canonicalBytes)

    const registrationCommitB = writeRegistration(
      fixture,
      "registration-concurrent-input-mutation",
      built.canonicalBytes
    )
    const authority = yield* validateS2SRegistrationCommitB(
      validated,
      registrationCommitB
    ).pipe(Effect.provide(processLayer))
    const evidence = inspectS2SRegistrationCommitAuthority(authority)
    expect(Either.isRight(evidence)).toBe(true)
    if (Either.isRight(evidence)) {
      expect(evidence.right.registrationCommitB).toBe(registrationCommitB)
    }
  }).pipe(Effect.ensuring(Effect.sync(fixture.cleanup)))
})

it.effect("rejects registration parentage forged only through grafts", () => {
  const fixture = makeGitFixture()
  const layer = makeS2SPreregGitRepositoryProcessLayer(fixture.root)
  return Effect.gen(function* () {
    const built = yield* buildS2SPreregistration(
      buildInput(fixture.sourceCommitA)
    )
    const validated = yield* parseAndValidateS2SPreregistration(
      built.canonicalBytes,
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    )
    const ordinaryB = writeRegistration(
      fixture,
      "registration-graft-preimage",
      built.canonicalBytes
    )
    const sourceTree = runGit(fixture.root, [
      "rev-parse",
      `${fixture.sourceCommitA}^{tree}`
    ])
    const unrelatedParent = runGit(fixture.root, [
      "commit-tree",
      sourceTree,
      "-m",
      "unrelated B parent"
    ])
    const registrationTree = runGit(fixture.root, [
      "rev-parse",
      `${ordinaryB}^{tree}`
    ])
    const forgedB = runGit(fixture.root, [
      "commit-tree",
      registrationTree,
      "-p",
      unrelatedParent,
      "-m",
      "graft-forged registration B"
    ])
    writeGraft(fixture, forgedB, [fixture.sourceCommitA])
    expect(
      runGit(fixture.root, [
        "--no-replace-objects",
        "rev-list",
        "--parents",
        "-n",
        "1",
        forgedB
      ])
    ).toBe(`${forgedB} ${fixture.sourceCommitA}`)

    const result = yield* validateS2SRegistrationCommitB(
      validated,
      forgedB
    ).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "NOT_DIRECT_CHILD" })
    }
  }).pipe(Effect.provide(layer), Effect.ensuring(Effect.sync(fixture.cleanup)))
})

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

    const preregPathRoot = decodeObject(built.canonicalBytes)
    const preregPathCore = requiredRecord(preregPathRoot, "registration_core")
    const preregPathFreeze = requiredRecord(preregPathCore, "source_freeze")
    const preregPathManifest = requiredRecord(
      preregPathFreeze,
      "tracked_bytes_manifest"
    )
    const preregPathRows = preregPathManifest["rows"]
    if (!Array.isArray(preregPathRows)) throw new Error("manifest rows missing")
    const fixtureRow = preregPathRows.find(
      (row) => isRecord(row) && row["path"] === "s2s-control-fixture.txt"
    )
    if (!isRecord(fixtureRow)) throw new Error("fixture manifest row missing")
    fixtureRow["path"] = S2S_PREREGISTRATION_PATH
    preregPathRows.sort((left, right) => {
      if (!isRecord(left) || !isRecord(right)) {
        throw new Error("manifest row is not an object")
      }
      const leftPath = left["path"]
      const rightPath = right["path"]
      if (typeof leftPath !== "string" || typeof rightPath !== "string") {
        throw new Error("manifest row path is not a string")
      }
      return leftPath < rightPath ? -1 : leftPath > rightPath ? 1 : 0
    })
    rehashPreregistrationDocument(preregPathRoot)
    const preregPathResult = yield* parseAndValidateS2SPreregistration(
      encodeCanonicalDocument(preregPathRoot),
      { expectedResourcePolicySha256: S2S_PREREG_RESOURCE_POLICY_SHA256 }
    ).pipe(Effect.either)
    expect(Either.isLeft(preregPathResult)).toBe(true)
    if (Either.isLeft(preregPathResult)) {
      expect(preregPathResult.left).toMatchObject({ reason: "FIXED_BINDING_DRIFT" })
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

it.effect("rejects a cycle in the raw commit-parent traversal", () => {
  const cyclicOid = "a".repeat(40)
  const layer = makeS2SPreregGitRepositoryTestLayer((command) => {
    if (command.operation === "verify source commit object type") {
      return Effect.succeed({
        exitCode: 0,
        stdout: UTF8_ENCODER.encode("commit\n"),
        stderr: new Uint8Array()
      })
    }
    if (command.operation === `read raw ancestry commit ${cyclicOid}`) {
      return Effect.succeed({
        exitCode: 0,
        stdout: encodeRawCommitBatch(cyclicOid, [cyclicOid]),
        stderr: new Uint8Array()
      })
    }
    return Effect.die(`unexpected Git operation: ${command.operation}`)
  })
  return Effect.gen(function* () {
    const result = yield* verifyS2SNumericContinuity(cyclicOid).pipe(
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "ANCESTRY_CYCLE" })
    }
  }).pipe(Effect.provide(layer))
})

it.effect("fails closed at the raw ancestry unique-commit bound", () => {
  const oidAt = (index: number): string => index.toString(16).padStart(40, "0")
  const sourceOid = oidAt(1)
  let rawReads = 0
  const layer = makeS2SPreregGitRepositoryTestLayer((command) => {
    if (command.operation === "verify source commit object type") {
      return Effect.succeed({
        exitCode: 0,
        stdout: UTF8_ENCODER.encode("commit\n"),
        stderr: new Uint8Array()
      })
    }
    const prefix = "read raw ancestry commit "
    if (command.operation.startsWith(prefix)) {
      rawReads += 1
      const oid = command.operation.slice(prefix.length)
      const index = Number.parseInt(oid, 16)
      return Effect.succeed({
        exitCode: 0,
        stdout: encodeRawCommitBatch(oid, [oidAt(index + 1)]),
        stderr: new Uint8Array()
      })
    }
    return Effect.die(`unexpected Git operation: ${command.operation}`)
  })
  return Effect.gen(function* () {
    const result = yield* verifyS2SNumericContinuity(sourceOid).pipe(
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "ANCESTRY_LIMIT_EXCEEDED" })
    }
    expect(rawReads).toBe(S2S_PREREG_ANCESTRY_MAX_COMMITS)
  }).pipe(Effect.provide(layer))
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
