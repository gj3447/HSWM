import { readFile } from "node:fs/promises"

import { Effect, Either } from "effect"

import {
  makeLocalPermitCommitStoreWithCheckpointForTest,
  makeLocalPermitVerifierContext,
  type LocalPermitCommitRequest
} from "../../src/canonical-atom-v2-local-permit-commit.js"

type Checkpoint = "prepared-file-fsync:after" | "slot-link:after"

interface ProcessCrashFixture {
  readonly clockIso: string
  readonly trustSnapshotBytesBase64Url: string
  readonly envelopeBytesBase64Url: string
  readonly expectedBindings: LocalPermitCommitRequest["expectedBindings"]
  readonly preStateBytesBase64Url: string
  readonly postStateBytesBase64Url: string
}

const isCheckpoint = (value: string | undefined): value is Checkpoint =>
  value === "prepared-file-fsync:after" || value === "slot-link:after"

const readFixture = async (path: string): Promise<ProcessCrashFixture> => {
  const parsed: unknown = JSON.parse(await readFile(path, "utf8"))
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("local Permit process-crash fixture must be an object")
  }
  const value = parsed as Partial<ProcessCrashFixture>
  if (
    typeof value.clockIso !== "string" ||
    typeof value.trustSnapshotBytesBase64Url !== "string" ||
    typeof value.envelopeBytesBase64Url !== "string" ||
    typeof value.preStateBytesBase64Url !== "string" ||
    typeof value.postStateBytesBase64Url !== "string" ||
    value.expectedBindings === undefined
  ) {
    throw new Error("local Permit process-crash fixture is incomplete")
  }
  return value as ProcessCrashFixture
}

const strictBase64Url = (value: string): Uint8Array => {
  const bytes = Uint8Array.from(Buffer.from(value, "base64url"))
  if (bytes.byteLength === 0 || Buffer.from(bytes).toString("base64url") !== value) {
    throw new Error("local Permit process-crash fixture has noncanonical base64url")
  }
  return bytes
}

const main = async (): Promise<void> => {
  const [rootPath, fixturePath, checkpoint] = process.argv.slice(2)
  if (rootPath === undefined || fixturePath === undefined || !isCheckpoint(checkpoint)) {
    throw new Error("usage: local-permit-process-worker ROOT FIXTURE CHECKPOINT")
  }
  const fixture = await readFixture(fixturePath)
  const verifier = makeLocalPermitVerifierContext(
    strictBase64Url(fixture.trustSnapshotBytesBase64Url)
  )
  if (Either.isLeft(verifier)) throw verifier.left
  const store = makeLocalPermitCommitStoreWithCheckpointForTest(
    rootPath,
    verifier.right,
    () => new Date(fixture.clockIso),
    checkpoint,
    () => process.kill(process.pid, "SIGKILL")
  )
  await Effect.runPromise(store.commit({
    envelopeBytes: strictBase64Url(fixture.envelopeBytesBase64Url),
    expectedBindings: fixture.expectedBindings,
    preStateBytes: strictBase64Url(fixture.preStateBytesBase64Url),
    postStateBytes: strictBase64Url(fixture.postStateBytesBase64Url)
  }))
  throw new Error("process-crash checkpoint did not terminate the worker")
}

void main().catch((cause: unknown) => {
  process.stderr.write(
    `${cause instanceof Error ? cause.stack ?? cause.message : String(cause)}\n`
  )
  process.exitCode = 1
})
