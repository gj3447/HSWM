import { chmod, mkdir, mkdtemp, readFile, readdir, rm, unlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

import { Effect } from "effect"
import { afterEach, describe, expect, it } from "vitest"

import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { BoundedSubprocess, type BoundedSubprocessShape } from "../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js"
import { CurlResearchSourceHttp, ResearchSourceHttp, archiveResearchSources, verifyResearchSourceArchive, type ResearchSourceHttpShape } from "../../src/hswm/effect-runtime/src/research-source-archive.js"
import { RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP, decodeResearchSourceManifest, sha256Hex } from "../../src/hswm/effect-runtime/src/research-source-archive-domain.js"

const roots: string[] = []
const fresh = async (): Promise<string> => { const root = await mkdtemp(join(tmpdir(), "hswm-source-archive-")); roots.push(root); return root }
afterEach(async () => { await Promise.all(roots.splice(0).map(root => rm(root, { recursive: true, force: true }))) })
const run = <A>(program: Effect.Effect<A, unknown, ResearchSourceHttp | import("../../src/hswm/effect-runtime/src/effect-posix-filesystem.js").PosixFileSystem | import("../../src/hswm/effect-runtime/src/effect-bounded-subprocess.js").BoundedSubprocess>, http: ResearchSourceHttpShape): Promise<A> => Effect.runPromise(program.pipe(Effect.provide(NodePosixServicesLive), Effect.provideService(ResearchSourceHttp, http)))
const headers = (contentType: string | null) => Object.freeze({ contentType, etag: "etag-1", lastModified: "Mon, 01 Jan 2024 00:00:00 GMT" })

describe("research source archive", () => {
  it("captures an allowlisted PDF as immutable content-addressed bytes and rehashes it", async () => {
    const root = await fresh(); const body = new Uint8Array([37, 80, 68, 70, 45, 49, 46, 55])
    let calls = 0
    const http: ResearchSourceHttpShape = { get: () => { calls += 1; return Effect.succeed({ status: 200, finalUrl: "https://cdn.example/paper.pdf", headers: headers("application/pdf"), bytes: body }) } }
    const manifest = JSON.stringify([{ id: "paper-1", url: "https://example.org/paper.pdf", expectedKind: "pdf", citations: ["doi:example"], metadata: { source: "primary" } }])
    const archived = await run(archiveResearchSources(root, manifest), http)
    expect(calls).toBe(1); expect(archived.manifest.receipts[0]).toMatchObject({ status: "ARCHIVED", originalUrl: "https://example.org/paper.pdf", requestedUrl: "https://example.org/paper.pdf", finalUrl: "https://cdn.example/paper.pdf", size: body.byteLength, metadata: { citations: ["doi:example"], source: "primary" } })
    const receipt = archived.manifest.receipts[0]
    if (receipt === undefined || receipt.status !== "ARCHIVED") throw new Error("test setup")
    expect(await readFile(join(root, receipt.blobPath))).toEqual(Buffer.from(body))
    expect((await run(verifyResearchSourceArchive(root), http)).valid).toBe(true)
  })

  it("records HTTP errors and PDF content-type mismatch without archiving error HTML", async () => {
    const root = await fresh()
    let calls = 0
    const http: ResearchSourceHttpShape = { get: request => { calls += 1; return Effect.succeed(request.url.includes("missing") ? { status: 404, finalUrl: request.url, headers: headers("text/html"), bytes: new Uint8Array() } : { status: 200, finalUrl: request.url, headers: headers("text/html"), bytes: new TextEncoder().encode("<html>error</html>") }) } }
    const archived = await run(archiveResearchSources(root, JSON.stringify([{ id: "missing", url: "https://example.org/missing.pdf", expectedKind: "pdf" }, { id: "html-error", url: "https://example.org/error.pdf", expectedKind: "pdf" }])), http)
    expect(calls).toBe(2)
    expect(archived.manifest.receipts.map(receipt => receipt.status === "FAILED" ? receipt.failure : "ARCHIVED")).toEqual(["HTTP_STATUS", "CONTENT_TYPE_MISMATCH"])
    expect(await readdir(join(root, "blobs", "sha256"))).toEqual([])
  })

  it("resumes immutable receipts without refetching and detects a tampered blob", async () => {
    const root = await fresh(); const body = new Uint8Array([1, 2, 3]); let calls = 0
    const http: ResearchSourceHttpShape = { get: () => { calls += 1; return Effect.succeed({ status: 200, finalUrl: "https://example.org/a.txt", headers: headers("text/plain"), bytes: body }) } }
    const manifest = JSON.stringify([{ id: "a", url: "https://example.org/a.txt", expectedKind: "text" }])
    const first = await run(archiveResearchSources(root, manifest), http); const second = await run(archiveResearchSources(root, manifest), { get: () => Effect.die("must not refetch") })
    expect(calls).toBe(1); expect(second.resumed).toBe(true)
    const receipt = first.manifest.receipts[0]; if (receipt === undefined || receipt.status !== "ARCHIVED") throw new Error("test setup")
    await chmod(join(root, receipt.blobPath), 0o600)
    await writeFile(join(root, receipt.blobPath), new Uint8Array([9, 9, 9]))
    const verified = await run(verifyResearchSourceArchive(root), http)
    expect(verified.valid).toBe(false); expect(verified.receipts[0]?.valid).toBe(false)
  })

  it("pins a partial archive input before restart, so a changed manifest cannot reuse its receipt ids", async () => {
    const root = await fresh(); const http: ResearchSourceHttpShape = { get: () => Effect.succeed({ status: 200, finalUrl: "https://example.org/a.txt", headers: headers("text/plain"), bytes: new Uint8Array([65]) }) }
    const initial = JSON.stringify([{ id: "a", url: "https://example.org/a.txt", expectedKind: "text" }])
    await run(archiveResearchSources(root, initial), http)
    await chmod(join(root, "manifest.receipt.v1.json"), 0o600)
    await unlink(join(root, "manifest.receipt.v1.json"))
    await expect(run(archiveResearchSources(root, JSON.stringify([{ id: "a", url: "https://example.org/different.txt", expectedKind: "text" }])), http)).rejects.toBeDefined()
    const partial = join(root, "receipts", "a.receipt.v1.json")
    await chmod(partial, 0o600); await writeFile(partial, "{}\n"); await chmod(partial, 0o400)
    await expect(run(archiveResearchSources(root, initial), http)).rejects.toBeDefined()
  })

  it("rejects tampered per-source receipts and duplicate membership during verify and resume", async () => {
    const root = await fresh(); const http: ResearchSourceHttpShape = { get: () => Effect.succeed({ status: 200, finalUrl: "https://example.org/a.txt", headers: headers("text/plain"), bytes: new Uint8Array([65]) }) }
    const manifest = JSON.stringify([{ id: "a", url: "https://example.org/a.txt", expectedKind: "text" }])
    await run(archiveResearchSources(root, manifest), http)
    const perSource = join(root, "receipts", "a.receipt.v1.json")
    await chmod(perSource, 0o600); await writeFile(perSource, "{}\n")
    expect((await run(verifyResearchSourceArchive(root), http)).valid).toBe(false)
    await expect(run(archiveResearchSources(root, manifest), http)).rejects.toBeDefined()

    const second = await fresh(); await run(archiveResearchSources(second, manifest), http)
    const indexPath = join(second, "manifest.receipt.v1.json"); const index = JSON.parse(await readFile(indexPath, "utf8")) as { receipts: unknown[] }
    await chmod(indexPath, 0o600); index.receipts = [index.receipts[0], index.receipts[0]]; await writeFile(indexPath, `${JSON.stringify(index)}\n`); await chmod(indexPath, 0o400)
    expect((await run(verifyResearchSourceArchive(second), http)).valid).toBe(false)
  })

  it("does not accept a corrupt pre-existing CAS path, HTML body mentions, or a PDF MIME lie", async () => {
    const body = new Uint8Array([65]); const digest = sha256Hex(body); const root = await fresh()
    await mkdir(join(root, "blobs", "sha256"), { recursive: true }); const corrupt = join(root, "blobs", "sha256", digest)
    await writeFile(corrupt, new Uint8Array([66])); await chmod(corrupt, 0o400)
    const textHttp: ResearchSourceHttpShape = { get: () => Effect.succeed({ status: 200, finalUrl: "https://example.org/a.txt", headers: headers("text/plain"), bytes: body }) }
    await expect(run(archiveResearchSources(root, JSON.stringify([{ id: "a", url: "https://example.org/a.txt", expectedKind: "text" }])), textHttp)).rejects.toBeDefined()

    const htmlRoot = await fresh(); const htmlHttp: ResearchSourceHttpShape = { get: request => Effect.succeed({ status: 200, finalUrl: request.url, headers: headers("text/html"), bytes: new TextEncoder().encode(request.url.includes("openreview") ? `${" ".repeat(20_000)}<title>Verifying your browser | OpenReview</title>` : "<title>Paper</title><p>Access Denied is discussed here.</p>") }) }
    const html = await run(archiveResearchSources(htmlRoot, JSON.stringify([{ id: "normal", url: "https://example.org/normal", expectedKind: "html" }, { id: "challenge", url: "https://example.org/openreview", expectedKind: "html" }])), htmlHttp)
    expect(html.manifest.receipts.map(receipt => receipt.status === "FAILED" ? receipt.failure : receipt.status)).toEqual(["ARCHIVED", "HTTP_CHALLENGE"])

    const pdfRoot = await fresh(); const pdfHttp: ResearchSourceHttpShape = { get: request => Effect.succeed({ status: 200, finalUrl: request.url, headers: headers("application/pdf"), bytes: new Uint8Array([110, 111, 116, 45, 112, 100, 102]) }) }
    const pdf = await run(archiveResearchSources(pdfRoot, JSON.stringify([{ id: "mime-lie", url: "https://example.org/file", expectedKind: "any" }])), pdfHttp)
    expect(pdf.manifest.receipts[0]).toMatchObject({ status: "FAILED", failure: "CONTENT_TYPE_MISMATCH" })
  })

  it("accepts octet-stream only when a requested PDF has a PDF signature and binds its explicit byte limit", async () => {
    const root = await fresh(); const seen: number[] = []
    const http: ResearchSourceHttpShape = { get: request => { seen.push(request.maximumBytes); return Effect.succeed({ status: 200, finalUrl: request.url, headers: headers("application/octet-stream"), bytes: request.url.includes("good") ? new TextEncoder().encode("%PDF-1.7") : new TextEncoder().encode("not-pdf") }) } }
    const archived = await run(archiveResearchSources(root, JSON.stringify([{ id: "good", url: "https://example.org/good", expectedKind: "pdf", maximumBytes: RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP }, { id: "bad", url: "https://example.org/bad", expectedKind: "pdf" }])), http)
    expect(seen).toEqual([RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP, 32 * 1024 * 1024])
    expect(archived.manifest.receipts.map(receipt => receipt.status === "FAILED" ? receipt.failure : receipt.status)).toEqual(["ARCHIVED", "CONTENT_TYPE_MISMATCH"])
    expect(archived.manifest.receipts[0]).toMatchObject({ maximumBytes: RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP, responseHeaders: { contentType: "application/octet-stream" } })
    expect(decodeResearchSourceManifest(JSON.stringify([{ id: "too-big", url: "https://example.org/x", maximumBytes: RESEARCH_SOURCE_ARCHIVE_MAXIMUM_BYTES_CAP + 1 }]))._tag).toBe("Left")
    expect(decodeResearchSourceManifest(JSON.stringify([{ id: "too-small", url: "https://example.org/x", maximumBytes: 1 }]))._tag).toBe("Left")
  })

  it("uses the explicit curl transport without a shell and binds parsed final headers and URL", async () => {
    let argv: ReadonlyArray<string> = []
    const curl: BoundedSubprocessShape = { observe: command => { argv = command.argv; return Effect.succeed({ exitCode: 0, signal: null, timedOut: false, outputTruncated: false, launchError: null, stdout: new TextEncoder().encode("HTTP/1.1 302 Found\r\nLocation: https://cdn.example/p.pdf\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nETag: etag-final\r\nLast-Modified: Tue, 02 Jan 2024 00:00:00 GMT\r\n\r\n%PDF-1.7"), stderr: new TextEncoder().encode("__HSWM_FINAL_URL__https://cdn.example/p.pdf\n") }) } }
    const result = await Effect.runPromise(CurlResearchSourceHttp.get({ url: "https://example.org/p.pdf", timeoutMs: 15_000, maximumBytes: 40_000_000 }).pipe(Effect.provideService(BoundedSubprocess, curl)))
    expect(argv).toContain("curl"); expect(argv).toContain("--proto-redir"); expect(argv).toContain("=http,https"); expect(argv).toContain("40000000")
    expect(result).toMatchObject({ status: 200, finalUrl: "https://cdn.example/p.pdf", transport: "curl", headers: { contentType: "application/pdf", etag: "etag-final" }, bytes: new TextEncoder().encode("%PDF-1.7") })
  })
})
