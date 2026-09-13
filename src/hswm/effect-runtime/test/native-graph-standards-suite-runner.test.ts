import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { createHash } from "node:crypto"
import { readFileSync } from "node:fs"
import { Effect, Layer } from "effect"
import { expect, it } from "vitest"
import { NodePosixFileSystem, NodePosixFileSystemLive, PosixFileSystem } from "../src/effect-posix-filesystem.js"
import { runNativeRdf11NQuadsSuite } from "../src/native-graph-standards-suite-runner.js"

const manifest = (entries: string) => `@prefix mf: <http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#>.\n@prefix rdft: <http://www.w3.org/ns/rdftest#>.\n${entries}`
const run = (root: string) => Effect.runPromise(runNativeRdf11NQuadsSuite(root).pipe(Effect.provide(NodePosixFileSystemLive)))

it("keeps every approved positive and negative manifest entry", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-nquads-suite-"))
  try {
    await mkdir(join(root, "syntax")); await writeFile(join(root, "syntax", "ok.nq"), "<urn:s> <urn:p> <urn:o> .\n"); await writeFile(join(root, "syntax", "bad.nq"), "not nquads\n")
    await writeFile(join(root, "manifest.ttl"), manifest("<#p> a rdft:TestNQuadsPositiveSyntax; rdft:approval rdft:Approved; mf:action <syntax/ok.nq>.\n<#n> a rdft:TestNQuadsNegativeSyntax; rdft:approval rdft:Approved; mf:action <syntax/bad.nq>.\n<#skip> a rdft:TestNQuadsPositiveSyntax; rdft:approval <urn:pending>; mf:action <syntax/ok.nq>.\n"))
    await expect(run(root)).resolves.toMatchObject({ status: "PASS", counts: { positive: 1, negative: 1, total: 2, passed: 2, failed: 0 } })
  } finally { await rm(root, { recursive: true, force: true }) }
})

it.each(["missing", "invalid-utf8"])("fails the suite when a negative fixture is %s", async kind => {
  const root = await mkdtemp(join(tmpdir(), "hswm-nquads-suite-"))
  try {
    await mkdir(join(root, "syntax")); if (kind === "invalid-utf8") await writeFile(join(root, "syntax", "bad.nq"), Buffer.from([0xff]))
    await writeFile(join(root, "manifest.ttl"), manifest("<#n> a rdft:TestNQuadsNegativeSyntax; rdft:approval rdft:Approved; mf:action <syntax/bad.nq>.\n"))
    const result = await Effect.runPromise(runNativeRdf11NQuadsSuite(root).pipe(Effect.either, Effect.provide(NodePosixFileSystemLive)))
    expect(result).toMatchObject({ _tag: "Left", left: { detail: kind === "missing" ? expect.stringContaining("unavailable") : expect.stringContaining("not valid UTF-8") } })
  } finally { await rm(root, { recursive: true, force: true }) }
})

it("rejects an empty approved denominator", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-nquads-suite-"))
  try { await writeFile(join(root, "manifest.ttl"), manifest("<#skip> a rdft:TestNQuadsPositiveSyntax; rdft:approval <urn:pending>; mf:action <missing.nq>.\n")); const result = await Effect.runPromise(runNativeRdf11NQuadsSuite(root).pipe(Effect.either, Effect.provide(NodePosixFileSystemLive))); expect(result).toMatchObject({ _tag: "Left", left: { detail: "official approved N-Quads syntax test set is empty" } }) } finally { await rm(root, { recursive: true, force: true }) }
})

it("rejects an action substituted after binding before the parser consumes it", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-nquads-suite-"))
  try {
    await mkdir(join(root, "syntax")); await writeFile(join(root, "syntax", "ok.nq"), "<urn:s> <urn:p> <urn:o> .\n"); await writeFile(join(root, "syntax", "bad.nq"), "not nquads\n")
    const source = manifest("<#p> a rdft:TestNQuadsPositiveSyntax; rdft:approval rdft:Approved; mf:action <syntax/ok.nq>.\n<#n> a rdft:TestNQuadsNegativeSyntax; rdft:approval rdft:Approved; mf:action <syntax/bad.nq>.\n")
    await writeFile(join(root, "manifest.ttl"), source)
    const expected = Object.freeze(Object.fromEntries([["manifest.ttl", createHash("sha256").update(source).digest("hex")], ["syntax/ok.nq", createHash("sha256").update("<urn:s> <urn:p> <urn:o> .\n").digest("hex")], ["syntax/bad.nq", createHash("sha256").update("not nquads\n").digest("hex")]]))
    await expect(runNativeRdf11NQuadsSuite(root).pipe(Effect.provide(NodePosixFileSystemLive), Effect.runPromise)).resolves.toMatchObject({ status: "PASS", counts: { positive: 1, negative: 1, total: 2, passed: 2, failed: 0 } })
    const substituted = Object.freeze({ ...NodePosixFileSystem, readRegularBounded: (path: string, options: Parameters<typeof NodePosixFileSystem.readRegularBounded>[1]) => path.endsWith("/syntax/ok.nq") ? Effect.succeed({ bytes: new TextEncoder().encode("restored after substituted parser read\n"), device: 1, inode: 1 }) : NodePosixFileSystem.readRegularBounded(path, options) })
    const outcome = await Effect.runPromise(runNativeRdf11NQuadsSuite(root, expected).pipe(Effect.either, Effect.provide(Layer.succeed(PosixFileSystem, substituted))))
    expect(outcome).toMatchObject({ _tag: "Left", left: { detail: expect.stringContaining("pinned suite hash drift for action") } })
  } finally { await rm(root, { recursive: true, force: true }) }
})

it("binds the recorded successor result to this runner and its full approved denominator", () => {
  const repository = new URL("../../../..", import.meta.url)
  const profile = JSON.parse(readFileSync(new URL("_research/graph_standards/native_typescript_2026-09-13/rdf11-nquads-n3-successor-profile.v1.json", repository), "utf8"))
  const result = JSON.parse(readFileSync(new URL("_research/graph_standards/native_typescript_2026-09-13/qualification/rdf11-nquads-n3-native-ts.json", repository), "utf8"))
  const runner = readFileSync(new URL(profile.runner.path, repository))
  expect(createHash("sha256").update(runner).digest("hex")).toBe(profile.runner.sha256)
  const domainRunner = readFileSync(new URL(profile.domain_runner.path, repository))
  expect(createHash("sha256").update(domainRunner).digest("hex")).toBe(profile.domain_runner.sha256)
  expect(result).toMatchObject({ status: "PASS", source_commit: profile.official_source.commit, manifest_sha256: profile.official_source.manifest_sha256, adapter: { package: profile.engine.package, version: profile.engine.version }, counts: profile.expected, failures: [] })
})
