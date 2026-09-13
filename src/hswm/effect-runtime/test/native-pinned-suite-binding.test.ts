import { createHash } from "node:crypto"
import { cp, mkdtemp, rm, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { execFileSync } from "node:child_process"
import { Effect } from "effect"
import { afterEach, describe, expect, it } from "vitest"
import { NodeBoundedSubprocessLive } from "../src/effect-bounded-subprocess.js"
import { NodePosixFileSystemLive } from "../src/effect-posix-filesystem.js"
import { bindPinnedSuiteRoot, type PinnedSuiteSpec } from "../src/native-pinned-suite-binding.js"

const temporary: string[] = []
const git = (directory: string, ...arguments_: readonly string[]): Uint8Array =>
  Uint8Array.from(execFileSync("git", ["-C", directory, ...arguments_], { encoding: "buffer" }))
const text = (bytes: Uint8Array): string => new TextDecoder().decode(bytes).trim()
const hash = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const run = (root: string, spec: PinnedSuiteSpec) => Effect.runPromise(bindPinnedSuiteRoot(root, spec).pipe(Effect.either, Effect.provide(NodeBoundedSubprocessLive), Effect.provide(NodePosixFileSystemLive)))

const fixture = async (): Promise<{ readonly checkout: string; readonly suite: string; readonly spec: PinnedSuiteSpec }> => {
  const checkout = await mkdtemp(join(tmpdir(), "pinned-suite-source-")); temporary.push(checkout)
  const suitePath = "official/suite"
  const suite = join(checkout, suitePath)
  await writeFile(join(checkout, ".gitignore"), "ignored\n")
  await (await import("node:fs/promises")).mkdir(join(suite, "nested"), { recursive: true })
  await writeFile(join(suite, "manifest.ttl"), "manifest\n")
  await writeFile(join(suite, "nested", "case.txt"), "original\n")
  git(checkout, "init", "-q")
  git(checkout, "config", "user.email", "test@example.invalid")
  git(checkout, "config", "user.name", "Pinned suite test")
  git(checkout, "add", ".")
  git(checkout, "commit", "-qm", "fixture")
  const commit = text(git(checkout, "rev-parse", "HEAD"))
  return { checkout, suite, spec: { commit, suitePath, tree: text(git(checkout, "rev-parse", `HEAD:${suitePath}`)), archiveSha256: hash(git(checkout, "archive", "--format=tar", commit, "--", suitePath)) } }
}

afterEach(async () => { await Promise.all(temporary.splice(0).map(directory => rm(directory, { recursive: true, force: true }))) })

describe("bindPinnedSuiteRoot", () => {
  it("binds only the real pinned subtree and every committed disk byte", async () => {
    const source = await fixture()
    await expect(run(source.suite, source.spec)).resolves.toMatchObject({ _tag: "Right", right: { root: source.suite } })
    await expect(run(source.checkout, source.spec)).resolves.toMatchObject({ _tag: "Left", left: { detail: "supplied suite root is not the pinned Git subtree" } })
  })

  it("rejects an assume-unchanged modified file in a copied root", async () => {
    const source = await fixture()
    const copiedRoot = await mkdtemp(join(tmpdir(), "pinned-suite-copiedroot-")); temporary.push(copiedRoot)
    await rm(copiedRoot, { recursive: true, force: true })
    await cp(source.checkout, copiedRoot, { recursive: true })
    const modified = join(copiedRoot, "official/suite/nested/case.txt")
    await writeFile(modified, "modified while assume-unchanged\n")
    git(copiedRoot, "update-index", "--assume-unchanged", "official/suite/nested/case.txt")
    expect(text(git(copiedRoot, "status", "--porcelain", "--", "official/suite"))).toBe("")
    await expect(run(join(copiedRoot, "official/suite"), source.spec)).resolves.toMatchObject({ _tag: "Left", left: { detail: "pinned suite file content drift" } })
  })

  it("rejects ignored additions and symbolic-link paths", async () => {
    const source = await fixture()
    await writeFile(join(source.suite, "ignored"), "not tracked\n")
    await expect(run(source.suite, source.spec)).resolves.toMatchObject({ _tag: "Left", left: { detail: "pinned suite disk files differ from the pinned Git subtree" } })
    await rm(join(source.suite, "ignored"))
    await symlink("nested/case.txt", join(source.suite, "linked.txt"))
    await expect(run(source.suite, source.spec)).resolves.toMatchObject({ _tag: "Left", left: { detail: "pinned suite contains a symbolic-link path" } })
  })
})
