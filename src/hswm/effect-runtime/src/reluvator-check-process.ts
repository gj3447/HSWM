#!/usr/bin/env node
/** Fixed, bounded Reluvator development checks. Both transport ends execute Node. */
import { Effect } from "effect"
import { BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { runArgvProcessMain, refuse } from "./effect-process-main.js"

const CHECKS: Readonly<Record<string, ReadonlyArray<string>>> = Object.freeze({
  contracts: ["packages/app/src/entrypoints/asyncapi-emit.ts", "--check"],
  mesh: ["tools/contract-mesh/mesh-check.mjs", "--deep", "--json"]
})

export const reluvatorCheck = (argv: ReadonlyArray<string>) => Effect.gen(function* () {
  const check = CHECKS[argv[0] ?? ""]
  if (argv.length !== 1 || check === undefined) return yield* Effect.fail(refuse("focus must be contracts or mesh"))
  // These bytes contain only a fixed allowlisted command. No task text is interpolated.
  // The remote child writes into a bounded buffer, then stdout drains before exit.
  const source = `import {spawnSync} from 'node:child_process';\nconst r=spawnSync('/data/kjra/.local/bin/node',${JSON.stringify(check)},{cwd:'/data/kjra/PROJECT/RELUVATOR',timeout:40000,maxBuffer:64000,encoding:'buffer',env:{...process.env,PATH:'/data/kjra/.local/bin:/usr/local/bin:/usr/bin:/bin'}});\nif(r.error){process.stderr.write(JSON.stringify({status:'FAILED',error:r.error.code})+'\\n');process.exitCode=65;}else{process.stdout.write(r.stdout);process.stderr.write(r.stderr);process.exitCode=r.status??1;}\n`
  const subprocess = yield* BoundedSubprocess
  const result = yield* subprocess.observe({
    argv: ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes", "delltower",
      "/usr/bin/timeout", "--kill-after=5s", "45s", "/data/kjra/.local/bin/node", "--input-type=module", "-"],
    cwd: process.cwd(), environment: process.env as Record<string, string>, timeoutMs: 55_000,
    maximumOutputBytes: 64_000, stdin: Buffer.from(source), killProcessGroup: true
  })
  return {
    stdout: Buffer.concat([Buffer.from(result.stdout), Buffer.from(result.stderr)]).toString("utf8"),
    exitCode: result.outputTruncated || result.timedOut || result.launchError !== null ? 65 : result.exitCode ?? 1
  }
})

if (import.meta.main) {
  process.exitCode = await runArgvProcessMain({ program: reluvatorCheck, describeFailure: (error) => error.detail }, process.argv.slice(2))
}
