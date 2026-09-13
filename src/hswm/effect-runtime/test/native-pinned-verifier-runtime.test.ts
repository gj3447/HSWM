import { createHash } from "node:crypto"
import { copyFileSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Effect, Layer } from "effect"
import { expect, it } from "@effect/vitest"

import { BoundedSubprocess, NodeBoundedSubprocessLive, type BoundedSubprocessShape } from "../src/effect-bounded-subprocess.js"
import { NativePinnedVerifier, NodePinnedVerifierLive } from "../src/native-pinned-verifier-runtime.js"

const digest = (value: string | Uint8Array): string => createHash("sha256").update(value).digest("hex")

it.effect("runs a copied Node executable and argv input from held descriptors after both pathname swaps", () => {
  const directory = mkdtempSync(join(tmpdir(), "hswm-pinned-verifier-"))
  const executable = join(directory, "node")
  const input = join(directory, "input.txt")
  const replacement = join(directory, "replacement")
  const inputReplacement = join(directory, "input-replacement")
  const script = join(directory, "read-input.mjs")
  copyFileSync(process.execPath, executable)
  writeFileSync(input, "held input\n")
  writeFileSync(script, "import { readFileSync } from 'node:fs'; process.stdout.write(readFileSync(process.argv[2], 'utf8'))")
  const originalExecutableHash = digest(readFileSync(executable))
  const originalInputHash = digest("held input\n")
  let calls = 0
  let verificationArgv: ReadonlyArray<string> = []
  const swapping: BoundedSubprocessShape = {
    observe: (command) => {
      if (calls++ === 1) {
        writeFileSync(replacement, "#!/bin/sh\necho replaced\n")
        renameSync(replacement, executable)
        writeFileSync(inputReplacement, "swapped input\n")
        renameSync(inputReplacement, input)
      }
      if (calls === 2) verificationArgv = command.argv
      return Effect.gen(function* () { return yield* BoundedSubprocess }).pipe(Effect.flatMap((real) => real.observe(command)), Effect.provide(NodeBoundedSubprocessLive))
    }
  }
  const request = {
    argv: [executable, script, input], executablePath: executable, executableSha256: originalExecutableHash,
    expectedVersionOutput: `${process.version}\n`, versionArgv: ["--version"], pinnedInputs: [{ path: input, argvPath: input, sha256: originalInputHash, maximumBytes: 64 * 1024 }],
    cwd: directory, environment: { LANG: "C", LC_ALL: "C", PATH: "/usr/bin:/bin" }, timeoutMs: 30_000, maximumOutputBytes: 64 * 1024
  }
  return Effect.gen(function* () {
    const verifier = yield* NativePinnedVerifier
    const result = yield* verifier.verify(request)
    expect(verificationArgv[2]).toBe("/proc/self/fd/4")
    expect(new TextDecoder().decode(result.verification.stdout)).toBe("held input\n")
    expect(result.verification.exitCode).toBe(0)
  }).pipe(
    Effect.provide(Layer.merge(Layer.succeed(BoundedSubprocess, swapping), NodePinnedVerifierLive)),
    Effect.ensuring(Effect.sync(() => rmSync(directory, { recursive: true, force: true })))
  )
})
