// Local-only USL resolver/storage regression probe. No external URL or real record file.
import { createHash } from "node:crypto"
import { execFileSync } from "node:child_process"
import { promises as fs } from "node:fs"
import * as os from "node:os"
import * as path from "node:path"
import { Effect, Either } from "../../../USL/node_modules/effect/dist/esm/index.js"
import { parseLocator } from "../../../USL/src/locator.ts"
import { resolveWith } from "../../../USL/src/resolve.ts"
import { writeTextAtomic } from "../../../USL/src/storage.ts"

const USL = "/home/lagyeongjun/CD/USL"
const watched = ["src/resolve.ts", "src/storage.ts", "src/cli.ts"]
const sha = (text: string | Uint8Array) => createHash("sha256").update(text).digest("hex")
const hashes = async () => Object.fromEntries(await Promise.all(watched.map(async (file) => [file, sha(await fs.readFile(path.join(USL, file)))])))
const loc = (text: string) => Either.getOrThrow(parseLocator(text))
const resolve = (cfg: any, text: string) => Effect.runPromise(Effect.either(resolveWith(cfg)(loc(text))))
const git = (cwd: string, args: string[]) => execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim()

const run = async () => {
  const before = await hashes()
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "hswm-usl-latest-audit-"))
  try {
    const hostname = "latest-audit"
    const source = path.join(dir, "lines.txt")
    await fs.writeFile(source, "one\ntwo\nthree\n")
    const fsLocator = `file://${hostname}${source}#L2-L3`
    const fsResult = await resolve({ hostname, gitRepos: {}, kgMcpUrl: "http://kg.invalid", fetchImpl: fetch, allowedLocators: [fsLocator] }, fsLocator)

    const repo = path.join(dir, "repo")
    await fs.mkdir(repo)
    git(repo, ["init", "-q"]); git(repo, ["config", "user.email", "audit@example.invalid"]); git(repo, ["config", "user.name", "audit"])
    await fs.writeFile(path.join(repo, "lines.txt"), "one\ntwo\nthree\n")
    git(repo, ["add", "lines.txt"]); git(repo, ["commit", "-m", "fixture"])
    const commit = git(repo, ["rev-parse", "HEAD"])
    const gitLocator = `git://fixture/repo@${commit}:lines.txt@L2-L3`
    const gitResult = await resolve({ hostname, gitRepos: { "fixture/repo": repo }, kgMcpUrl: "http://kg.invalid", fetchImpl: fetch, allowedLocators: [gitLocator] }, gitLocator)

    const start = "https://inside.test/start", next = "https://inside.test/final"
    const redirectCalls: string[] = []
    const redirect = await resolve({ hostname, gitRepos: {}, kgMcpUrl: "http://kg.invalid", allowedLocators: [start, next], maxResponseBytes: 2,
      fetchImpl: async (url: string) => {
        redirectCalls.push(url)
        return url === start ? new Response(null, { status: 302, headers: { location: next } }) : new Response("abc")
      },
    }, start)
    const timeout = await resolve({ hostname, gitRepos: {}, kgMcpUrl: "http://kg.invalid", allowedLocators: [start], timeoutMs: 1,
      fetchImpl: async (_url: string, init: RequestInit) => new Promise<Response>((_ok, fail) => init.signal?.addEventListener("abort", () => fail(new Error("aborted")))),
    }, start)

    const record = path.join(dir, "records.json")
    await fs.writeFile(record, "old\n")
    let casRejected = false
    try { await writeTextAtomic(record, "new\n", "different\n") } catch { casRejected = true }
    const afterCas = await fs.readFile(record, "utf8")
    const after = await hashes()
    const fsRight = Either.getOrElse(fsResult, () => null) as any
    const gitRight = Either.getOrElse(gitResult, () => null) as any
    console.log(JSON.stringify({
      source_hashes_before: before, source_hashes_after: after,
      filesystem_line_range: fsRight !== null && fsRight.resolvedLocator.endsWith("#L2-L3") && fsRight.contentHash === sha("two\nthree"),
      git_commit_and_line_range: gitRight !== null && gitRight.resolvedLocator === gitLocator && gitRight.contentHash === sha("two\nthree"),
      redirect_byte_limit: Either.isLeft(redirect) && redirect.left.reason === "IO" && JSON.stringify(redirectCalls) === JSON.stringify([start, next]),
      timeout_is_bounded: Either.isLeft(timeout) && timeout.left.reason === "IO",
      cas_preserves_stale_baseline: casRejected && afterCas === "old\n",
      source_unchanged: JSON.stringify(before) === JSON.stringify(after),
    }, null, 2))
  } finally { await fs.rm(dir, { recursive: true, force: true }) }
}
void run()
