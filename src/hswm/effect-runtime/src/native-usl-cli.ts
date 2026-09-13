/** Effect I/O shell preserving usl_cli.py's project|preview --request PATH surface. */
import { resolve } from "node:path"
import { parseArgs } from "node:util"
import { Effect, Either } from "effect"
import { PosixFileSystem, type PosixFileSystem as PosixFileSystemService } from "./effect-posix-filesystem.js"
import { NativeUslCliError, previewNativeUsl, projectNativeUsl } from "./native-usl-cli-domain.js"
import { decodeNativeTaskJson, renderNativeTaskJson } from "./native-task-json-domain.js"
import type { ProcessReply } from "./effect-process-main.js"

const usage = "usage: hswm-usl-native <project|preview> --request REQUEST"
const fail = (detail: string) => new NativeUslCliError({ detail })
export const runNativeUslCli = (argv: readonly string[]): Effect.Effect<ProcessReply, NativeUslCliError, PosixFileSystemService> => Effect.gen(function* () {
  const parsed = yield* Effect.try({ try: () => parseArgs({ args: [...argv], allowPositionals: true, strict: true, options: { request: { type: "string" }, help: { type: "boolean" } } }), catch: () => fail(usage) })
  if (parsed.values.help) return { stdout: `${usage}\n`, exitCode: 0 }
  const command = parsed.positionals[0], requestPath = parsed.values.request
  if ((command !== "project" && command !== "preview") || parsed.positionals.length !== 1 || requestPath === undefined) return yield* Effect.fail(fail(usage))
  const fs = yield* PosixFileSystem
  const bytes = yield* fs.readRegularBounded(resolve(requestPath), { maximumBytes: 1_048_576, operation: "native-usl-request" }).pipe(Effect.mapError(error => fail(error.detail)))
  const decoded = decodeNativeTaskJson(bytes.bytes)
  if (Either.isLeft(decoded)) return yield* Effect.fail(fail("malformed JSON"))
  const result = command === "project" ? projectNativeUsl(decoded.right) : previewNativeUsl(decoded.right)
  if (Either.isLeft(result)) return yield* Effect.fail(result.left)
  return { stdout: command === "project" ? `${JSON.stringify(result.right, null, 2)}\n` : `${renderNativeTaskJson(result.right, "pretty")}\n`, exitCode: 0 }
})
export const describeNativeUslCliError = (error: NativeUslCliError): string => JSON.stringify({ status: "REJECTED", error: error.detail })
