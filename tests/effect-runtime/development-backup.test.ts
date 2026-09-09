import { access, chmod, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"
import { spawn } from "node:child_process"

import { Effect } from "effect"
import { afterEach, describe, expect, it } from "vitest"

import { runDevelopmentBackupCli } from "../../src/hswm/effect-runtime/src/development-backup.js"
import { NodePosixFileSystemLive } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"

const run = (argv: ReadonlyArray<string>) => Effect.runPromise(runDevelopmentBackupCli(argv).pipe(Effect.provide(NodePosixFileSystemLive)))

const initializeWal = (path: string): void => {
  const db = new DatabaseSync(path)
  db.exec("PRAGMA journal_mode=WAL; CREATE TABLE entries (id INTEGER PRIMARY KEY, value TEXT); INSERT INTO entries(value) VALUES ('before');")
  db.close()
}

const readRowsInFreshProcess = (path: string): Promise<string> => new Promise((resolve, reject) => {
  const child = spawn(process.execPath, ["-e", "const {DatabaseSync}=require('node:sqlite');const d=new DatabaseSync(process.argv[1],{readOnly:true});process.stdout.write(JSON.stringify(d.prepare('SELECT id,value FROM entries ORDER BY id').all()));d.close()", path])
  const chunks: Array<Buffer> = []
  child.stdout.on("data", (chunk: Buffer) => chunks.push(chunk))
  child.once("error", reject)
  child.once("exit", (code) => code === 0 ? resolve(Buffer.concat(chunks).toString("utf8")) : reject(new Error(`reader exited ${code}`)))
})

const writeInFreshProcess = (path: string): Promise<void> => new Promise((resolve, reject) => {
  const child = spawn(process.execPath, ["-e", "const {DatabaseSync}=require('node:sqlite');const d=new DatabaseSync(process.argv[1]);d.prepare('INSERT INTO entries(value) VALUES(?)').run('after-restore');d.close()", path])
  child.once("error", reject)
  child.once("exit", (code) => code === 0 ? resolve() : reject(new Error(`writer exited ${code}`)))
})

const controlledWalWriter = (path: string): { readonly ready: Promise<void>; readonly finish: () => Promise<void> } => {
  const source = "const {DatabaseSync}=require('node:sqlite');const d=new DatabaseSync(process.argv[1]);d.prepare('INSERT INTO entries(value) VALUES(?)').run('wal-before-snapshot');process.send('ready');process.once('message',()=>{d.prepare('INSERT INTO entries(value) VALUES(?)').run('after-backup');d.close();});"
  const child = spawn(process.execPath, ["-e", source, path], { stdio: ["ignore", "pipe", "pipe", "ipc"] })
  let readySeen = false
  const ready = new Promise<void>((resolve, reject) => {
    child.once("message", (message) => {
      if (message === "ready" && !readySeen) { readySeen = true; resolve() }
      else reject(new Error("writer sent an invalid readiness message"))
    })
    child.once("error", reject)
    child.once("exit", (code) => { if (!readySeen) reject(new Error(`writer exited before readiness: ${code}`)) })
  })
  const exited = new Promise<void>((resolve, reject) => {
    child.once("error", reject)
    child.once("exit", (code) => code === 0 ? resolve() : reject(new Error(`writer exited ${code}`)))
  })
  return Object.freeze({ ready, finish: () => { child.send("finish"); return exited } })
}

describe("development SQLite backup", () => {
  const roots: Array<string> = []
  afterEach(async () => {
    await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
  })

  it("uses an online WAL snapshot, detects tampering, and restores only to a fresh path", async () => {
    const root = await mkdtemp(join(tmpdir(), "hswm-development-backup-"))
    roots.push(root)
    await chmod(root, 0o700)
    const source = join(root, "source.sqlite")
    const snapshot = join(root, "snapshot.sqlite")
    const restored = join(root, "restored.sqlite")
    const existing = join(root, "existing.sqlite")
    initializeWal(source)

    // The first committed row is held in an open WAL connection during snapshot;
    // the second commit happens only after the online backup completes.
    const writer = controlledWalWriter(source)
    await writer.ready
    await run(["backup", "--source", source, "--destination", snapshot])
    await writer.finish()
    await expect(run(["verify", "--backup", snapshot])).resolves.toMatchObject({ exitCode: 0 })
    await expect(access(`${snapshot}-wal`)).rejects.toThrow()
    await expect(access(`${snapshot}-shm`)).rejects.toThrow()

    await writeFile(existing, "do not replace")
    await expect(run(["restore", "--backup", snapshot, "--destination", existing])).rejects.toThrow()
    expect(await readFile(existing, "utf8")).toBe("do not replace")

    await run(["restore", "--backup", snapshot, "--destination", restored])
    const restoredRows = await readRowsInFreshProcess(restored)
    expect(restoredRows).toContain("before")
    expect(restoredRows).toContain("wal-before-snapshot")
    expect(restoredRows).not.toContain("after-backup")
    expect(await readRowsInFreshProcess(source)).toContain("after-backup")
    await writeInFreshProcess(restored)
    expect(await readRowsInFreshProcess(restored)).toContain("after-restore")
    await expect(run(["verify", "--backup", snapshot])).resolves.toMatchObject({ exitCode: 0 })

    const alias = join(root, "alias.sqlite")
    await symlink(snapshot, alias)
    await expect(run(["verify", "--backup", alias])).rejects.toThrow()

    // A single-byte physical modification must fail the content-addressed verification.
    const bytes = await readFile(snapshot)
    bytes[bytes.byteLength - 1] = (bytes[bytes.byteLength - 1] ?? 0) ^ 1
    await chmod(snapshot, 0o600)
    await writeFile(snapshot, bytes)
    await chmod(snapshot, 0o400)
    await expect(run(["verify", "--backup", snapshot])).rejects.toThrow()
  })
})
