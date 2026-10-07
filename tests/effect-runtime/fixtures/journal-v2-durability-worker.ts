import { existsSync, readFileSync, writeFileSync } from "node:fs"

import { Effect, Either } from "effect"

import {
  makeLocalPermitVerifierContext,
  type LocalPermitCommitRequest
} from "../../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.js"
import { makeVerifiedAdmissionGatewayV2WithCheckpointForTest } from "../../../src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.js"

type Checkpoint = "prepared-file-fsync:after" | "slot-link:after"
interface Fixture {
  readonly clockIso: string
  readonly leanCli: string
  readonly trustSnapshotBytesBase64Url: string
  readonly envelopeBytesBase64Url: string
  readonly expectedBindings: LocalPermitCommitRequest["expectedBindings"]
  readonly preStateBytesBase64Url: string
  readonly postStateBytesBase64Url: string
}

const checkpoint = (value: string | undefined): Checkpoint => {
  if (value === "prepared-file-fsync:after" || value === "slot-link:after") return value
  throw new Error("invalid V2 publication checkpoint")
}
const bytes = (value: string): Uint8Array => {
  const decoded = Uint8Array.from(Buffer.from(value, "base64url"))
  if (decoded.byteLength === 0 || Buffer.from(decoded).toString("base64url") !== value) {
    throw new Error("fixture has noncanonical base64url")
  }
  return decoded
}
const main = async (): Promise<void> => {
  const [root, fixturePath, selected, readyPath, releasePath] = process.argv.slice(2)
  if (root === undefined || fixturePath === undefined) throw new Error("usage: ROOT FIXTURE CHECKPOINT")
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as Fixture
  if (!existsSync(fixture.leanCli)) throw new Error("fixture Lean CLI is unavailable")
  const verifier = makeLocalPermitVerifierContext(bytes(fixture.trustSnapshotBytesBase64Url))
  if (Either.isLeft(verifier)) throw verifier.left
  const gateway = makeVerifiedAdmissionGatewayV2WithCheckpointForTest(
    root,
    verifier.right,
    { leanExecutable: fixture.leanCli },
    () => new Date(fixture.clockIso),
    checkpoint(selected),
    () => {
      const ready = readyPath
      const release = releasePath
      if (ready === undefined || release === undefined) {
        process.kill(process.pid, "SIGKILL")
        return
      }
      writeFileSync(ready, `${process.pid}\n`, { flag: "wx", mode: 0o400 })
      const wait = new Int32Array(new SharedArrayBuffer(4))
      const deadline = Date.now() + 10_000
      while (!existsSync(release)) {
        if (Date.now() >= deadline) throw new Error("race release did not appear")
        Atomics.wait(wait, 0, 0, 10)
      }
    }
  )
  if (Either.isLeft(gateway)) throw gateway.left
  const result = await Effect.runPromise(Effect.either(gateway.right.submit({
    envelopeBytes: bytes(fixture.envelopeBytesBase64Url),
    expectedBindings: fixture.expectedBindings,
    preStateBytes: bytes(fixture.preStateBytesBase64Url),
    postStateBytes: bytes(fixture.postStateBytesBase64Url)
  })))
  if (Either.isLeft(result)) {
    process.stderr.write(`${JSON.stringify({ code: result.left.code })}\n`)
    process.exitCode = 1
    return
  }
  if (readyPath !== undefined && releasePath !== undefined) {
    process.stdout.write(`${JSON.stringify({ status: "PUBLISHED", recordSha256: result.right.commit.recordSha256 })}\n`)
    return
  }
  throw new Error("V2 crash checkpoint did not terminate worker")
}
void main().catch((cause: unknown) => {
  process.stderr.write(`${cause instanceof Error ? cause.message : String(cause)}\n`)
  process.exitCode = 1
})
