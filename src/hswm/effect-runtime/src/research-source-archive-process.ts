#!/usr/bin/env node
import { resolve } from "node:path"
import { Effect } from "effect"
import { runArgvProcessMain, refuse, type ProcessReply } from "./effect-process-main.js"
import { PosixFileSystem } from "./effect-posix-filesystem.js"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { NodePosixServicesLive } from "./effect-posix-services.js"
import { CurlResearchSourceHttp, NativeResearchSourceHttp, ResearchSourceHttp, archiveResearchSources, verifyResearchSourceArchive } from "./research-source-archive.js"

const usage = "Usage: node dist/research-source-archive-process.js archive --manifest SOURCES.json --root PRIVATE_ARCHIVE [--transport native|curl] | verify --root PRIVATE_ARCHIVE\\n"
interface ArchiveArgs { readonly command: "archive" | "verify"; readonly root: string; readonly manifest: string | null; readonly transport: "native" | "curl" }
const parseArgs = (argv: ReadonlyArray<string>): ArchiveArgs | null => {
  const command = argv[0]; if (command !== "archive" && command !== "verify") return null
  const fields = new Map<string, string>(); const allowed = command === "archive" ? new Set(["--root", "--manifest", "--transport"]) : new Set(["--root"])
  for (let index = 1; index < argv.length; index += 2) { const flag = argv[index]; const value = argv[index + 1]; if (typeof flag !== "string" || typeof value !== "string" || !allowed.has(flag) || fields.has(flag) || value.length === 0 || value.startsWith("--")) return null; fields.set(flag, value) }
  const root = fields.get("--root"); if (root === undefined) return null
  const manifest = fields.get("--manifest") ?? null; const transport = fields.get("--transport") ?? "native"
  if ((command === "archive" && manifest === null) || (transport !== "native" && transport !== "curl")) return null
  return Object.freeze({ command, root, manifest, transport })
}
const run = (argv: ReadonlyArray<string>): Effect.Effect<string | ProcessReply, unknown, PosixFileSystem | BoundedSubprocess> => Effect.gen(function* () {
  const parsed = parseArgs(argv); if (parsed === null) return yield* Effect.fail(refuse(usage.trim()))
  if (parsed.command === "verify") { const verified = yield* verifyResearchSourceArchive(parsed.root); return Object.freeze({ stdout: `${JSON.stringify(verified)}\n`, exitCode: verified.valid ? 0 : 1 }) }
  const manifestPath = parsed.manifest; if (manifestPath === null) return yield* Effect.fail(refuse(usage.trim()))
  const fs = yield* PosixFileSystem; const read = yield* fs.readRegularBounded(resolve(manifestPath), { maximumBytes: 4 * 1024 * 1024, minimumBytes: 1, operation: "read source archive input manifest" }).pipe(Effect.mapError(error => refuse(error.detail)))
  const archived = yield* archiveResearchSources(parsed.root, new TextDecoder().decode(read.bytes)).pipe(Effect.provideService(ResearchSourceHttp, parsed.transport === "curl" ? CurlResearchSourceHttp : NativeResearchSourceHttp)); const failures = archived.manifest.receipts.filter(receipt => receipt.status === "FAILED").length
  return `${JSON.stringify({ root: archived.root, resumed: archived.resumed, sources: archived.manifest.receipts.length, archived: archived.manifest.receipts.length - failures, failed: failures, manifestReceipt: "manifest.receipt.v1.json" })}\n`
})
export const researchSourceArchiveMain = (argv: ReadonlyArray<string>) => runArgvProcessMain({ program: args => run(args), refusalPrefix: "RESEARCH_SOURCE_ARCHIVE_REFUSED", describeFailure: error => error instanceof Error ? error.message : String(error), failureExitCode: 1 }, argv, undefined, NodePosixServicesLive)
if (import.meta.main) process.exitCode = await researchSourceArchiveMain(process.argv.slice(2))
