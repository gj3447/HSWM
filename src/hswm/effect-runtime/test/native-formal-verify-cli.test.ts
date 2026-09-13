import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { Effect } from "effect"
import { expect, it } from "vitest"

import { NodePosixServicesLive } from "../src/effect-posix-services.js"
import { runNativeFormalVerifyCli } from "../src/native-formal-verify-cli.js"

const root = resolve(import.meta.dirname, "../../../..")
const original = JSON.parse(readFileSync(resolve(root, "tests/fixtures/formal_native_v1/original_python.json"), "utf8"))
const expected = typeof original === "object" && original !== null && "canonical_permit_vector_stdout" in original && typeof original.canonical_permit_vector_stdout === "string"
  ? original.canonical_permit_vector_stdout
  : ""

const run = (argv: readonly string[]) => Effect.runPromise(runNativeFormalVerifyCli(argv).pipe(Effect.provide(NodePosixServicesLive)))

it("runs the independent bounded OpenSSL Ed25519 consumer and preserves canonical output bytes", async () => {
  const result = await run(["canonical-permit-vector", "--repo-root", root])
  expect(result.exitCode).toBe(0)
  expect(result.stdout).toBe(expected)
})

it("preloads extra runtime sources before its hash-bound verifier runs", async () => {
  const outcome = await Effect.runPromise(Effect.either(runNativeFormalVerifyCli(["cellular-runtime-longinus", "--repo-root", root]).pipe(Effect.provide(NodePosixServicesLive))))
  expect(outcome._tag).toBe("Left")
  if (outcome._tag === "Left") expect(outcome.left.detail).not.toContain("missing source: formal/HSWMRuntime.lean")
})

it("preloads the durable preregistration's locked judge before verification", async () => {
  const outcome = await Effect.runPromise(Effect.either(runNativeFormalVerifyCli(["durable-runtime-longinus", "--repo-root", root]).pipe(Effect.provide(NodePosixServicesLive))))
  expect(outcome._tag).toBe("Left")
  if (outcome._tag === "Left") expect(outcome.left.detail).not.toContain("locked judge SHA-256 drift")
})
