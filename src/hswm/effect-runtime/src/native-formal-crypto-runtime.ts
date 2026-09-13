import { createHash, randomUUID } from "node:crypto"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Data, Effect } from "effect"

import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"

export class NativeFormalCryptoRuntimeError extends Data.TaggedError("NativeFormalCryptoRuntimeError")<{
  readonly detail: string
}> {}

export interface NativeFormalEd25519Vector {
  readonly signingDocument: Uint8Array
  readonly publicKeySpkiDer: Uint8Array
  readonly signature: Uint8Array
}

const fail = (detail: string): NativeFormalCryptoRuntimeError => new NativeFormalCryptoRuntimeError({ detail })
const executable = "/usr/bin/openssl"
const maximumExecutableBytes = 32 * 1024 * 1024

const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")

const temporaryPaths = (): readonly [string, string, string] => {
  const token = randomUUID()
  return [
    join(tmpdir(), `hswm-formal-public-key-${token}.der`),
    join(tmpdir(), `hswm-formal-signature-${token}.bin`),
    join(tmpdir(), `hswm-formal-document-${token}.json`)
  ]
}

export const verifyNativeFormalOpenSslEd25519 = (
  vector: NativeFormalEd25519Vector
): Effect.Effect<void, NativeFormalCryptoRuntimeError, PosixFileSystem | BoundedSubprocess> =>
  Effect.gen(function* () {
    if (vector.publicKeySpkiDer.byteLength !== 44 || vector.signature.byteLength !== 64 || vector.signingDocument.byteLength < 1) {
      return yield* Effect.fail(fail("fixed Ed25519 vector bytes are invalid"))
    }
    const filesystem = yield* PosixFileSystem
    const subprocess = yield* BoundedSubprocess
    const pinnedBefore = yield* filesystem.readRegularBounded(executable, {
      maximumBytes: maximumExecutableBytes,
      minimumBytes: 1,
      operation: "native-formal-openssl-pin-before"
    }).pipe(Effect.mapError(() => fail("OpenSSL executable is unavailable")))
    const before = digest(pinnedBefore.bytes)
    const [publicKeyPath, signaturePath, documentPath] = temporaryPaths()
    yield* Effect.acquireUseRelease(
      Effect.all([
        filesystem.writeExclusive(publicKeyPath, vector.publicKeySpkiDer, { mode: 0o600, sync: true, operation: "native-formal-openssl-public-key" }),
        filesystem.writeExclusive(signaturePath, vector.signature, { mode: 0o600, sync: true, operation: "native-formal-openssl-signature" }),
        filesystem.writeExclusive(documentPath, vector.signingDocument, { mode: 0o600, sync: true, operation: "native-formal-openssl-document" })
      ], { concurrency: 1 }).pipe(Effect.mapError(() => fail("cannot stage fixed Ed25519 vector"))),
      () => Effect.gen(function* () {
        const observation = yield* subprocess.observe({
          argv: [executable, "pkeyutl", "-verify", "-pubin", "-inkey", publicKeyPath, "-keyform", "DER", "-in", documentPath, "-sigfile", signaturePath, "-rawin"],
          cwd: tmpdir(),
          environment: { PATH: "/usr/bin:/bin", LANG: "C", LC_ALL: "C" },
          timeoutMs: 2_000,
          maximumOutputBytes: 8_192,
          killProcessGroup: true
        }).pipe(Effect.mapError(() => fail("OpenSSL invocation failed")))
        if (observation.launchError !== null || observation.timedOut || observation.outputTruncated || observation.exitCode !== 0 || observation.signal !== null) {
          return yield* Effect.fail(fail("OpenSSL rejected the fixed Ed25519 vector"))
        }
      }),
      () => Effect.all([
        filesystem.unlinkIfPresent(publicKeyPath, "native-formal-openssl-cleanup"),
        filesystem.unlinkIfPresent(signaturePath, "native-formal-openssl-cleanup"),
        filesystem.unlinkIfPresent(documentPath, "native-formal-openssl-cleanup")
      ], { concurrency: 1 }).pipe(Effect.ignore)
    )
    const pinnedAfter = yield* filesystem.readRegularBounded(executable, {
      maximumBytes: maximumExecutableBytes,
      minimumBytes: 1,
      operation: "native-formal-openssl-pin-after"
    }).pipe(Effect.mapError(() => fail("OpenSSL executable changed during verification")))
    if (digest(pinnedAfter.bytes) !== before) return yield* Effect.fail(fail("OpenSSL executable changed during verification"))
  })
